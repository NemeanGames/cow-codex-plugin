"""Claim compilation, sealing, delta replay and evidence closure.

The producer compiles claims and seals a bundle. That establishes *structural
readiness* and nothing else: no function in this module returns a verification
verdict, and the audit result type is written only by ``continuity_audit``.

Sealing order matters and is enforced by construction. Producer evidence is
sealed first; the audit references that frozen bundle; promotion references the
audit; a checkpoint references accepted state; a view references the checkpoint
or audit. Nothing rewrites an earlier sealed object to point at a descendant
that already depends on it, so there is no cycle to resolve.

Delta resolution is bounded. A chain deeper than the configured limit, a
missing parent, a cycle, a dropped mandatory claim or two revisions of one
claim in the same delta are all rejections, not warnings.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with

__all__ = [
    "ClaimError",
    "BundleClosureError",
    "DeltaChainError",
    "SealOrderError",
    "compile_claim",
    "evidence_sufficiency",
    "seal_bundle",
    "compile_delta",
    "resolve_delta_chain",
    "materialize",
    "verify_seal_dag",
    "ConflictRegister",
]

_MAX_DELTA_DEPTH = 32


class ClaimError(ValueError):
    """Base class for claim-compilation failures."""


class BundleClosureError(ClaimError):
    """A bundle is missing members or evidence it declares."""


class DeltaChainError(ClaimError):
    """A delta chain cannot be resolved."""


class SealOrderError(ClaimError):
    """A seal would create a circular dependency."""


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def evidence_sufficiency(
    requirements: Sequence[Mapping[str, Any]],
    available_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate whether the required evidence for a claim is present.

    ``available_evidence`` maps content digest to an evidence record. A
    requirement is satisfied only by evidence of the declared kind whose
    admissibility is ADMISSIBLE; a requirement marked not applicable is
    excluded from the denominator rather than counted as satisfied.
    """
    results: list[dict[str, Any]] = []
    mandatory_applicable = 0
    mandatory_satisfied = 0

    for requirement in requirements:
        applicable = bool(requirement.get("applicable", True))
        mandatory = bool(requirement.get("mandatory", False))
        kind = requirement.get("evidenceKind")
        matched: list[str] = []
        reason = ""
        for digest, record in sorted(available_evidence.items()):
            if record.get("evidenceKind") != kind:
                continue
            if record.get("admissibility") != "ADMISSIBLE":
                reason = "evidence of the right kind is present but " + str(record.get("admissibility"))
                continue
            if not requirement.get("syntheticAcceptable", True) and record.get("synthetic"):
                reason = "only synthetic evidence is available and this requirement forbids it"
                continue
            matched.append(digest)
        satisfied = bool(matched)
        if not satisfied and not reason:
            reason = "no admissible evidence of kind " + str(kind)
        if satisfied:
            reason = "satisfied by " + str(len(matched)) + " admissible item(s)"
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
                "reason": reason,
                "evidenceRefs": matched,
            }
        )

    return {
        "recordType": "EvidenceSufficiencyReceipt",
        "requirementResults": results,
        "mandatoryApplicable": mandatory_applicable,
        "mandatorySatisfied": mandatory_satisfied,
        "closed": mandatory_applicable == mandatory_satisfied,
    }


def compile_claim(
    claim_id: str,
    proposition: Mapping[str, Any],
    producer_assertion: Mapping[str, Any],
    requirements: Sequence[Mapping[str, Any]],
    available_evidence: Mapping[str, Mapping[str, Any]],
    *,
    mandatory: bool = True,
    freshness_policy_ref: str | None = None,
) -> dict[str, Any]:
    """Build one producer claim.

    The producer's own status travels inside ``producerAssertion`` and never
    escapes into a top-level verification field. There is no parameter here
    that would let a producer record a verified result.
    """
    if "claimType" not in proposition:
        raise ClaimError("a proposition must name its claim type")
    if "scope" not in proposition:
        raise ClaimError("a proposition must carry a bounded scope")
    if "producerStatus" not in producer_assertion:
        raise ClaimError("a producer assertion must carry the producer's own status")

    requirement_ids = [r["requirementId"] for r in requirements]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ClaimError("duplicate requirement IDs")
    sufficiency = evidence_sufficiency(requirements, available_evidence)
    claim = {
        "recordType": "Claim",
        "claimId": claim_id,
        "proposition": dict(proposition),
        "producerAssertion": dict(producer_assertion),
        "requiredEvidence": [dict(r) for r in requirements],
        "sufficiency": sufficiency,
        "lifecycle": "DRAFT",
        "mandatory": mandatory,
    }
    if freshness_policy_ref:
        claim["freshnessPolicyRef"] = freshness_policy_ref
    return claim


