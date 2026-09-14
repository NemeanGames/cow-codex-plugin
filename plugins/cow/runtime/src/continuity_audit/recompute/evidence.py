"""Independent recomputation of evidence sufficiency and claim status.

This is deliberately *not* the producer's algorithm re-run. The producer walks
requirements and looks for matching evidence. This walks the evidence store
first, builds a kind-to-digest index, re-derives each item's admissibility from
the authority matrix rather than trusting the ``admissibility`` field the
producer wrote, and only then answers each requirement.

The practical consequence is that the auditor can and does disagree: a producer
that marked inadmissible evidence as ADMISSIBLE gets contradicted here, which
is exactly the behaviour a producer re-running its own function could never
exhibit.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "recompute_sufficiency",
    "recompute_claim_status",
    "LEGACY_CLASS_ORDER",
]

#: Re-declared here rather than imported from the producer. If the two ever
#: diverge, the parity test in tests/conformance catches it; importing would
#: hide the divergence instead of surfacing it.
LEGACY_CLASS_ORDER: tuple[str, ...] = (
    "AUTHORITATIVE_SOURCE",
    "DETERMINISTIC_DERIVATION",
    "PROVIDER_OBSERVATION",
    "OPERATION_OWNED_RESULT",
    "HEURISTIC_DECISION",
    "POLICY_OR_SYNTHETIC_AID",
    "CALLER_ASSERTION",
)


def _index_by_kind(evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    """Evidence-major index. The producer is requirement-major."""
    index: dict[str, list[str]] = {}
    for digest in sorted(evidence):
        record = evidence[digest]
        index.setdefault(str(record.get("evidenceKind")), []).append(digest)
    return index


def _rederive_admissibility(
    record: Mapping[str, Any],
    claim_type: str,
    matrix: Mapping[str, Any],
) -> tuple[bool, str]:
    """Re-derive admissibility from the matrix, ignoring the producer's field."""
    rules = matrix.get("byClaimType", {})
    rule = rules.get(claim_type)
    if rule is None:
        return False, "claim type " + repr(claim_type) + " has no admissibility rule"

    provenance = record.get("provenance", {})
    if record.get("synthetic") or provenance.get("syntheticFixture"):
        if not rule.get("syntheticAcceptable", False):
            return False, "synthetic material is inadmissible for " + claim_type

    kind = str(record.get("evidenceKind"))
    permitted_kinds = rule.get("permittedEvidenceKinds")
    if permitted_kinds is not None and kind not in permitted_kinds:
        return False, kind + " is not a permitted evidence kind for " + claim_type

    declared_class = provenance.get("authorityClass") or record.get("authorityClass")
    permitted_classes = rule.get("permittedAuthorityClasses", ())
    if declared_class not in permitted_classes:
        return False, (
            str(declared_class) + " is not an admitted authority class for " + claim_type
        )

    required_channels = rule.get("requiredObservationChannels")
    if required_channels:
        channel = provenance.get("observationChannel")
        if channel not in required_channels:
            return False, (
                "observation channel " + str(channel) + " is not required-channel for " + claim_type
            )
    return True, "admissible under the matrix rule for " + claim_type


