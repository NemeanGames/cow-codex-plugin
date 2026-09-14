"""Mutation ledger, mutation-effect closure and bounded enumeration.

A mutation-effect claim is expensive to establish on purpose. It needs the
authorized operation, the declared intent, the pre-state, a contiguous ledger
range, the post-state, an independent provider readback, a *direct* ownership
and transaction binding, and set equality across the rollback closure. A
provider's ``success`` field and an image difference are both explicitly
insufficient, and the evaluator says so by name rather than returning a bare
FAIL.

Absence is equally deliberate. An absence claim requires a bounded scope, a
complete enumeration over exactly that scope, and a closure receipt. An empty
result from a query that failed, or from an exporter that truncated, proves
nothing about what exists.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with

__all__ = [
    "LedgerError",
    "MutationLedger",
    "evaluate_mutation_effect",
    "enumeration_closure",
    "evaluate_absence",
    "GENESIS_ENTRY_DIGEST",
]

GENESIS_ENTRY_DIGEST = "sha256:" + "0" * 64

#: Evidence kinds that can never establish a mutation effect on their own.
_INSUFFICIENT_FOR_MUTATION = {
    "visual_capture": "an image difference cannot establish a mutation effect",
    "provider_success_flag": "a provider's success field is not a readback",
    "log_line": "a log line is not an owned transaction",
}


class LedgerError(ValueError):
    """Raised when the mutation ledger is malformed."""


class MutationLedger:
    """Append-only, digest-chained record of authorized mutations."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def head_digest(self) -> str:
        if not self._entries:
            return GENESIS_ENTRY_DIGEST
        return digest_with("continuity.core.v2", self._entries[-1])

    def append(
        self,
        entry_id: str,
        *,
        operation_id: str,
        transaction_id: str,
        intent_id: str,
        ownership: Mapping[str, Any],
        pre_state_digest: str,
        post_state_digest: str,
        effect_description: str,
        readback_ref: str | None = None,
    ) -> dict[str, Any]:
        if ownership.get("transactionId") != transaction_id:
            raise LedgerError(
                "ownership assertion binds transaction " + str(ownership.get("transactionId"))
                + " but the entry is for " + transaction_id
            )
        entry: dict[str, Any] = {
            "recordType": "MutationLedgerEntry",
            "entryId": entry_id,
            "sequence": len(self._entries),
            "priorEntryDigest": self.head_digest(),
            "operationId": operation_id,
            "transactionId": transaction_id,
            "intentId": intent_id,
            "ownership": dict(ownership),
            "preStateDigest": pre_state_digest,
            "postStateDigest": post_state_digest,
            "effectDescription": effect_description,
        }
        if readback_ref:
            entry["readbackRef"] = readback_ref
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._entries)

    def range_for(self, operation_id: str) -> tuple[dict[str, Any], ...]:
        return tuple(e for e in self._entries if e["operationId"] == operation_id)

    def verify_chain(self) -> None:
        prior = GENESIS_ENTRY_DIGEST
        for index, entry in enumerate(self._entries):
            if entry["sequence"] != index:
                raise LedgerError("ledger entry " + entry["entryId"] + " is out of sequence")
            if entry["priorEntryDigest"] != prior:
                raise LedgerError("ledger entry " + entry["entryId"] + " breaks the chain")
            prior = digest_with("continuity.core.v2", entry)

    def __len__(self) -> int:
        return len(self._entries)


