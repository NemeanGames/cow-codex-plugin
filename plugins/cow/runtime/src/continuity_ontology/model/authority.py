"""Authority classes, orthogonal provenance and per-claim admissibility.

The seven legacy classes are preserved, but they are not a single global trust
ranking. A provider-observed count, an operation-owned result, a policy
selection and a source file establish *different* claims, so admissibility is
decided per claim type against the evidence-authority matrix, never by
comparing two class names.

The legacy label is *derived* from the orthogonal dimensions through a tested
mapping. The mapping only ever weakens: no combination of origin, method,
channel and ownership can promote an assertion above what its weakest
dimension supports.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with

__all__ = [
    "AuthorityError",
    "LEGACY_CLASSES",
    "derive_authority_class",
    "AdmissibilityDecision",
    "EvidenceAuthorityMatrix",
    "check_admissibility",
]

LEGACY_CLASSES: tuple[str, ...] = (
    "AUTHORITATIVE_SOURCE",
    "DETERMINISTIC_DERIVATION",
    "PROVIDER_OBSERVATION",
    "OPERATION_OWNED_RESULT",
    "HEURISTIC_DECISION",
    "POLICY_OR_SYNTHETIC_AID",
    "CALLER_ASSERTION",
)

#: Ceiling each origin can support, regardless of the other dimensions.
_ORIGIN_CEILING: dict[str, str] = {
    "SOURCE_ARTIFACT": "AUTHORITATIVE_SOURCE",
    "LIVE_OBSERVATION": "PROVIDER_OBSERVATION",
    "DERIVATION": "DETERMINISTIC_DERIVATION",
    "POLICY": "POLICY_OR_SYNTHETIC_AID",
    "HUMAN_INPUT": "CALLER_ASSERTION",
    "SYNTHETIC_FIXTURE": "POLICY_OR_SYNTHETIC_AID",
}

_METHOD_CEILING: dict[str, str] = {
    "MEASURED": "PROVIDER_OBSERVATION",
    "RECOMPUTED": "DETERMINISTIC_DERIVATION",
    "REPLAYED": "DETERMINISTIC_DERIVATION",
    "TRANSCRIBED": "CALLER_ASSERTION",
    "ESTIMATED": "HEURISTIC_DECISION",
    "ASSERTED": "CALLER_ASSERTION",
    "GENERATED": "POLICY_OR_SYNTHETIC_AID",
}

_CHANNEL_CEILING: dict[str, str] = {
    "FILE_BYTES": "AUTHORITATIVE_SOURCE",
    "PROCESS_API": "PROVIDER_OBSERVATION",
    "PROVIDER_API": "PROVIDER_OBSERVATION",
    "ENGINE_API": "PROVIDER_OBSERVATION",
    "SCREEN_CAPTURE": "HEURISTIC_DECISION",
    "USER_REPORT": "CALLER_ASSERTION",
    "LOG_STREAM": "HEURISTIC_DECISION",
    "NOT_OBSERVED": "CALLER_ASSERTION",
}

#: Ownership only raises to OPERATION_OWNED_RESULT when the effect is directly
#: owned; a delegated or third-party effect never reaches it by itself.
_OWNERSHIP_CEILING: dict[str, str] = {
    "DIRECTLY_OWNED": "OPERATION_OWNED_RESULT",
    "DELEGATED_WITH_RECEIPT": "PROVIDER_OBSERVATION",
    "OBSERVED_THIRD_PARTY": "HEURISTIC_DECISION",
    "NOT_APPLICABLE": "AUTHORITATIVE_SOURCE",
    "UNKNOWN": "CALLER_ASSERTION",
}


class AuthorityError(ValueError):
    """Raised when provenance dimensions are missing or unrecognized."""


def _rank(cls: str) -> int:
    """Position in the legacy order. Unknown ranks weakest, never strongest."""
    try:
        return LEGACY_CLASSES.index(cls)
    except ValueError:
        return len(LEGACY_CLASSES)


def _weakest(*classes: str) -> str:
    present = [c for c in classes if c]
    if not present:
        return "CALLER_ASSERTION"
    return max(present, key=_rank)


def derive_authority_class(provenance: Mapping[str, Any]) -> str:
    """Derive the legacy label from the orthogonal dimensions.

    The result is the weakest ceiling among origin, production method,
    observation channel and operational ownership. Synthetic material is
    additionally floored at POLICY_OR_SYNTHETIC_AID so a fixture can never
    present as an authoritative source.
    """
    for key in ("origin", "productionMethod", "observationChannel", "operationalOwnership"):
        if key not in provenance:
            raise AuthorityError("provenance is missing " + key)
    try:
        ceilings = (
            _ORIGIN_CEILING[provenance["origin"]],
            _METHOD_CEILING[provenance["productionMethod"]],
            _CHANNEL_CEILING[provenance["observationChannel"]],
            _OWNERSHIP_CEILING[provenance["operationalOwnership"]],
        )
    except KeyError as exc:
        raise AuthorityError("unrecognized provenance value: " + str(exc)) from exc
    derived = _weakest(*ceilings)
    if provenance.get("syntheticFixture"):
        derived = _weakest(derived, "POLICY_OR_SYNTHETIC_AID")
    return derived


class AdmissibilityDecision:
    __slots__ = ("admissible", "code", "reason", "claim_type", "evidence_kind")

    def __init__(self, admissible: bool, code: str, reason: str, claim_type: str, evidence_kind: str) -> None:
        self.admissible = admissible
        self.code = code
        self.reason = reason
        self.claim_type = claim_type
        self.evidence_kind = evidence_kind

    def as_dict(self) -> dict[str, Any]:
        return {
            "admissible": self.admissible,
            "code": self.code,
            "reason": self.reason,
            "claimType": self.claim_type,
            "evidenceKind": self.evidence_kind,
        }

    def __bool__(self) -> bool:
        return self.admissible

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "AdmissibilityDecision(" + self.claim_type + ", " + self.code + ")"


class EvidenceAuthorityMatrix:
    """Per-claim-type admissibility. Loaded from registries/authority-rules.json."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.document = dict(document)
        self.by_claim: dict[str, Mapping[str, Any]] = dict(document.get("byClaimType", {}))
        self.digest = digest_with("continuity.core.v2", self.document)

    def known_claim_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.by_claim))

    def rule_for(self, claim_type: str) -> Mapping[str, Any] | None:
        return self.by_claim.get(claim_type)

    def check(
        self,
        claim_type: str,
        evidence_kind: str,
        provenance: Mapping[str, Any],
        *,
        for_live_claim: bool = False,
    ) -> AdmissibilityDecision:
        rule = self.by_claim.get(claim_type)
        if rule is None:
            # An unknown claim type is never admitted by default; that is how a
            # new claim silently becoming PASS is prevented.
            return AdmissibilityDecision(
                False, "UNKNOWN_CLAIM_TYPE",
                "claim type " + repr(claim_type) + " has no admissibility rule",
                claim_type, evidence_kind,
            )
        if provenance.get("syntheticFixture") and (for_live_claim or not rule.get("syntheticAcceptable", False)):
            return AdmissibilityDecision(
                False, "INADMISSIBLE_SYNTHETIC_FOR_LIVE",
                "synthetic fixture material cannot support this claim",
                claim_type, evidence_kind,
            )
        permitted_kinds = rule.get("permittedEvidenceKinds")
        if permitted_kinds is not None and evidence_kind not in permitted_kinds:
            return AdmissibilityDecision(
                False, "INADMISSIBLE_SCOPE",
                evidence_kind + " does not support " + claim_type
                + "; permitted: " + ", ".join(sorted(permitted_kinds)),
                claim_type, evidence_kind,
            )
        permitted_classes = rule.get("permittedAuthorityClasses", ())
        derived = derive_authority_class(provenance)
        declared = provenance.get("authorityClass")
        if declared and _rank(declared) < _rank(derived):
            return AdmissibilityDecision(
                False, "AUTHORITY_UPGRADE_ATTEMPT",
                "declared authority " + declared + " is stronger than the "
                + derived + " its own provenance supports",
                claim_type, evidence_kind,
            )
        if derived not in permitted_classes:
            return AdmissibilityDecision(
                False, "INADMISSIBLE_AUTHORITY",
                derived + " is not admitted for " + claim_type
                + "; permitted: " + ", ".join(sorted(permitted_classes)),
                claim_type, evidence_kind,
            )
        required_channels = rule.get("requiredObservationChannels")
        if required_channels and provenance.get("observationChannel") not in required_channels:
            return AdmissibilityDecision(
                False, "INADMISSIBLE_SCOPE",
                "channel " + str(provenance.get("observationChannel"))
                + " is not one of the required channels for " + claim_type,
                claim_type, evidence_kind,
            )
        return AdmissibilityDecision(True, "ADMISSIBLE", "meets the matrix rule", claim_type, evidence_kind)


def check_admissibility(
    matrix: EvidenceAuthorityMatrix,
    claim_type: str,
    evidence_kind: str,
    provenance: Mapping[str, Any],
    *,
    for_live_claim: bool = False,
) -> AdmissibilityDecision:
    return matrix.check(claim_type, evidence_kind, provenance, for_live_claim=for_live_claim)