def recompute_sufficiency(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    matrix: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute one claim's evidence sufficiency from the evidence store."""
    claim_type = str(claim.get("proposition", {}).get("claimType"))
    by_kind = _index_by_kind(evidence)

    results: list[dict[str, Any]] = []
    mandatory_applicable = 0
    mandatory_satisfied = 0

    for requirement in claim.get("requiredEvidence", []):
        kind = str(requirement.get("evidenceKind"))
        applicable = bool(requirement.get("applicable", True))
        mandatory = bool(requirement.get("mandatory", False))
        candidates = by_kind.get(kind, [])

        admitted: list[str] = []
        rejections: list[str] = []
        for digest in candidates:
            ok, why = _rederive_admissibility(evidence[digest], claim_type, matrix)
            if ok and requirement.get("syntheticAcceptable", True) is False and (
                evidence[digest].get("synthetic")
                or evidence[digest].get("provenance", {}).get("syntheticFixture")
            ):
                ok, why = False, "this requirement forbids synthetic evidence"
            if ok:
                admitted.append(digest)
            else:
                rejections.append(digest + ": " + why)

        satisfied = bool(admitted)
        if applicable and mandatory:
            mandatory_applicable += 1
            if satisfied:
                mandatory_satisfied += 1
        results.append(
            {
                "requirementId": requirement.get("requirementId"),
                "satisfied": satisfied,
                "mandatory": mandatory,
                "applicable": applicable,
                "reason": (
                    "re-derived " + str(len(admitted)) + " admissible item(s)"
                    if satisfied
                    else ("no admissible evidence of kind " + kind
                          + ("; rejected: " + "; ".join(rejections) if rejections else ""))
                ),
                "evidenceRefs": admitted,
            }
        )

    return {
        "recordType": "EvidenceSufficiencyReceipt",
        "requirementResults": results,
        "mandatoryApplicable": mandatory_applicable,
        "mandatorySatisfied": mandatory_satisfied,
        "closed": mandatory_applicable == mandatory_satisfied,
        "recomputedBy": "continuity_audit.recompute.evidence",
    }


def recompute_claim_status(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    matrix: Mapping[str, Any],
    observed_values: Mapping[str, Any],
    *,
    blocked_by: Sequence[str] = (),
    collector_errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Recompute one claim to a five-state status.

    The five states are kept genuinely distinct:

    * ``NOT_RUN`` -- a prior dependency stopped this check before it ran;
    * ``ERROR``   -- the collector supplied an explicitly classified failure;
    * ``UNKNOWN`` -- required evidence is missing, stale, incomplete or inadmissible;
    * ``FAIL``    -- admissible evidence contradicts the claim;
    * ``PASS``    -- admissible evidence satisfies it.

    A real FAIL is never softened into UNKNOWN because some *other* input was
    missing: the contradiction is reported on its own terms.
    """
    claim_id = str(claim.get("claimId"))
    proposition = claim.get("proposition", {})
    claim_type = str(proposition.get("claimType"))

    if blocked_by:
        return _result(claim_id, "NOT_RUN", "blocked by " + ", ".join(sorted(blocked_by)), [])

    errors = collector_errors or {}

    if claim_type not in matrix.get("byClaimType", {}):
        return _result(
            claim_id, "UNKNOWN",
            "claim type " + repr(claim_type) + " is unknown to the authority matrix; "
            "an unknown claim type cannot be resolved to PASS",
            [],
        )

    sufficiency = recompute_sufficiency(claim, evidence, matrix)
    expected = proposition.get("expectedValue")
    observed = observed_values.get(claim_id)

    # A contradiction is decided on its own admissible evidence, before any
    # complaint about other missing requirements.
    if observed is not None and expected is not None and observed != expected:
        satisfied_refs = [
            r for result in sufficiency["requirementResults"] for r in result["evidenceRefs"]
        ]
        if satisfied_refs:
            return _result(
                claim_id, "FAIL",
                "observed " + repr(observed) + " contradicts expected " + repr(expected),
                satisfied_refs, sufficiency,
            )

    if claim_id in errors:
        return _result(claim_id, "ERROR", "collector error: " + errors[claim_id], [])

    if not sufficiency["closed"]:
        unmet = [
            str(r["requirementId"])
            for r in sufficiency["requirementResults"]
            if r["mandatory"] and r["applicable"] and not r["satisfied"]
        ]
        return _result(
            claim_id, "UNKNOWN",
            "mandatory evidence not closed: " + ", ".join(sorted(unmet)),
            [], sufficiency,
        )

    if observed is None:
        return _result(
            claim_id, "UNKNOWN", "no observed value was recorded for this claim", [], sufficiency
        )

    if expected is None:
        return _result(
            claim_id, "UNKNOWN", "the proposition declares no expected value to compare", [], sufficiency
        )

    if observed == expected:
        refs = [r for result in sufficiency["requirementResults"] for r in result["evidenceRefs"]]
        return _result(
            claim_id, "PASS",
            "observed value matches the proposition under admissible evidence",
            refs, sufficiency,
        )
    return _result(
        claim_id, "FAIL",
        "observed " + repr(observed) + " contradicts expected " + repr(expected),
        [], sufficiency,
    )


def _result(
    claim_id: str,
    status: str,
    reason: str,
    evidence_refs: Sequence[str],
    sufficiency: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "claimId": claim_id,
        "status": status,
        "reason": reason,
        "evidenceRefs": sorted(set(evidence_refs)),
    }
    if sufficiency is not None:
        out["sufficiency"] = sufficiency
    return out
