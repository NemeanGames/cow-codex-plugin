"""Record and graph validation against the resolved semantic model.

Validation is fail-closed. An unknown production field is an error, not a
silently preserved extra; an unknown vocabulary value is an error, not a
pass-through string. A structural success here establishes shape only -- it
never implies observed execution, correct geometry, accepted work, authorized
mutation or independent audit.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from ..model.metamodel import Metamodel, load_metamodel

__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "RecordValidator",
    "validate_record",
    "ID_PATTERN",
]

#: A bounded identifier: a restricted alphabet and at most 4096 characters.
#: The bound exists to keep identifiers sane, not to fit a filesystem
#: component: an evidence ID carries the whole escaped relative path of its
#: file (``ev.<escaped path>``), which can legitimately exceed 256 characters
#: for a deeply nested path. File names are bounded separately.
#: The generators read ID_PATTERN so the published JSON Schemas, the
#: TypeScript types and this validator carry one identifier grammar; a test
#: asserts the generated pattern equals this one.
_ID_MAX_LENGTH = 4096
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@/+-]{0," + str(_ID_MAX_LENGTH - 1) + r"}$"
_ID_RE = re.compile(ID_PATTERN)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$"
)
_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

_MAX_DEPTH = 64

#: A field name allowed to carry opaque extension data. Content under it can
#: never influence acceptance, authority or required behaviour.
EXTENSION_FIELD = "x-extension"


class ValidationIssue:
    __slots__ = ("path", "code", "message")

    def __init__(self, path: str, code: str, message: str) -> None:
        self.path = path
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ValidationIssue(" + self.path + ", " + self.code + ")"


class ValidationResult:
    __slots__ = ("record_type", "issues")

    def __init__(self, record_type: str, issues: Sequence[ValidationIssue]) -> None:
        self.record_type = record_type
        self.issues = list(issues)

    @property
    def ok(self) -> bool:
        return not self.issues

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted({i.code for i in self.issues}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "recordType": self.record_type,
            "valid": self.ok,
            "issues": [i.as_dict() for i in self.issues],
        }

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ValidationResult(" + self.record_type + ", ok=" + str(self.ok) + ")"


class RecordValidator:
    """Validates instances of the model's entities."""

    def __init__(self, metamodel: Metamodel | None = None) -> None:
        self.model = metamodel or load_metamodel()
        self._envelope_fields = self.model.record_envelope.get("fields", {})

    # -- public ------------------------------------------------------------

    def validate(
        self,
        record_type: str,
        value: Any,
        *,
        with_envelope: bool | None = None,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        entity = self.model.entities.get(record_type)
        if entity is None:
            issues.append(
                ValidationIssue("$", "UNKNOWN_RECORD_TYPE", "no entity named " + repr(record_type))
            )
            return ValidationResult(record_type, issues)
        if not isinstance(value, Mapping):
            issues.append(
                ValidationIssue("$", "NOT_AN_OBJECT", "record must be an object, got " + type(value).__name__)
            )
            return ValidationResult(record_type, issues)

        require_envelope = entity.identity_bearing if with_envelope is None else with_envelope
        known: set[str] = set(entity.fields)
        if require_envelope:
            known |= set(self._envelope_fields)
            for name, spec in self._envelope_fields.items():
                if spec.get("required") and name not in value:
                    issues.append(
                        ValidationIssue("$." + name, "MISSING_ENVELOPE_FIELD", "envelope field is required")
                    )
                elif name in value:
                    self._check(value[name], spec["type"], "$." + name, issues, 0)
            declared = value.get("recordType")
            if declared is not None and declared != record_type:
                issues.append(
                    ValidationIssue(
                        "$.recordType",
                        "RECORD_TYPE_MISMATCH",
                        "envelope says " + repr(declared) + " but validating as " + repr(record_type),
                    )
                )

        for name, field in sorted(entity.fields.items()):
            if name not in value:
                if field.required:
                    issues.append(
                        ValidationIssue("$." + name, "MISSING_REQUIRED_FIELD", "field is required")
                    )
                continue
            self._check(value[name], field.type, "$." + name, issues, 0)

        for name in sorted(value):
            if name in known or name == EXTENSION_FIELD:
                continue
            issues.append(
                ValidationIssue(
                    "$." + name,
                    "UNKNOWN_PRODUCTION_FIELD",
                    "unknown field; put versioned extension data under " + repr(EXTENSION_FIELD)
                    + " where it cannot affect acceptance, authority or required behaviour",
                )
            )
        if EXTENSION_FIELD in value and not isinstance(value[EXTENSION_FIELD], Mapping):
            issues.append(
                ValidationIssue("$." + EXTENSION_FIELD, "MALFORMED_EXTENSION", "extension data must be an object")
            )

        return ValidationResult(record_type, issues)

    # -- type dispatch -----------------------------------------------------

    def _check(self, value: Any, spec: Any, path: str, issues: list[ValidationIssue], depth: int) -> None:
        if depth > _MAX_DEPTH:
            issues.append(ValidationIssue(path, "DEPTH_EXCEEDED", "value nesting exceeds the validation bound"))
            return
        if isinstance(spec, str):
            self._check_scalar(value, spec, path, issues)
            return
        if not isinstance(spec, Mapping) or len(spec) != 1:
            issues.append(ValidationIssue(path, "MALFORMED_TYPE", "type constructor is malformed"))
            return
        (ctor, arg), = spec.items()
        if ctor == "enum":
            allowed = self.model.vocabulary_values(arg)
            if not isinstance(value, str) or value not in allowed:
                issues.append(
                    ValidationIssue(
                        path,
                        "VOCABULARY_VIOLATION",
                        repr(value) + " is not in " + arg + " " + str(list(allowed)),
                    )
                )
            return
        if ctor == "ref":
            self._check_ref(value, arg, path, issues, depth)
            return
        if ctor == "list":
            if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
                issues.append(ValidationIssue(path, "NOT_A_LIST", "expected a list"))
                return
            for index, item in enumerate(value):
                self._check(item, arg, path + "[" + str(index) + "]", issues, depth + 1)
            return
        if ctor == "map":
            if not isinstance(value, Mapping):
                issues.append(ValidationIssue(path, "NOT_A_MAP", "expected an object"))
                return
            for key in sorted(value):
                if not isinstance(key, str):
                    issues.append(ValidationIssue(path, "NON_STRING_KEY", "map keys must be strings"))
                    continue
                self._check(value[key], arg, path + "." + key, issues, depth + 1)
            return
        if ctor == "object":
            if not isinstance(value, Mapping):
                issues.append(ValidationIssue(path, "NOT_AN_OBJECT", "expected an object"))
                return
            declared = dict(arg)
            for name, sub in sorted(declared.items()):
                if name not in value:
                    if sub.get("required"):
                        issues.append(
                            ValidationIssue(path + "." + name, "MISSING_REQUIRED_FIELD", "field is required")
                        )
                    continue
                self._check(value[name], sub["type"], path + "." + name, issues, depth + 1)
            for name in sorted(value):
                if name not in declared:
                    issues.append(
                        ValidationIssue(path + "." + name, "UNKNOWN_PRODUCTION_FIELD", "unknown field")
                    )
            return
        issues.append(ValidationIssue(path, "MALFORMED_TYPE", "unknown constructor " + repr(ctor)))

    def _check_ref(self, value: Any, target: str, path: str, issues: list[ValidationIssue], depth: int) -> None:
        """A reference is either an identifier/digest or an embedded record."""
        if isinstance(value, str):
            if not (_ID_RE.match(value) or _DIGEST_RE.match(value)):
                issues.append(
                    ValidationIssue(path, "MALFORMED_REFERENCE", "not a usable identifier or digest")
                )
            return
        if isinstance(value, Mapping):
            nested = self.validate(target, value, with_envelope=False)
            for issue in nested.issues:
                issues.append(
                    ValidationIssue(path + issue.path[1:], issue.code, issue.message)
                )
            return
        issues.append(
            ValidationIssue(path, "MALFORMED_REFERENCE", "expected an identifier, digest or embedded " + target)
        )

    def _check_scalar(self, value: Any, kind: str, path: str, issues: list[ValidationIssue]) -> None:
        if kind == "json":
            return
        if kind in ("string", "text"):
            if not isinstance(value, str):
                issues.append(ValidationIssue(path, "NOT_A_STRING", "expected a string"))
            return
        if kind == "boolean":
            if not isinstance(value, bool):
                issues.append(ValidationIssue(path, "NOT_A_BOOLEAN", "expected true or false"))
            return
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                issues.append(ValidationIssue(path, "NOT_AN_INTEGER", "expected an integer"))
            return
        if kind == "duration_ms":
            if isinstance(value, bool) or not isinstance(value, int):
                issues.append(ValidationIssue(path, "NOT_AN_INTEGER", "expected an integer millisecond count"))
            elif value < 0:
                issues.append(ValidationIssue(path, "NEGATIVE_DURATION", "duration cannot be negative"))
            return
        if kind == "decimal":
            if isinstance(value, bool):
                issues.append(ValidationIssue(path, "NOT_A_DECIMAL", "expected an exact decimal string"))
                return
            if isinstance(value, float):
                issues.append(
                    ValidationIssue(
                        path,
                        "FLOAT_DECIMAL",
                        "decimals travel as exact strings; a binary float has no stable digest text",
                    )
                )
                return
            if isinstance(value, int):
                return
            if not isinstance(value, str):
                issues.append(ValidationIssue(path, "NOT_A_DECIMAL", "expected an exact decimal string"))
                return
            try:
                parsed = Decimal(value)
            except InvalidOperation:
                issues.append(ValidationIssue(path, "NOT_A_DECIMAL", "not parseable as a decimal"))
                return
            if not parsed.is_finite():
                issues.append(ValidationIssue(path, "NONFINITE_DECIMAL", "NaN and infinity are not values"))
            return
        if kind == "timestamp":
            if not isinstance(value, str) or not _TIMESTAMP_RE.match(value):
                issues.append(ValidationIssue(path, "MALFORMED_TIMESTAMP", "expected RFC3339 UTC or offset time"))
            return
        if kind == "digest":
            if not isinstance(value, str) or not (_DIGEST_RE.match(value) or _BARE_DIGEST_RE.match(value)):
                issues.append(ValidationIssue(path, "MALFORMED_DIGEST", "expected sha256:<64 hex> or bare 64 hex"))
            return
        if kind == "id":
            if not isinstance(value, str) or not _ID_RE.match(value):
                issues.append(ValidationIssue(path, "MALFORMED_ID", "expected a bounded identifier"))
            return
        if kind == "uri":
            if not isinstance(value, str) or not _URI_RE.match(value):
                issues.append(ValidationIssue(path, "MALFORMED_URI", "expected an absolute URI"))
            return
        issues.append(ValidationIssue(path, "MALFORMED_TYPE", "unknown scalar " + repr(kind)))


_DEFAULT: RecordValidator | None = None


def validate_record(record_type: str, value: Any, metamodel: Metamodel | None = None) -> ValidationResult:
    """Validate one record with a cached default validator."""
    global _DEFAULT
    if metamodel is not None:
        return RecordValidator(metamodel).validate(record_type, value)
    if _DEFAULT is None:
        _DEFAULT = RecordValidator()
    return _DEFAULT.validate(record_type, value)
