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


_INTEGRITY_NOT_RUN_UNCHECKED: dict[str, Any] = {
    "status": "NOT_RUN", "reason": "evidence integrity was not checked",
    "checked": 0, "passed": 0, "findings": [], "blockers": [],
}


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
        "evidence_integrity",
        "claim_integrity",
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
        evidence_integrity: Mapping[str, Any] | None = None,
        claim_integrity: Mapping[str, Any] | None = None,
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
        self.evidence_integrity = dict(evidence_integrity or _INTEGRITY_NOT_RUN_UNCHECKED)
        self.claim_integrity = dict(claim_integrity or {})

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
            "evidenceIntegrity": self.evidence_integrity,
            "claimIntegrity": self.claim_integrity,
        }

    def __bool__(self) -> bool:
        return self.resumable


class CheckpointStore:
    """Commits checkpoints and resumes from them in a fresh process.

    ``cas_root`` and ``records_root`` locate the run's content store and
    sealed records for the evidence-integrity pass on resume. When omitted
    the historical layout is assumed: ``<run>/cas`` and ``<run>/records``
    beside ``<run>/checkpoints``.
    """

    def __init__(self, root: str | os.PathLike[str], *, validate_records: bool = False,
                 cas_root: str | os.PathLike[str] | None = None,
                 records_root: str | os.PathLike[str] | None = None) -> None:
        self.root = Path(root)
        self.validate_records = validate_records
        self.cas_root = Path(cas_root) if cas_root is not None else None
        self.records_root = Path(records_root) if records_root is not None else None
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
        proposed_claim_records: Mapping[str, Any] | None = None,
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
        claim_check = self.claim_integrity(record, proposed=proposed_claim_records)
        if claim_check["blockers"]:
            raise CheckpointError("; ".join(claim_check["blockers"]))
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

        # Evidence integrity: every path the snapshot binds must have its
        # bytes in the CAS and a sealed record naming it with the same digest.
        # A checkpoint whose facts all restore is still not resumable over a
        # mis-bound, missing or corrupted evidence reference.
        integrity = self.evidence_integrity(record)
        blockers.extend(integrity["blockers"])
        claims = self.claim_integrity(record)
        blockers.extend(claims["blockers"])

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
            evidence_integrity=integrity,
            claim_integrity=claims,
        )

    def claim_integrity(self, record: Mapping[str, Any], *, proposed=None) -> dict[str, Any]:
        from .claim_integrity import check_claim_integrity
        from ..claims.cas import ContentStore
        cas_root = self.cas_root if self.cas_root is not None else self.root.parent / "cas"
        records_root = self.records_root if self.records_root is not None else self.root.parent / "records"
        return check_claim_integrity(record, records_root,
                                     ContentStore(cas_root) if cas_root.is_dir() else None,
                                     proposed=proposed)

    # -- evidence integrity ----------------------------------------------

    def evidence_integrity(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """The evidence-integrity pass over a loaded checkpoint.

        ``NOT_RUN`` is reported, never treated as a pass: when the snapshot
        references evidence and no CAS can be located, the result carries a
        blocker. Only a snapshot with zero evidence references is
        ``NOT_RUN`` without a blocker.
        """
        from ..claims.cas import ContentStore
        from .evidence_integrity import load_evidence_records, snapshot_references, verify_evidence_bindings

        snapshot = record.get("snapshot") or {}
        refs = snapshot_references(snapshot)
        if not refs:
            return {"status": "NOT_RUN", "reason": "the snapshot references no evidence",
                    "checked": 0, "passed": 0, "findings": [], "blockers": []}
        explicit = self.cas_root is not None
        cas_root = self.cas_root if explicit else self.root.parent / "cas"
        if not cas_root.is_dir():
            reason = (("explicit CAS root " + str(cas_root) + " does not exist or is not a directory")
                      if explicit else
                      ("no CAS root found at " + str(cas_root) + "; pass --cas-root"))
            return {"status": "NOT_RUN", "reason": reason, "checked": 0, "passed": 0,
                    "findings": [{"section": section, "path": path, "digest": digest, "status": "NOT_RUN",
                                  "problems": []} for section, path, digest in refs],
                    "blockers": ["evidence integrity not run: " + reason]}
        records_root = self.records_root if self.records_root is not None else self.root.parent / "records"
        records = load_evidence_records(records_root)
        # The sealed Claim, when the run wrote one, is checked against the
        # snapshot too: its evidence refs and its evidence ids must equal the
        # snapshot's digests and derived ids. A run without a claim record
        # (the e2e pipeline keeps its claim in the bundle) reports
        # claimChecked: false rather than pretending the check ran.
        claim = None
        claim_path = Path(records_root) / "claim.json"
        if claim_path.is_file():
            try:
                loaded = json.loads(claim_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, dict) and loaded.get("recordType") == "Claim":
                claim = loaded
        witnesses = (record.get("closureReceipt") or {}).get("witnessRefs")
        result = verify_evidence_bindings(
            snapshot, records, ContentStore(cas_root),
            witness_refs=witnesses if isinstance(witnesses, list) else None, claim=claim)
        result["casRoot"] = str(cas_root)
        result["recordsRoot"] = str(records_root)
        result["evidenceRecords"] = len(records)
        return result


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