def _revision(claim: Mapping[str, Any], number: int, parent_digest: str | None, reason: str) -> dict[str, Any]:
    sealed = dict(claim)
    sealed["sufficiency"] = {k: v for k, v in claim["sufficiency"].items() if k != "recordType"}
    sealed["lifecycle"] = "SEALED"
    revision = {
        "recordType": "ClaimRevision",
        "claimId": claim["claimId"],
        "revisionNumber": number,
        "claim": sealed,
        "changeReason": reason,
    }
    if parent_digest:
        revision["parentRevisionDigest"] = parent_digest
    revision["_digest"] = digest_with("continuity.core.v2", revision)
    return revision


# ---------------------------------------------------------------------------
# Bundles
# ---------------------------------------------------------------------------

def seal_bundle(
    bundle_id: str,
    candidate_digest: str,
    claims: Sequence[Mapping[str, Any]],
    *,
    sealed_at: str | None = None,
    require_evidence_closure: bool = True,
) -> dict[str, Any]:
    """Freeze a producer bundle.

    A mandatory claim whose evidence closure is incomplete blocks the seal.
    That is the point at which "we have not gathered the evidence" is caught,
    rather than later when it would be indistinguishable from "the evidence
    contradicts the claim".
    """
    seen: set[str] = set()
    members: list[dict[str, Any]] = []
    revisions: dict[str, dict[str, Any]] = {}
    unclosed: list[str] = []

    for claim in claims:
        claim_id = claim["claimId"]
        if claim_id in seen:
            raise BundleClosureError("claim " + repr(claim_id) + " appears twice in one bundle")
        seen.add(claim_id)
        if require_evidence_closure and claim.get("mandatory") and not claim["sufficiency"]["closed"]:
            unclosed.append(claim_id)
        revision = _revision(claim, 1, None, "initial seal")
        revisions[claim_id] = revision
        members.append(
            {
                "claimId": claim_id,
                "revisionDigest": revision["_digest"],
                "mandatory": bool(claim.get("mandatory")),
            }
        )

    if unclosed:
        raise BundleClosureError(
            "mandatory claims without complete evidence closure: " + ", ".join(sorted(unclosed))
        )

    members.sort(key=lambda m: m["claimId"])
    bundle = {
        "recordType": "ClaimBundle",
        "bundleId": bundle_id,
        "candidateDigest": candidate_digest,
        "memberIndex": members,
        "lifecycle": "SEALED",
    }
    bundle["resolvedStateDigest"] = digest_with(
        "continuity.core.v2", {"members": members, "candidateDigest": candidate_digest}
    )
    if sealed_at:
        bundle["sealedAt"] = sealed_at
    bundle["_revisions"] = revisions
    return bundle


