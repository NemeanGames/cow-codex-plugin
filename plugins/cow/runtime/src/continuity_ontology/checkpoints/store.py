"""Durable checkpoints, resume and interrupted-operation reconciliation.

A checkpoint exists so a replacement agent can continue without reconstructing
the project from a conversation. It therefore carries the admitted source
versions, plan and contract identities, accepted decisions, unresolved claims,
artifact references, the sealed event position, the required-fact inventory and
the next legal actions.

What it deliberately does *not* carry is authority. A saved PID, an editor
connection, an authorization that has expired, a prior visibility observation:
all of these are recorded as historical notes with ``carriesAuthority`` false,
and resume refreshes them rather than trusting them.

An interruption that may already have produced a side effect but has no receipt
is an *open operation*. Resume reports it as requiring reconciliation. A missing
receipt is not permission to repeat the effect.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cityqa.engine.atomic import write_bytes
from ..validate.records import validate_persisted

from ..canonical.profiles import digest_with

__all__ = [
    "CheckpointError",
    "UncommittedCheckpoint",
    "ResumeBlocked",
    "CheckpointStore",
    "ResumeReport",
    "reconcile_open_operation",
]


class CheckpointError(ValueError):
    """Base class for checkpoint failures."""


class UncommittedCheckpoint(CheckpointError):
    """Raised when a draft is treated as a committed checkpoint."""


class ResumeBlocked(CheckpointError):
    """Raised when resume cannot legally proceed."""


class ResumeReport:
    """The result of attempting to resume from a committed checkpoint."""

    __slots__ = (
        "checkpoint_id",
        "resumable",
        "blockers",
        "restored_facts",
        "missing_facts",
        "refresh_required",
        "open_operations",
        "next_legal_actions",
        "tail_events",
        "restored_values",
    )

    def __init__(
        self,
        checkpoint_id: str,
        resumable: bool,
        blockers: Sequence[str],
        restored_facts: Sequence[str],
        missing_facts: Sequence[Mapping[str, Any]],
        refresh_required: Sequence[Mapping[str, Any]],
        open_operations: Sequence[Mapping[str, Any]],
        next_legal_actions: Sequence[str],
        tail_events: int,
        restored_values: Mapping[str, Any] | None = None,
    ) -> None:
        self.checkpoint_id = checkpoint_id
        self.resumable = resumable
        self.blockers = list(blockers)
        self.restored_facts = list(restored_facts)
        self.missing_facts = [dict(f) for f in missing_facts]
        self.refresh_required = [dict(b) for b in refresh_required]
        self.open_operations = [dict(o) for o in open_operations]
        self.next_legal_actions = list(next_legal_actions)
        self.tail_events = tail_events
        self.restored_values = dict(restored_values or {})

    def retention(self) -> dict[str, Any]:
        """Continuity retention over the frozen required-fact set."""
        total = len(self.restored_facts) + len(self.missing_facts)
        if total == 0:
            return {"availability": "NOT_APPLICABLE", "value": None, "unavailableReason": "no required facts declared"}
        return {
            "availability": "AVAILABLE",
            "value": len(self.restored_facts) / total,
            "restored": len(self.restored_facts),
            "required": total,
            "unit": "fraction",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "checkpointId": self.checkpoint_id,
            "resumable": self.resumable,
            "blockers": self.blockers,
            "restoredFacts": self.restored_facts,
            "restoredFactValues": self.restored_values,
            "missingFacts": self.missing_facts,
            "refreshRequired": self.refresh_required,
            "openOperations": self.open_operations,
            "nextLegalActions": self.next_legal_actions,
            "tailEventsAfterSeal": self.tail_events,
            "continuityRetention": self.retention(),
        }

    def __bool__(self) -> bool:
        return self.resumable


class CheckpointStore:
    """Commits checkpoints and resumes from them in a fresh process."""

    def __init__(self, root: str | os.PathLike[str], *, validate_records: bool = False) -> None:
        self.root = Path(root)
        self.validate_records = validate_records
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, checkpoint_id: str) -> Path:
        safe = checkpoint_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.root / (safe + ".checkpoint.json")

    # -- commit ------------------------------------------------------------

    def commit(
        self,
        checkpoint_id: str,
        *,
        outcome_id: str,
        snapshot: Mapping[str, Any],
        last_sealed_event_seq: int,
        last_sealed_event_digest: str,
        accepted_decisions: Sequence[Mapping[str, Any]],
        unresolved_claims: Sequence[str],
        open_operations: Sequence[Mapping[str, Any]],
        next_legal_actions: Sequence[str],
        recovery_policy_ref: str,
        closure_receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Write a committed checkpoint atomically.

        A checkpoint is only visible once it is complete and validated; a
        partial write leaves the previous committed state in place.
        """
        if not closure_receipt.get("complete"):
            raise UncommittedCheckpoint(
                "a checkpoint requires a complete state-closure receipt; "
                + str(closure_receipt.get("incompleteReason", "closure is incomplete"))
            )
        for binding in snapshot.get("ephemeralBindings", []):
            if binding.get("carriesAuthority"):
                raise CheckpointError(
                    "ephemeral binding " + str(binding.get("bindingKind"))
                    + " claims continuing authority; a saved handle is a historical note, not a grant"
                )
        for operation in open_operations:
            if operation.get("sideEffectPossible") is None:
                raise CheckpointError(
                    "open operation " + str(operation.get("operationId"))
                    + " does not declare sideEffectPossible; a checkpoint cannot carry an "
                    "operation whose retry safety is unknown"
                )
        record: dict[str, Any] = {
            "schemaVersion": "2.0.0",
            "recordType": "Checkpoint",
            "logicalId": checkpoint_id,
            "hashProfile": "continuity.core.v2",
            "outcome": outcome_id,
            "snapshot": dict(snapshot),
            "committed": True,
            "closureReceipt": dict(closure_receipt),
            "lastSealedEventSeq": int(last_sealed_event_seq),
            "lastSealedEventDigest": last_sealed_event_digest,
            "acceptedDecisions": [dict(d) for d in accepted_decisions],
            "unresolvedClaims": list(unresolved_claims),
            "openOperations": [dict(o) for o in open_operations],
            "nextLegalActions": list(next_legal_actions),
            "recoveryPolicyRef": recovery_policy_ref,
        }
        record["revisionId"] = digest_with("continuity.core.v2", record)
        if self.validate_records:
            validate_persisted(record)
        payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
        write_bytes(self._path(checkpoint_id), payload)
        return record

    def load(self, checkpoint_id: str) -> dict[str, Any]:
        path = self._path(checkpoint_id)
        if not path.exists():
            raise CheckpointError("no committed checkpoint named " + repr(checkpoint_id))
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("committed"):
            raise UncommittedCheckpoint(repr(checkpoint_id) + " is a draft, not a committed checkpoint")
        stored = record.pop("revisionId", None)
        recomputed = digest_with("continuity.core.v2", record)
        record["revisionId"] = stored
        if stored != recomputed:
            raise CheckpointError(
                "checkpoint " + repr(checkpoint_id) + " does not match its recorded revision digest"
            )
        return record

    # -- resume ------------------------------------------------------------

    def resume(
        self,
        checkpoint_id: str,
        *,
        observed_environment: Mapping[str, Any] | None = None,
        event_tail: Sequence[Mapping[str, Any]] = (),
        now: str | None = None,
    ) -> ResumeReport:
        """Attempt to resume. Nothing here reads a conversation transcript.

        Blockers are reported rather than worked around: a missing required
        fact, an expired authorization, an unreconciled open operation and a
        stale ephemeral binding each stop resume with a named reason.
        """
        record = self.load(checkpoint_id)
        snapshot = record["snapshot"]
        blockers: list[str] = []
        restored: list[str] = []
        restored_values: dict[str, Any] = {}
        missing: list[dict[str, Any]] = []

        for fact in snapshot.get("requiredFacts", []):
            if fact.get("present"):
                restored.append(str(fact.get("factId")))
                restored_values[str(fact.get("factId"))] = fact.get("value")
            else:
                missing.append(
                    {
                        "factId": fact.get("factId"),
                        "missingReason": fact.get("missingReason", "not recorded"),
                    }
                )
        if missing:
            blockers.append(
                "required facts missing from the snapshot: "
                + ", ".join(sorted(str(m["factId"]) for m in missing))
            )

        refresh: list[dict[str, Any]] = []
        for binding in snapshot.get("ephemeralBindings", []):
            if binding.get("carriesAuthority"):
                blockers.append(
                    "ephemeral binding " + str(binding.get("bindingKind")) + " claims authority"
                )
            if binding.get("refreshRequiredOnResume"):
                kind = str(binding.get("bindingKind"))
                observed = (observed_environment or {}).get(kind)
                entry = {
                    "bindingKind": kind,
                    "recordedValue": binding.get("recordedValue"),
                    "observedValue": observed,
                    "refreshed": observed is not None,
                }
                if observed is None:
                    blockers.append(
                        "ephemeral binding " + kind + " requires a fresh observation on resume "
                        "and none was supplied"
                    )
                elif observed != binding.get("recordedValue"):
                    entry["changed"] = True
                refresh.append(entry)

        open_ops: list[dict[str, Any]] = []
        for operation in record.get("openOperations", []):
            disposition = reconcile_open_operation(operation)
            open_ops.append(disposition)
            if disposition["requiresReconciliation"]:
                blockers.append(
                    "open operation " + str(operation.get("operationId"))
                    + " may have produced a side effect without a receipt; reconcile before acting"
                )

        tail = [e for e in event_tail if int(e.get("sequence", -1)) > int(record["lastSealedEventSeq"])]
        if tail:
            blockers.append(
                str(len(tail)) + " event(s) follow the sealed position and must be verified "
                "before the tail is treated as committed"
            )

        return ResumeReport(
            checkpoint_id=checkpoint_id,
            resumable=not blockers,
            blockers=blockers,
            restored_facts=restored,
            missing_facts=missing,
            refresh_required=refresh,
            open_operations=open_ops,
            next_legal_actions=record.get("nextLegalActions", []),
            tail_events=len(tail),
            restored_values=restored_values,
        )


