"""Audit verdicts and pure promotion evaluation.

Two separations are structural rather than procedural here.

The **auditor** produces an AuditResult over a frozen bundle. It records which
claims it disagreed with the producer about, because an auditor that can never
disagree is not auditing anything.

The **promotion evaluator** is pure: it reads a frozen audit result and a
policy and returns a decision. It does not act. ``actuatorRole`` stays empty,
and :func:`apply_promotion` refuses to be called by the same role that issued
the decision -- a worker cannot promote its own candidate.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from continuity_ontology.canonical.profiles import digest_with

from .._boundary import AUDITOR_ROLE, COMMON_MODE_DEPENDENCIES

__all__ = [
    "PromotionError",
    "SelfPromotionRefused",
    "build_audit_result",
    "evaluate_promotion",
    "apply_promotion",
]

_STATUSES = ("PASS", "FAIL", "UNKNOWN", "ERROR", "NOT_RUN")


class PromotionError(ValueError):
    """Raised when a promotion cannot be evaluated or applied as asked."""


class SelfPromotionRefused(PromotionError):
    """Raised when the issuing role tries to act on its own decision."""


def build_audit_result(
    audit_id: str,
    frozen_bundle_digest: str,
    audit_input_manifest_digest: str,
    claim_results: Sequence[Mapping[str, Any]],
    producer_statuses: Mapping[str, str],
    auditor_implementation_digest: str,
    *,
    independence_level: str = "SEPARATE_IMPLEMENTATION",
    mandatory_claim_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble an AuditResult from recomputed claim results."""
    mandatory = set(mandatory_claim_ids) or {str(r["claimId"]) for r in claim_results}
    totals = {status: 0 for status in _STATUSES}
    disagreed: list[str] = []
    verifications: list[dict[str, Any]] = []

    for result in claim_results:
        claim_id = str(result["claimId"])
        status = str(result["status"])
        if claim_id in mandatory:
            totals[status] = totals.get(status, 0) + 1
        producer_status = producer_statuses.get(claim_id)
        if producer_status is not None and producer_status != status:
            disagreed.append(claim_id)
        verifications.append(
            {
                "recordType": "Verification",
                "claimId": claim_id,
                "mode": "RECOMPUTE",
                "status": status,
                "reason": result.get("reason", ""),
                "producerStatus": producer_status,
                "commonModeDependencies": [d["dependency"] for d in COMMON_MODE_DEPENDENCIES],
                "independenceLevel": independence_level,
            }
        )

    if totals["ERROR"]:
        verdict = "INDETERMINATE"
        rationale = str(totals["ERROR"]) + " mandatory claim(s) errored"
    elif totals["FAIL"]:
        verdict = "REJECT"
        rationale = str(totals["FAIL"]) + " mandatory claim(s) are contradicted"
    elif totals["UNKNOWN"] or totals["NOT_RUN"]:
        verdict = "INDETERMINATE"
        rationale = (
            str(totals["UNKNOWN"]) + " unknown and " + str(totals["NOT_RUN"])
            + " not-run mandatory claim(s); missing evidence is not approval"
        )
    elif totals["PASS"]:
        verdict = "APPROVE"
        rationale = "all mandatory claims independently recomputed to PASS"
    else:
        verdict = "INDETERMINATE"
        rationale = "no mandatory claims were evaluated"

    result = {
        "recordType": "AuditResult",
        "auditId": audit_id,
        "frozenBundleDigest": frozen_bundle_digest,
        "auditInputManifestDigest": audit_input_manifest_digest,
        "verifications": verifications,
        "verdict": verdict,
        "verdictRationale": rationale,
        "mandatoryTotals": totals,
        "disagreedWithProducer": sorted(disagreed),
        "auditorRole": AUDITOR_ROLE,
        "auditorImplementationDigest": auditor_implementation_digest,
        "commonModeDependencies": [dict(d) for d in COMMON_MODE_DEPENDENCIES],
    }
    result["resultDigest"] = digest_with("continuity.core.v2", result)
    return result


def evaluate_promotion(
    candidate_digest: str,
    audit_result: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    issuer_role: str,
    human_approval_refs: Sequence[str] = (),
    unresolved_conflicts: Sequence[str] = (),
) -> dict[str, Any]:
    """Pure policy evaluation over a frozen audit result. Performs no action."""
    reasons: list[str] = []

    if audit_result.get("frozenBundleDigest") is None:
        reasons.append("the audit result does not name the frozen bundle it evaluated")
    if audit_result.get("verdict") != "APPROVE":
        reasons.append(
            "audit verdict is " + str(audit_result.get("verdict"))
            + "; only APPROVE is eligible"
        )
    totals = audit_result.get("mandatoryTotals", {})
    if not totals or not any(totals.values()):
        reasons.append("mandatory claim observations are absent")
    for status in ("FAIL", "UNKNOWN", "ERROR", "NOT_RUN"):
        if totals.get(status):
            reasons.append(
                str(totals[status]) + " mandatory claim(s) are " + status
                + "; these cannot become PASS for promotion purposes"
            )
    if unresolved_conflicts:
        reasons.append(
            "unresolved conflict(s) still invalidate downstream acceptance: "
            + ", ".join(sorted(unresolved_conflicts))
        )
    required_approvals = policy.get("requiredHumanApprovals", [])
    missing_approvals = [a for a in required_approvals if a not in set(human_approval_refs)]
    if missing_approvals:
        reasons.append(
            "required human approval(s) absent: " + ", ".join(sorted(missing_approvals))
        )
    if policy.get("requireIndependentAudit", True):
        if audit_result.get("auditorRole") != AUDITOR_ROLE:
            reasons.append(
                "the audit was not produced by the independent auditor role"
            )

    decision = {
        "recordType": "PromotionDecision",
        "candidateDigest": candidate_digest,
        "auditResultDigest": audit_result.get("resultDigest"),
        "policyDigest": digest_with("continuity.core.v2", dict(policy)),
        "state": "INELIGIBLE" if reasons else "ELIGIBLE",
        "reasons": reasons or ["all promotion predicates satisfied over the frozen audit"],
        "issuerRole": issuer_role,
        "humanApprovalRefs": sorted(human_approval_refs),
    }
    # actuatorRole is deliberately absent: an evaluation has not acted.
    return decision


def apply_promotion(
    decision: Mapping[str, Any],
    *,
    actuator_role: str,
    actuator_authorization_digest: str,
) -> dict[str, Any]:
    """Record that a separately authorized actuator acted on a decision."""
    if decision.get("state") != "ELIGIBLE":
        raise PromotionError(
            "cannot act on a decision in state " + str(decision.get("state"))
        )
    if actuator_role == decision.get("issuerRole"):
        raise SelfPromotionRefused(
            "the role that issued this decision cannot also actuate it; promotion "
            "requires a separately authorized actuator"
        )
    if not actuator_authorization_digest:
        raise PromotionError("the actuator must present an authorization receipt")
    applied = dict(decision)
    applied["state"] = "PROMOTED"
    applied["actuatorRole"] = actuator_role
    applied["actuatorAuthorizationDigest"] = actuator_authorization_digest
    return applied