def evaluate_mutation_effect(
    *,
    authorized_operation: Mapping[str, Any] | None,
    intent: Mapping[str, Any] | None,
    ledger_entries: Sequence[Mapping[str, Any]],
    readbacks: Sequence[Mapping[str, Any]],
    rollback_set: Sequence[str],
    offered_evidence_kinds: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate one mutation-effect claim to a five-state result.

    Returns ``UNKNOWN`` when a required element is missing, ``FAIL`` when the
    sets disagree, and ``PASS`` only when every element is present and the
    intended, ledgered, confirmed and rollback sets are equal.
    """
    inadmissible = [
        _INSUFFICIENT_FOR_MUTATION[kind]
        for kind in offered_evidence_kinds
        if kind in _INSUFFICIENT_FOR_MUTATION
    ]

    missing: list[str] = []
    if authorized_operation is None:
        missing.append("authorized operation")
    if intent is None:
        missing.append("mutation intent")
    if not ledger_entries:
        missing.append("mutation ledger entries")
    if not readbacks:
        missing.append("provider readback")

    contradictions: list[str] = []
    def bind(label, values):
        present = [v for v in values if v is not None and v != ""]
        if len(present) != len(values):
            missing.append(label)
        if present and any(v != present[0] for v in present[1:]):
            contradictions.append(label + " disagrees")

    operation = authorized_operation if authorized_operation is not None else {}
    declared = intent if intent is not None else {}
    bind("operation identity", [operation.get("operationId")]
         + [e.get("operationId") for e in ledger_entries]
         + [r.get("operationId") for r in readbacks])
    bind("intent identity", [declared.get("intentId")]
         + [e.get("intentId") for e in ledger_entries])
    bind("intent pre-state", [declared.get("preStateDigest")]
         + [e.get("preStateDigest") for e in ledger_entries])
    bind("transaction identity", [e.get("transactionId") for e in ledger_entries]
         + [e.get("ownership", {}).get("transactionId") for e in ledger_entries])
    # Optional cross-references, when supplied, cannot contradict the primary binding.
    for key, expected in (("operationId", operation.get("operationId")),
                          ("intentId", declared.get("intentId")),
                          ("transactionId", ledger_entries[0].get("transactionId") if ledger_entries else None)):
        for record in [operation, declared, *readbacks,
                       *(e.get("ownership", {}) for e in ledger_entries)]:
            if key in record:
                bind(key, [expected, record[key]])
    if contradictions:
        return {"status": "FAIL", "reason": "; ".join(contradictions),
                "missing": missing, "inadmissibleOffers": inadmissible, "closure": None}

    if missing:
        reason = "missing required mutation evidence: " + ", ".join(missing)
        if inadmissible:
            reason += ". Offered instead: " + "; ".join(inadmissible)
        return {
            "status": "UNKNOWN",
            "reason": reason,
            "missing": missing,
            "inadmissibleOffers": inadmissible,
            "closure": None,
        }

    ownerships = [e["ownership"] for e in ledger_entries]
    indirect = [
        o for o in ownerships if o.get("directness") != "DIRECTLY_OWNED"
    ]
    if indirect:
        return {
            "status": "FAIL",
            "reason": (
                "mutation effect requires a directly owned transaction; "
                + str(len(indirect)) + " ledger entr(ies) assert "
                + ", ".join(sorted({str(o.get("directness")) for o in indirect}))
            ),
            "missing": [],
            "inadmissibleOffers": inadmissible,
            "closure": None,
        }

    sequences = [e["sequence"] for e in ledger_entries]
    if sequences != list(range(min(sequences), min(sequences) + len(sequences))):
        return {
            "status": "FAIL",
            "reason": "ledger range for this operation is not contiguous",
            "missing": [],
            "inadmissibleOffers": inadmissible,
            "closure": None,
        }

    intended = set(intent.get("declaredEffects", []))
    ledgered = {e["effectDescription"] for e in ledger_entries}
    confirmed = {
        r["operationId"] + ":" + str(r.get("observedStateDigest"))
        for r in readbacks
        if r.get("matchesExpectedPostState")
    }
    confirmed_effects = {
        e["effectDescription"]
        for e in ledger_entries
        if any(
            r.get("matchesExpectedPostState")
            and r.get("operationId") == e["operationId"]
            and r.get("observedStateDigest") == e["postStateDigest"]
            for r in readbacks
        )
    }
    rollback = set(rollback_set)

    closure = {
        "recordType": "MutationSetClosureReceipt",
        "operationId": authorized_operation.get("operationId"),
        "intendedEffects": sorted(intended),
        "ledgeredEffects": sorted(ledgered),
        "readbackConfirmedEffects": sorted(confirmed_effects),
        "rollbackSet": sorted(rollback),
        "setsEqual": intended == ledgered == confirmed_effects == rollback,
        "discrepancies": [],
    }
    discrepancies: list[str] = []
    if intended != ledgered:
        discrepancies.append("intended effects differ from ledgered effects")
    if ledgered != confirmed_effects:
        discrepancies.append("ledgered effects are not all confirmed by readback")
    if ledgered != rollback:
        discrepancies.append("rollback set does not cover exactly the ledgered effects")
    closure["discrepancies"] = discrepancies
    closure["setsEqual"] = not discrepancies

    if discrepancies:
        return {
            "status": "FAIL",
            "reason": "mutation set closure failed: " + "; ".join(discrepancies),
            "missing": [],
            "inadmissibleOffers": inadmissible,
            "closure": closure,
        }
    return {
        "status": "PASS",
        "reason": "authorized, intended, ledgered, read back and rollback-closed",
        "missing": [],
        "inadmissibleOffers": inadmissible,
        "closure": closure,
    }


# ---------------------------------------------------------------------------
# Enumeration closure and absence
# ---------------------------------------------------------------------------

def enumeration_closure(
    scope: Mapping[str, Any],
    enumerated_members: Sequence[str],
    witness_refs: Sequence[str],
    *,
    collector_error: str | None = None,
    truncated: bool = False,
) -> dict[str, Any]:
    """Build an enumeration closure receipt over a bounded scope."""
    observed = len(set(enumerated_members))
    expected = scope.get("expectedMemberCount")
    incomplete_reason = None
    complete = True

    if collector_error:
        complete = False
        incomplete_reason = "collector error: " + collector_error
    elif truncated:
        complete = False
        incomplete_reason = "the exporter truncated its output"
    elif not scope.get("enumerationComplete"):
        complete = False
        incomplete_reason = "the scope does not declare a complete enumeration"
    elif expected is not None and observed != expected:
        complete = False
        incomplete_reason = (
            "enumerated " + str(observed) + " member(s) against an expected " + str(expected)
        )
    elif not witness_refs:
        complete = False
        incomplete_reason = (
            "no witness is recorded for the enumeration; a closure nobody can check "
            "cannot stand behind an absence claim"
        )

    return {
        "recordType": "ClosureReceipt",
        "closureKind": "ENUMERATION",
        "scope": dict(scope),
        "enumeratedMembers": sorted(set(enumerated_members)),
        "expectedCount": expected,
        "observedCount": observed,
        "complete": complete,
        "incompleteReason": incomplete_reason,
        "witnessRefs": sorted(witness_refs),
    }


def evaluate_absence(subject: str, closure: Mapping[str, Any]) -> dict[str, Any]:
    """Decide whether a bounded scope supports an absence claim."""
    if subject in (closure.get("enumeratedMembers") or []):
        return {"status": "FAIL", "subject": subject,
                "reason": "the subject is present in the enumerated scope"}
    if not closure.get("complete"):
        return {
            "status": "UNKNOWN",
            "subject": subject,
            "reason": (
                "absence needs a complete enumeration over a bounded scope; "
                + str(closure.get("incompleteReason", "the enumeration is incomplete"))
                + ". An empty or failed retrieval does not establish that the subject is absent."
            ),
        }
    if closure.get("enumeratedMembers") is None or closure.get("observedCount") is None:
        return {"status": "UNKNOWN", "subject": subject, "reason": "enumeration evidence is missing"}
    return {
        "status": "PASS",
        "subject": subject,
        "reason": (
            "the scope enumerated " + str(closure["observedCount"])
            + " member(s) completely and the subject is not among them"
        ),
    }