def reconcile_open_operation(operation: Mapping[str, Any]) -> dict[str, Any]:
    """Classify an interrupted operation.

    The only case that permits a plain retry is one where no side effect was
    possible. Where an effect was possible and no receipt was observed, the
    disposition is RECONCILE_BEFORE_RETRY and the caller must probe actual
    state first -- a missing receipt is not evidence that nothing happened.
    """
    declared = operation.get("sideEffectPossible") is not None
    # An undeclared effect is treated as possible. The fail-open reading would
    # let a half-finished write be retried on the strength of a missing field.
    side_effect = operation.get("sideEffectPossible") is not False
    receipt = bool(operation.get("receiptObserved"))
    if not side_effect:
        disposition = "SAFE_TO_RETRY"
        reason = "the operation declared that no side effect was possible"
        requires = False
    elif receipt:
        disposition = "COMPLETED"
        reason = "a receipt was observed; the effect is accounted for"
        requires = False
    else:
        disposition = "RECONCILE_BEFORE_RETRY"
        reason = (
            ("sideEffectPossible was not declared, so an effect is treated as possible,"
             if not declared else "a side effect was possible")
            + " and no receipt was observed; probe actual state "
            "through " + str(operation.get("reconciliationProbe") or "the declared reconciliation probe")
            + " before any retry"
        )
        requires = True
    return {
        "operationId": operation.get("operationId"),
        "idempotencyKey": operation.get("idempotencyKey"),
        "sideEffectDeclared": declared,
        "disposition": disposition,
        "reason": reason,
        "requiresReconciliation": requires,
        "automaticRetryPermitted": disposition == "SAFE_TO_RETRY",
    }