def compile_delta(
    delta_id: str,
    parent_bundle: Mapping[str, Any],
    changed_claims: Sequence[Mapping[str, Any]],
    removed_claim_ids: Sequence[str] = (),
    new_evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a delta over a sealed parent.

    Only changed revisions and genuinely new evidence references travel.
    Unchanged evidence is referenced through the parent, not recopied.
    """
    parent_members = {m["claimId"]: m for m in parent_bundle["memberIndex"]}
    parent_digest = digest_with(
        "continuity.core.v2",
        {"members": parent_bundle["memberIndex"], "candidateDigest": parent_bundle["candidateDigest"]},
    )
    if parent_digest != parent_bundle["resolvedStateDigest"]:
        raise DeltaChainError("parent bundle does not match its own resolved-state digest")

    dropped_mandatory = [
        cid for cid in removed_claim_ids if parent_members.get(cid, {}).get("mandatory")
    ]
    if dropped_mandatory:
        raise DeltaChainError(
            "a delta cannot drop mandatory claims: " + ", ".join(sorted(dropped_mandatory))
        )

    seen: set[str] = set()
    changed: list[dict[str, Any]] = []
    revisions: dict[str, dict[str, Any]] = {}
    for claim in changed_claims:
        claim_id = claim["claimId"]
        if claim_id in seen:
            raise DeltaChainError(
                "claim " + repr(claim_id) + " has two revisions in one delta; "
                "a delta carries at most one revision per claim"
            )
        seen.add(claim_id)
        parent_member = parent_members.get(claim_id)
        number = 2 if parent_member else 1
        revision = _revision(
            claim, number, parent_member["revisionDigest"] if parent_member else None, "delta revision"
        )
        revisions[claim_id] = revision
        changed.append({"claimId": claim_id, "revisionDigest": revision["_digest"]})

    overlap = seen & set(removed_claim_ids)
    if overlap:
        raise DeltaChainError(
            "claims both revised and removed in one delta: " + ", ".join(sorted(overlap))
        )

    changed.sort(key=lambda c: c["claimId"])
    delta = {
        "recordType": "ClaimBundleDelta",
        "deltaId": delta_id,
        "parentBundleDigest": parent_bundle["resolvedStateDigest"],
        "changedRevisions": changed,
        "removedClaimIds": sorted(removed_claim_ids),
        "newEvidenceRefs": sorted(new_evidence_refs),
        "depth": int(parent_bundle.get("_depth", 0)) + 1,
    }
    resolved = _apply(parent_bundle["memberIndex"], delta, revisions)
    delta["resolvedStateDigest"] = digest_with(
        "continuity.core.v2",
        {"members": resolved, "candidateDigest": parent_bundle["candidateDigest"]},
    )
    delta["_revisions"] = revisions
    return delta


def _apply(
    members: Sequence[Mapping[str, Any]],
    delta: Mapping[str, Any],
    revisions: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {m["claimId"]: dict(m) for m in members}
    for removed in delta["removedClaimIds"]:
        by_id.pop(removed, None)
    for change in delta["changedRevisions"]:
        claim_id = change["claimId"]
        mandatory = by_id.get(claim_id, {}).get(
            "mandatory", bool(revisions.get(claim_id, {}).get("claim", {}).get("mandatory"))
        )
        by_id[claim_id] = {
            "claimId": claim_id,
            "revisionDigest": change["revisionDigest"],
            "mandatory": mandatory,
        }
    return [by_id[k] for k in sorted(by_id)]


def resolve_delta_chain(
    base_bundle: Mapping[str, Any],
    deltas: Sequence[Mapping[str, Any]],
    max_depth: int = _MAX_DELTA_DEPTH,
) -> dict[str, Any]:
    """Replay a chain of deltas onto a sealed base bundle.

    Rejects a missing parent, a cycle, an over-deep chain and any resolved
    state that disagrees with the digest a delta recorded for itself.
    """
    if len(deltas) > max_depth:
        raise DeltaChainError(
            "delta chain depth " + str(len(deltas)) + " exceeds the bound of " + str(max_depth)
        )
    members = [dict(m) for m in base_bundle["memberIndex"]]
    current_digest = base_bundle["resolvedStateDigest"]
    seen_digests = {current_digest}

    for index, delta in enumerate(deltas):
        if delta["parentBundleDigest"] != current_digest:
            raise DeltaChainError(
                "delta " + str(delta["deltaId"]) + " at position " + str(index)
                + " names a parent that is not the current resolved state"
            )
        revisions = delta.get("_revisions", {})
        members = _apply(members, delta, revisions)
        current_digest = digest_with(
            "continuity.core.v2",
            {"members": members, "candidateDigest": base_bundle["candidateDigest"]},
        )
        if current_digest != delta["resolvedStateDigest"]:
            raise DeltaChainError(
                "delta " + str(delta["deltaId"]) + " resolves to a state that disagrees with "
                "the digest it recorded"
            )
        if current_digest in seen_digests and index > 0:
            raise DeltaChainError("delta chain revisits a previous resolved state (cycle)")
        seen_digests.add(current_digest)

    return {
        "recordType": "ClaimBundle",
        "bundleId": base_bundle["bundleId"],
        "candidateDigest": base_bundle["candidateDigest"],
        "memberIndex": members,
        "lifecycle": "MATERIALIZED",
        "resolvedStateDigest": current_digest,
    }


def materialize(
    base_bundle: Mapping[str, Any],
    deltas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve a chain and assert it equals a directly built full bundle."""
    resolved = resolve_delta_chain(base_bundle, deltas)
    direct = digest_with(
        "continuity.core.v2",
        {"members": resolved["memberIndex"], "candidateDigest": base_bundle["candidateDigest"]},
    )
    if direct != resolved["resolvedStateDigest"]:
        raise DeltaChainError("materialized state does not equal the resolved delta state")
    return resolved


# ---------------------------------------------------------------------------
# Seal ordering
# ---------------------------------------------------------------------------

#: Permitted seal edges: a later artifact may reference an earlier one.
_SEAL_ORDER = ("evidence", "claim_bundle", "audit", "promotion", "checkpoint", "view")


def verify_seal_dag(edges: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Check that every reference points backwards in the seal order.

    ``edges`` are ``(referrer, referenced)`` pairs over the stage names above.
    A view may reference an audit; an audit may not reference the view that
    displays it, and nothing may reference itself.
    """
    rank = {name: index for index, name in enumerate(_SEAL_ORDER)}
    violations: list[dict[str, str]] = []
    for referrer, referenced in edges:
        if referrer not in rank or referenced not in rank:
            violations.append(
                {"referrer": referrer, "referenced": referenced, "reason": "unknown seal stage"}
            )
            continue
        if referrer == referenced:
            violations.append(
                {"referrer": referrer, "referenced": referenced, "reason": "self-dependent digest"}
            )
        elif rank[referrer] < rank[referenced]:
            violations.append(
                {
                    "referrer": referrer,
                    "referenced": referenced,
                    "reason": "an earlier seal cannot reference a later descendant that depends on it",
                }
            )
    return {
        "sealOrder": list(_SEAL_ORDER),
        "acyclic": not violations,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

class ConflictRegister:
    """Conflicts stay visible until an authorized adjudication cites evidence."""

    def __init__(self, *, evidence: Mapping[str, Any] | None = None,
                 policies: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._evidence = deepcopy(dict(evidence or {}))
        self._policies = deepcopy(dict(policies or {}))
        self._conflicts: dict[str, dict[str, Any]] = {}
        self._adjudications: dict[str, dict[str, Any]] = {}

    def record(
        self,
        conflict_id: str,
        claim_ids: Sequence[str],
        conflicting_evidence: Sequence[str],
        description: str,
        invalidates_downstream: Sequence[str] = (),
    ) -> dict[str, Any]:
        conflict = {
            "recordType": "ConflictSet",
            "conflictId": conflict_id,
            "claimIds": sorted(claim_ids),
            "conflictingEvidence": sorted(conflicting_evidence),
            "description": description,
            "disposition": "UNRESOLVED",
            "invalidatesDownstream": sorted(invalidates_downstream),
        }
        existing = self._conflicts.get(conflict_id)
        if existing is not None:
            original = dict(existing, disposition="UNRESOLVED")
            if original != conflict:
                raise ClaimError("conflict ID already records different content: " + conflict_id)
            return deepcopy(existing)
        self._conflicts[conflict_id] = conflict
        return deepcopy(conflict)

    def adjudicate(
        self,
        conflict_id: str,
        disposition: str,
        cited_evidence: Sequence[str],
        cited_policy: str,
        authorized_by_role: str,
        rationale: str,
    ) -> dict[str, Any]:
        if conflict_id not in self._conflicts:
            raise ClaimError("no conflict named " + repr(conflict_id))
        if disposition == "UNRESOLVED":
            raise ClaimError("an adjudication must reach a disposition")
        if not cited_evidence:
            raise ClaimError(
                "an adjudication must cite the conflicting evidence it resolves; "
                "a bare decision does not close a conflict"
            )
        if disposition not in {"ADJUDICATED_ACCEPT", "ADJUDICATED_REJECT", "ADJUDICATED_SPLIT_SCOPE"}:
            raise ClaimError("invalid conflict disposition: " + disposition)
        if any(ref not in self._evidence or self._evidence[ref] is None for ref in cited_evidence):
            raise ClaimError("cited evidence does not resolve")
        if not set(cited_evidence).issubset(self._conflicts[conflict_id]["conflictingEvidence"]):
            raise ClaimError("cited evidence does not belong to this conflict")
        policy = self._policies.get(cited_policy)
        if policy is None or authorized_by_role not in policy.get("authorizedAdjudicatorRoles", []):
            raise ClaimError("adjudicating role is not authorized by the cited policy")
        receipt = {
            "recordType": "AdjudicationReceipt",
            "conflictId": conflict_id,
            "disposition": disposition,
            "citedEvidence": sorted(cited_evidence),
            "citedPolicy": cited_policy,
            "authorizedByRole": authorized_by_role,
            "rationale": rationale,
        }
        self._conflicts[conflict_id]["disposition"] = disposition
        self._adjudications[conflict_id] = receipt
        return receipt

    def unresolved(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            deepcopy(self._conflicts[k]) for k in sorted(self._conflicts)
            if self._conflicts[k]["disposition"] == "UNRESOLVED"
        )

    def blocks(self, claim_id: str) -> tuple[str, ...]:
        """Conflict ids that still block a claim's downstream acceptance."""
        return tuple(
            c["conflictId"]
            for c in self.unresolved()
            if claim_id in c["claimIds"] or claim_id in c["invalidatesDownstream"]
        )

    def conflicts(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._conflicts[k]) for k in sorted(self._conflicts))
