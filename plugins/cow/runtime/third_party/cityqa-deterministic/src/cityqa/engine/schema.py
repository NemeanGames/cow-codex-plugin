"""A bounded, dependency-free JSON Schema validator.

The suite validates its own structure with this module rather than importing a
third-party validator. The QA, audit and promotion paths therefore import
nothing outside the standard library, which keeps a hash-bound tool free of a
supply-chain surface it cannot itself verify, and satisfies the no-network
runtime constraint without vendoring.

Supported keywords (draft 2020-12 subset):

    structural   type, enum, const, $ref (local, "#/$defs/name"), $defs
    objects      properties, patternProperties, additionalProperties, required,
                 propertyNames, minProperties, maxProperties, dependentRequired
    arrays       items, prefixItems, minItems, maxItems, uniqueItems, contains
    strings      minLength, maxLength, pattern, format
    numbers      minimum, maximum, exclusiveMinimum, exclusiveMaximum,
                 multipleOf
    combinators  allOf, anyOf, oneOf, not, if/then/else

Anything else in a schema document is a schema authoring error and is reported
as such: an unknown keyword is never ignored silently, because a silently
ignored constraint is an unenforced contract.

A schema validates *structure*. Numeric limits, operators, units, required
evidence, severity, stop scope, tolerances and promotion conditions belong to
versioned policy instances and are never read from a schema (directive
section 2).
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .canonical import canonical_text

__all__ = [
    "SchemaError",
    "ValidationIssue",
    "ValidationResult",
    "validate",
    "SchemaRegistry",
]

_KNOWN_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "$comment",
        "title",
        "description",
        "examples",
        "default",
        "deprecated",
        "readOnly",
        "type",
        "enum",
        "const",
        "properties",
        "patternProperties",
        "additionalProperties",
        "required",
        "propertyNames",
        "minProperties",
        "maxProperties",
        "dependentRequired",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "uniqueItems",
        "contains",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "if",
        "then",
        "else",
    }
)

_TYPE_CHECKS = {
    "null": lambda value: value is None,
    "boolean": lambda value: isinstance(value, bool),
    "object": lambda value: isinstance(value, Mapping),
    "array": lambda value: isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: (isinstance(value, int) and not isinstance(value, bool))
    or (isinstance(value, Decimal) and value == value.to_integral_value()),
    "number": lambda value: isinstance(value, (int, float, Decimal))
    and not isinstance(value, bool),
}

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_LOGICAL_PATH_RE = re.compile(r"^[^\\]*$")

_FORMATS = {
    "sha256-digest": _DIGEST_RE,
    "uuid": _UUID_RE,
    "date-time": _DATETIME_RE,
    "semver": _SEMVER_RE,
    "logical-path": _LOGICAL_PATH_RE,
}


class SchemaError(ValueError):
    """Raised when a schema document is itself malformed."""


class ValidationIssue:
    """One structural violation, addressed by instance path."""

    __slots__ = ("path", "keyword", "message")

    def __init__(self, path: str, keyword: str, message: str) -> None:
        self.path = path
        self.keyword = keyword
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "keyword": self.keyword, "message": self.message}

    def __str__(self) -> str:
        return self.path + ": " + self.message

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ValidationIssue(%r, %r)" % (self.path, self.message)


class ValidationResult:
    """The outcome of validating one instance against one schema."""

    __slots__ = ("schema_id", "issues")

    def __init__(self, schema_id: str, issues: Sequence[ValidationIssue]) -> None:
        self.schema_id = schema_id
        self.issues = list(issues)

    @property
    def valid(self) -> bool:
        return not self.issues

    def __bool__(self) -> bool:
        return self.valid

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaId": self.schema_id,
            "valid": self.valid,
            "issueCount": len(self.issues),
            "issues": [issue.as_dict() for issue in self.issues],
        }

    def raise_for_issues(self) -> None:
        if self.issues:
            detail = "; ".join(str(issue) for issue in self.issues[:8])
            raise SchemaError(
                "instance does not satisfy " + self.schema_id + ": " + detail
            )


class _Validator:
    def __init__(self, root: Mapping[str, Any], registry: "SchemaRegistry | None") -> None:
        self.root = root
        self.registry = registry
        self.issues: list[ValidationIssue] = []

    def fail(self, path: str, keyword: str, message: str) -> None:
        self.issues.append(ValidationIssue(path, keyword, message))

    def resolve(self, ref: str, path: str) -> Mapping[str, Any] | None:
        if ref.startswith("#/$defs/"):
            name = ref[len("#/$defs/"):]
            defs = self.root.get("$defs", {})
            target = defs.get(name)
            if target is None:
                raise SchemaError("unresolved local $ref: " + ref)
            return target
        if self.registry is not None:
            target = self.registry.resolve_external(ref)
            if target is not None:
                return target
        raise SchemaError("unresolved $ref: " + ref)

    def check(self, schema: Any, value: Any, path: str) -> None:
        if schema is True:
            return
        if schema is False:
            self.fail(path, "false", "schema forbids any value here")
            return
        if not isinstance(schema, Mapping):
            raise SchemaError("schema fragment at " + path + " is not an object")

        unknown = sorted(set(schema) - _KNOWN_KEYWORDS)
        if unknown:
            raise SchemaError(
                "unsupported schema keyword(s) at " + path + ": " + ", ".join(unknown)
            )

        if "$ref" in schema:
            target = self.resolve(schema["$ref"], path)
            self.check(target, value, path)

        self._check_type(schema, value, path)
        self._check_enum(schema, value, path)
        self._check_object(schema, value, path)
        self._check_array(schema, value, path)
        self._check_string(schema, value, path)
        self._check_number(schema, value, path)
        self._check_combinators(schema, value, path)

    # -- type -----------------------------------------------------------

    def _check_type(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        declared = schema.get("type")
        if declared is None:
            return
        names = [declared] if isinstance(declared, str) else list(declared)
        for name in names:
            check = _TYPE_CHECKS.get(name)
            if check is None:
                raise SchemaError("unknown type name " + repr(name) + " at " + path)
            if check(value):
                return
        self.fail(
            path,
            "type",
            "expected type " + "|".join(names) + ", observed " + _type_name(value),
        )

    def _check_enum(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        if "enum" in schema:
            allowed = schema["enum"]
            if not any(_equal(value, candidate) for candidate in allowed):
                self.fail(
                    path,
                    "enum",
                    "value " + _brief(value) + " is outside the permitted set "
                    + _brief(allowed),
                )
        if "const" in schema:
            if not _equal(value, schema["const"]):
                self.fail(
                    path,
                    "const",
                    "value must equal " + _brief(schema["const"]) + ", observed " + _brief(value),
                )

    # -- objects --------------------------------------------------------

    def _check_object(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        if not isinstance(value, Mapping):
            return
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        additional = schema.get("additionalProperties")

        for name in schema.get("required", []):
            if name not in value:
                self.fail(path, "required", "required field " + repr(name) + " is absent")

        minimum = schema.get("minProperties")
        if minimum is not None and len(value) < minimum:
            self.fail(path, "minProperties", "fewer than %d properties" % minimum)
        maximum = schema.get("maxProperties")
        if maximum is not None and len(value) > maximum:
            self.fail(path, "maxProperties", "more than %d properties" % maximum)

        names_schema = schema.get("propertyNames")
        compiled = [(re.compile(p), s) for p, s in pattern_properties.items()]

        for key in sorted(value):
            child_path = path + "." + str(key)
            if names_schema is not None:
                self.check(names_schema, key, child_path + "<name>")
            matched = False
            if key in properties:
                self.check(properties[key], value[key], child_path)
                matched = True
            for regex, subschema in compiled:
                if regex.search(str(key)):
                    self.check(subschema, value[key], child_path)
                    matched = True
            if not matched and additional is not None:
                if additional is False:
                    self.fail(
                        child_path,
                        "additionalProperties",
                        "field " + repr(key) + " is not permitted by the schema",
                    )
                elif additional is not True:
                    self.check(additional, value[key], child_path)

        for trigger, dependents in schema.get("dependentRequired", {}).items():
            if trigger in value:
                for dependent in dependents:
                    if dependent not in value:
                        self.fail(
                            path,
                            "dependentRequired",
                            "field " + repr(dependent) + " is required when "
                            + repr(trigger) + " is present",
                        )

    # -- arrays ---------------------------------------------------------

    def _check_array(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
            return
        prefix = schema.get("prefixItems")
        offset = 0
        if prefix is not None:
            for index, subschema in enumerate(prefix):
                if index < len(value):
                    self.check(subschema, value[index], path + "[%d]" % index)
            offset = len(prefix)
        items = schema.get("items")
        if items is not None:
            for index in range(offset, len(value)):
                self.check(items, value[index], path + "[%d]" % index)

        minimum = schema.get("minItems")
        if minimum is not None and len(value) < minimum:
            self.fail(path, "minItems", "fewer than %d items" % minimum)
        maximum = schema.get("maxItems")
        if maximum is not None and len(value) > maximum:
            self.fail(path, "maxItems", "more than %d items" % maximum)
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for index, element in enumerate(value):
                text = canonical_text(element)
                if text in seen:
                    self.fail(
                        path + "[%d]" % index,
                        "uniqueItems",
                        "duplicate item " + _brief(element),
                    )
                seen.add(text)
        contains = schema.get("contains")
        if contains is not None:
            if not any(_sub_valid(self, contains, element) for element in value):
                self.fail(path, "contains", "no item satisfies the contains schema")

    # -- strings --------------------------------------------------------

    def _check_string(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        if not isinstance(value, str):
            return
        minimum = schema.get("minLength")
        if minimum is not None and len(value) < minimum:
            self.fail(path, "minLength", "shorter than %d characters" % minimum)
        maximum = schema.get("maxLength")
        if maximum is not None and len(value) > maximum:
            self.fail(path, "maxLength", "longer than %d characters" % maximum)
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            self.fail(path, "pattern", "does not match " + repr(pattern))
        fmt = schema.get("format")
        if fmt is not None:
            regex = _FORMATS.get(fmt)
            if regex is None:
                raise SchemaError("unknown format " + repr(fmt) + " at " + path)
            if regex.match(value) is None:
                self.fail(path, "format", "is not a valid " + fmt)

    # -- numbers --------------------------------------------------------

    def _check_number(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            return
        numeric = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
        for keyword, comparator, wording in (
            ("minimum", lambda a, b: a >= b, "below the minimum"),
            ("maximum", lambda a, b: a <= b, "above the maximum"),
            ("exclusiveMinimum", lambda a, b: a > b, "not above the exclusive minimum"),
            ("exclusiveMaximum", lambda a, b: a < b, "not below the exclusive maximum"),
        ):
            bound = schema.get(keyword)
            if bound is not None and not comparator(numeric, Decimal(str(bound))):
                self.fail(path, keyword, str(value) + " is " + wording + " " + str(bound))
        multiple = schema.get("multipleOf")
        if multiple is not None:
            step = Decimal(str(multiple))
            if step == 0 or (numeric % step) != 0:
                self.fail(path, "multipleOf", str(value) + " is not a multiple of " + str(multiple))

    # -- combinators ----------------------------------------------------

    def _check_combinators(self, schema: Mapping[str, Any], value: Any, path: str) -> None:
        for subschema in schema.get("allOf", []):
            self.check(subschema, value, path)

        if "anyOf" in schema:
            if not any(_sub_valid(self, sub, value) for sub in schema["anyOf"]):
                self.fail(path, "anyOf", "value satisfies none of the permitted variants")

        if "oneOf" in schema:
            matches = sum(1 for sub in schema["oneOf"] if _sub_valid(self, sub, value))
            if matches != 1:
                self.fail(
                    path,
                    "oneOf",
                    "value satisfies %d variants; exactly one is required" % matches,
                )

        if "not" in schema and _sub_valid(self, schema["not"], value):
            self.fail(path, "not", "value satisfies a schema it must not satisfy")

        if "if" in schema:
            branch = "then" if _sub_valid(self, schema["if"], value) else "else"
            if branch in schema:
                self.check(schema[branch], value, path)


def _sub_valid(parent: _Validator, schema: Any, value: Any) -> bool:
    probe = _Validator(parent.root, parent.registry)
    probe.check(schema, value, "$")
    return not probe.issues


def _equal(left: Any, right: Any) -> bool:
    left_is_bool = isinstance(left, bool)
    right_is_bool = isinstance(right, bool)
    if left_is_bool != right_is_bool:
        # A boolean never equals a number here, even though bool subclasses int.
        return False
    if left_is_bool:
        return left is right
    if isinstance(left, (int, float, Decimal)) and isinstance(right, (int, float, Decimal)):
        return Decimal(str(left)) == Decimal(str(right))
    try:
        return canonical_text(left) == canonical_text(right)
    except Exception:
        return left == right


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, Decimal)):
        return "integer/number"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _brief(value: Any, limit: int = 72) -> str:
    try:
        text = canonical_text(value)
    except Exception:
        text = repr(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def validate(
    schema: Mapping[str, Any],
    instance: Any,
    registry: "SchemaRegistry | None" = None,
) -> ValidationResult:
    """Validate ``instance`` against ``schema`` and return every issue found."""
    validator = _Validator(schema, registry)
    validator.check(schema, instance, "$")
    validator.issues.sort(key=lambda issue: (issue.path, issue.keyword, issue.message))
    return ValidationResult(str(schema.get("$id", "<inline>")), validator.issues)


class SchemaRegistry:
    """Loads the repository's schema documents and validates against them.

    The registry hashes every schema it loads. Those digests are what the
    receipts bind to, so a schema edit is visible in the receipt rather than
    silently changing what a past receipt meant.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._schemas: dict[str, Mapping[str, Any]] = {}
        self._digests: dict[str, str] = {}
        self._by_id: dict[str, Mapping[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        import json

        from .hashing import digest_bytes

        if not self.directory.is_dir():
            raise SchemaError("schema directory not found: " + str(self.directory))
        for path in sorted(self.directory.glob("*.schema.json")):
            raw = path.read_bytes()
            try:
                document = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SchemaError("schema " + path.name + " is not valid JSON: " + str(exc)) from exc
            name = path.name[: -len(".schema.json")]
            self._schemas[name] = document
            self._digests[name] = digest_bytes(raw)
            identifier = document.get("$id")
            if identifier:
                self._by_id[str(identifier)] = document

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas))

    def get(self, name: str) -> Mapping[str, Any]:
        try:
            return self._schemas[name]
        except KeyError as exc:
            raise SchemaError(
                "no schema named " + repr(name) + "; available: " + ", ".join(self.names)
            ) from exc

    def digest(self, name: str) -> str:
        self.get(name)
        return self._digests[name]

    def digests(self) -> dict[str, str]:
        return dict(sorted(self._digests.items()))

    def set_digest(self) -> str:
        """Digest of the whole schema set, bound into receipts."""
        from .hashing import digest_value

        return digest_value({"schemas": self.digests()})

    def resolve_external(self, ref: str) -> Mapping[str, Any] | None:
        if ref in self._by_id:
            return self._by_id[ref]
        base = ref.split("/")[-1]
        if base.endswith(".schema.json"):
            name = base[: -len(".schema.json")]
            if name in self._schemas:
                return self._schemas[name]
        return None

    def validate(self, name: str, instance: Any) -> ValidationResult:
        return validate(self.get(name), instance, self)

    def check_all_wellformed(self) -> list[str]:
        """Return the names of schemas that fail to compile.

        A schema this validator cannot execute is an authoring error, so the
        repository verifier calls this rather than discovering it at run time.
        """
        broken: list[str] = []
        for name in self.names:
            try:
                validate(self.get(name), _PROBE_INSTANCE, self)
            except SchemaError:
                broken.append(name)
        return broken


# A deliberately mismatched probe value: it exercises every keyword branch in a
# schema without ever satisfying it, which is enough to surface authoring errors.
_PROBE_INSTANCE: Any = {"__probe__": [1, "x", None, {"k": 2}]}
