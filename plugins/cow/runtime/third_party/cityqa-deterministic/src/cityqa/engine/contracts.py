"""Contract and policy loading.

Every operational value the suite acts on is resolved through this module, from
a versioned instance on disk. Two rules hold without exception:

  * Operational values are never read from a JSON Schema. A schema validates
    structure; it does not hold limits.
  * Operational values are never embedded in Python. A missing contract value
    produces UNKNOWN, never a default.

The absence of a fallback is deliberate. A silent default is an unversioned,
unhashed policy that nobody approved.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .canonical import canonical_path
from .hashing import digest_bytes, digest_value
from .schema import SchemaRegistry, SchemaError

__all__ = [
    "ContractError",
    "MissingContractValue",
    "ProbeSpec",
    "ContractSet",
    "load_contract_set",
]


class ContractError(ValueError):
    """Raised when a contract instance is unusable."""


class MissingContractValue(LookupError):
    """Raised when a contract reference does not resolve.

    Callers translate this into UNKNOWN. It is never translated into a default.
    """

    def __init__(self, reference: str) -> None:
        super().__init__("contract reference does not resolve: " + reference)
        self.reference = reference


class ProbeSpec:
    """One probe's contract-declared behaviour.

    The probe implementation supplies measurement. Everything about how that
    measurement is judged -- required, severity, stop scope, authority, evidence,
    operator, limit -- comes from here.
    """

    __slots__ = (
        "probe_id", "phase", "description", "required", "severity", "stop_scope",
        "defect_domain", "unknown_promotion_rule", "required_authority",
        "required_evidence_types", "cacheable", "input_patterns", "required_probes",
        "invalidated_probes", "downstream_phases", "contract_ref", "operator",
        "metric", "unit", "failure_code", "adapter", "_raw",
    )

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self._raw = dict(raw)
        self.probe_id = raw["probeId"]
        self.phase = raw["phase"]
        self.description = raw.get("description", "")
        self.required = bool(raw["required"])
        self.severity = raw["severity"]
        self.stop_scope = raw["stopScope"]
        self.defect_domain = raw["defectDomain"]
        self.unknown_promotion_rule = raw.get("unknownPromotionRule", "block")
        self.required_authority = raw["requiredAuthority"]
        self.required_evidence_types = tuple(raw["requiredEvidenceTypes"])
        self.cacheable = bool(raw["cacheable"])
        self.input_patterns = tuple(raw.get("inputPatterns", ()))
        self.required_probes = tuple(raw.get("requiredProbes", ()))
        self.invalidated_probes = tuple(raw.get("invalidatedProbes", ()))
        self.downstream_phases = tuple(raw.get("downstreamPhases", ()))
        self.contract_ref = raw.get("contractRef")
        self.operator = raw.get("operator")
        self.metric = raw.get("metric")
        self.unit = raw.get("unit")
        self.failure_code = raw.get("failureCode")
        self.adapter = raw.get("adapter")

    def as_dict(self) -> dict[str, Any]:
        return dict(self._raw)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ProbeSpec(" + self.probe_id + ", " + self.phase + ")"


class ContractSet:
    """The loaded, validated, hash-bound contract and policy set."""

    #: Contract file name -> schema name used to validate it.
    VALIDATED = {
        "city_generation_qa.v1.json": "qa_contract",
        "evidence_authority.v1.json": "evidence_authority",
        "canonicalization_policy.v1.json": "canonicalization_policy",
        "promotion_requirements.v1.json": "promotion_requirements",
        "authority_contract.v1.json": "authority_contract",
    }

    def __init__(
        self,
        directory: Path,
        documents: Mapping[str, Any],
        digests: Mapping[str, str],
        schemas: SchemaRegistry,
    ) -> None:
        self.directory = directory
        self._documents = dict(documents)
        self._digests = dict(digests)
        self.schemas = schemas
        self._probes: dict[str, ProbeSpec] = {}
        for raw in self.qa.get("probes", []):
            spec = ProbeSpec(raw)
            if spec.probe_id in self._probes:
                raise ContractError("duplicate probeId in QA contract: " + spec.probe_id)
            self._probes[spec.probe_id] = spec

    # -- documents ------------------------------------------------------

    def document(self, name: str) -> Mapping[str, Any]:
        try:
            return self._documents[name]
        except KeyError as exc:
            raise ContractError(
                "contract " + repr(name) + " is not loaded; available: "
                + ", ".join(sorted(self._documents))
            ) from exc

    def digest(self, name: str) -> str:
        self.document(name)
        return self._digests[name]

    @property
    def qa(self) -> Mapping[str, Any]:
        return self.document("city_generation_qa.v1.json")

    @property
    def audit(self) -> Mapping[str, Any]:
        return self.document("audit_contract.v1.json")

    @property
    def authority(self) -> Mapping[str, Any]:
        return self.document("authority_contract.v1.json")

    @property
    def evidence_authority(self) -> Mapping[str, Any]:
        return self.document("evidence_authority.v1.json")

    @property
    def promotion_requirements(self) -> Mapping[str, Any]:
        return self.document("promotion_requirements.v1.json")

    @property
    def canonicalization_policy(self) -> Mapping[str, Any]:
        return self.document("canonicalization_policy.v1.json")

    @property
    def failure_codes(self) -> Mapping[str, Any]:
        return self.document("failure_codes.v1.json")

    @property
    def stage(self) -> Mapping[str, Any]:
        return self.document("stage_contract.v1.json")

    @property
    def visual(self) -> Mapping[str, Any]:
        return self.document("visual_qa.v1.json")

    @property
    def camera_plan(self) -> Mapping[str, Any]:
        return self.document("camera_plan.v1.json")

    @property
    def design_tokens(self) -> Mapping[str, Any]:
        return self.document("design_tokens.v1.json")

    # -- digests --------------------------------------------------------

    @property
    def contract_digest(self) -> str:
        """Digest of the QA contract instance alone."""
        return self.digest("city_generation_qa.v1.json")

    @property
    def policy_set_digest(self) -> str:
        """Digest binding every loaded contract instance."""
        return digest_value({"policies": dict(sorted(self._digests.items()))})

    def digests(self) -> dict[str, str]:
        return dict(sorted(self._digests.items()))

    # -- probes ---------------------------------------------------------

    @property
    def phase_order(self) -> tuple[str, ...]:
        return tuple(self.qa["phaseOrder"])

    @property
    def attempt_limit(self) -> int:
        return int(self.qa["attemptLimit"])

    def probe(self, probe_id: str) -> ProbeSpec:
        try:
            return self._probes[probe_id]
        except KeyError as exc:
            raise ContractError("no probe " + repr(probe_id) + " in the QA contract") from exc

    def probes(self) -> tuple[ProbeSpec, ...]:
        """Every probe, ordered by phase then probeId.

        Phase order is contract order; probe order inside a phase is lexical by
        probeId so that execution order is stable across runs and machines.
        """
        order = {phase: index for index, phase in enumerate(self.phase_order)}
        return tuple(
            sorted(
                self._probes.values(),
                key=lambda spec: (order.get(spec.phase, 1 << 16), spec.probe_id),
            )
        )

    def probes_for_phase(self, phase: str) -> tuple[ProbeSpec, ...]:
        return tuple(spec for spec in self.probes() if spec.phase == phase)

    def __iter__(self) -> Iterator[ProbeSpec]:
        return iter(self.probes())

    # -- operational value resolution -----------------------------------

    def resolve(self, reference: str) -> Any:
        """Resolve a dotted contract reference such as ``contracts.roads.x``.

        Raises :class:`MissingContractValue` when the reference does not exist.
        There is no default: the caller reports UNKNOWN.
        """
        if not reference:
            raise MissingContractValue(reference)
        parts = reference.split(".")
        if parts[0] != "contracts":
            raise MissingContractValue(reference)
        node: Any = self.qa.get("contracts", {})
        for part in parts[1:]:
            if not isinstance(node, Mapping) or part not in node:
                raise MissingContractValue(reference)
            node = node[part]
        if node is None:
            raise MissingContractValue(reference)
        return node

    def resolve_decimal(self, reference: str) -> Decimal:
        """Resolve a reference that must compare as an exact decimal."""
        value = self.resolve(reference)
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            raise ContractError(reference + " is a boolean, not a decimal limit")
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ContractError(
                reference + " is not an exact decimal limit: " + repr(value)
            ) from exc

    def resolve_optional(self, reference: str, present: bool = True) -> Any:
        """Resolve a reference, returning ``None`` when it is genuinely absent."""
        try:
            return self.resolve(reference)
        except MissingContractValue:
            if present:
                raise
            return None

    # -- failure code catalogue -----------------------------------------

    def failure_code_entry(self, code: str) -> Mapping[str, Any] | None:
        catalogue = self.failure_codes
        for group in ("orchestrationCodes", "evidenceCodes", "auditCodes",
                      "presentationCodes", "harnessCodes"):
            entries = catalogue.get(group, {})
            if code in entries:
                return entries[code]
        return None

    def expand_stop_scope(self, scope: str) -> tuple[str, ...]:
        """Expand a stop scope through the contract's declared expansion table.

        ``both`` is not self-describing against three named scopes, so the
        expansion is read from the contract rather than assumed here.
        """
        table = self.failure_codes.get("stopScopeExpansion", {})
        if scope not in table:
            raise ContractError(
                "stop scope " + repr(scope) + " has no declared expansion in "
                "failure_codes.v1.json"
            )
        return tuple(table[scope])


def load_contract_set(
    directory: str | Path,
    schemas: SchemaRegistry,
    strict: bool = True,
) -> ContractSet:
    """Load, validate and digest every contract instance in ``directory``."""
    root = Path(directory)
    if not root.is_dir():
        raise ContractError("contract directory not found: " + str(root))

    documents: dict[str, Any] = {}
    digests: dict[str, str] = {}
    for path in sorted(root.glob("*.json")):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ContractError(
                path.name + " begins with a byte order mark; canonical instances are "
                "UTF-8 without a BOM"
            )
        try:
            documents[path.name] = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError(path.name + " is not valid UTF-8 JSON: " + str(exc)) from exc
        digests[path.name] = digest_bytes(raw)

    if strict:
        for filename, schema_name in ContractSet.VALIDATED.items():
            if filename not in documents:
                raise ContractError("required contract instance missing: " + filename)
            try:
                result = schemas.validate(schema_name, documents[filename])
            except SchemaError as exc:
                raise ContractError(
                    "schema " + schema_name + " could not validate " + filename + ": " + str(exc)
                ) from exc
            if not result.valid:
                detail = "; ".join(str(issue) for issue in result.issues[:8])
                raise ContractError(filename + " violates " + schema_name + ": " + detail)

    return ContractSet(root, documents, digests, schemas)


def logical(path: str | Path) -> str:
    """Convenience wrapper so callers do not import canonical directly."""
    return canonical_path(str(path))
