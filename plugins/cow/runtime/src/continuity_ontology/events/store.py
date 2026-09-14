"""Append-only observed-execution event store.

Canonical events are append-only. A correction is a *linked* event carrying
``correctsEventId``; prior history is never edited in place, so a replay of the
log reconstructs both what was believed and what replaced it.

Re-ingesting the same event is a no-op (same event id, same payload digest).
Re-using an event id with a *different* payload is a conflict and is rejected:
that is the difference between an at-least-once delivery retry and tampering.

Unknown event types or versions fail closed into an explicit quarantine rather
than being dropped or guessed at.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from cityqa.engine.atomic import write_bytes
from ..validate.records import validate_persisted

from ..canonical.profiles import digest_with

__all__ = [
    "EventStoreError",
    "DuplicateEventConflict",
    "SequenceGap",
    "ChainBroken",
    "QuarantinedEvent",
    "EventStore",
    "GENESIS_DIGEST",
]

#: Prior-event digest of the first event in a stream.
GENESIS_DIGEST = "sha256:" + "0" * 64

_MAX_PAYLOAD_BYTES = 4 * 1024 * 1024


class EventStoreError(ValueError):
    """Base class for event-store rejections."""


class DuplicateEventConflict(EventStoreError):
    """Same event id, different payload. Never silently accepted."""


class SequenceGap(EventStoreError):
    """A sequence number is missing or out of order."""


class ChainBroken(EventStoreError):
    """The prior-event digest does not match the recorded predecessor."""


class QuarantinedEvent(EventStoreError):
    """An unknown event type or version reached a fail-closed store."""


class EventStore:
    """One append-only stream, persisted as JSON lines with a digest chain.

    A single writer owns the stream. Packet workers use separate stream roots;
    concurrent writers to one stream are a configuration error, not something
    this class silently merges.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        stream_id: str,
        known_event_types: Mapping[str, Sequence[str]] | None = None,
        fail_closed: bool = True,
    ) -> None:
        self.root = Path(root)
        self.stream_id = stream_id
        self.known_event_types = {k: tuple(v) for k, v in (known_event_types or {}).items()}
        self.fail_closed = fail_closed
        self._events: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_idempotency: dict[str, str] = {}
        self._quarantine: list[dict[str, Any]] = []
        self.root.mkdir(parents=True, exist_ok=True)
        self._log_path = self.root / (stream_id + ".events.jsonl")
        self._quarantine_path = self.root / (stream_id + ".quarantine.jsonl")
        if self._log_path.exists():
            self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        text = self._log_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            self._events.append(event)
            self._by_id[event["eventId"]] = event
            self._by_idempotency.setdefault(event["idempotencyKey"], event["eventId"])
        self.verify_chain()

    def _persist(self) -> None:
        payload = "".join(
            json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n" for e in self._events
        ).encode("utf-8")
        write_bytes(self._log_path, payload)

    def _persist_quarantine(self) -> None:
        payload = "".join(
            json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n" for e in self._quarantine
        ).encode("utf-8")
        write_bytes(self._quarantine_path, payload)

    # -- ingestion ---------------------------------------------------------

    def head_digest(self) -> str:
        if not self._events:
            return GENESIS_DIGEST
        return digest_with("continuity.core.v2", self._events[-1])

    def next_sequence(self) -> int:
        return len(self._events)

    def append(
        self,
        event_type: str,
        logical_subject: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        *,
        event_id: str | None = None,
        event_type_version: str = "1",
        wall_clock: str,
        monotonic_ns: int | None = None,
        monotonic_clock_domain: str | None = None,
        replay_policy: str = "REPLAYABLE",
        corrects_event_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one event. Returns the stored envelope.

        Ingestion is idempotent by ``idempotencyKey``: a repeated delivery of
        the same logical event returns the already-stored envelope without
        appending, so a retried write cannot double-charge a resource or
        double-credit a work unit.
        """
        self._check_known(event_type, event_type_version, logical_subject, payload)

        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(payload_bytes) > _MAX_PAYLOAD_BYTES:
            raise EventStoreError(
                "event payload exceeds the " + str(_MAX_PAYLOAD_BYTES) + " byte bound"
            )
        payload_digest = digest_with("continuity.core.v2", payload)
        resolved_id = event_id or (self.stream_id + ":" + str(self.next_sequence()).zfill(8))

        existing_id = self._by_idempotency.get(idempotency_key)
        if existing_id is not None:
            existing = self._by_id[existing_id]
            if existing["payloadDigest"] != payload_digest:
                raise DuplicateEventConflict(
                    "idempotency key " + repr(idempotency_key)
                    + " was already used with a different payload"
                )
            return existing

        if resolved_id in self._by_id:
            existing = self._by_id[resolved_id]
            if existing["payloadDigest"] != payload_digest:
                raise DuplicateEventConflict(
                    "event id " + repr(resolved_id) + " already exists with a different payload"
                )
            return existing

        if corrects_event_id is not None and corrects_event_id not in self._by_id:
            raise EventStoreError(
                "correction references unknown event " + repr(corrects_event_id)
            )

        envelope: dict[str, Any] = {
            "schemaVersion": "2.0.0",
            "recordType": "ExecutionEvent",
            "eventId": resolved_id,
            "sequence": self.next_sequence(),
            "priorEventDigest": self.head_digest(),
            "logicalSubject": logical_subject,
            "eventType": event_type,
            "eventTypeVersion": event_type_version,
            "payloadDigest": payload_digest,
            "payload": dict(payload),
            "wallClock": wall_clock,
            "replayPolicy": replay_policy,
            "idempotencyKey": idempotency_key,
        }
        if monotonic_ns is not None:
            envelope["monotonicNs"] = int(monotonic_ns)
        if monotonic_clock_domain is not None:
            envelope["monotonicClockDomain"] = monotonic_clock_domain
        if corrects_event_id is not None:
            envelope["correctsEventId"] = corrects_event_id
        if provenance is not None:
            envelope["provenance"] = dict(provenance)

        validate_persisted(envelope)
        self._events.append(envelope)
        self._by_id[resolved_id] = envelope
        self._by_idempotency[idempotency_key] = resolved_id
        self._persist()
        return envelope

    def _check_known(
        self, event_type: str, version: str, subject: str, payload: Mapping[str, Any]
    ) -> None:
        if not self.known_event_types:
            return
        versions = self.known_event_types.get(event_type)
        if versions is None or version not in versions:
            record = {
                "eventType": event_type,
                "eventTypeVersion": version,
                "logicalSubject": subject,
                "payloadDigest": digest_with("continuity.core.v2", payload),
                "reason": "UNKNOWN_EVENT_TYPE_OR_VERSION",
            }
            self._quarantine.append(record)
            self._persist_quarantine()
            if self.fail_closed:
                raise QuarantinedEvent(
                    "event type " + repr(event_type) + " version " + repr(version)
                    + " is not declared; quarantined rather than guessed at"
                )

    # -- reading and integrity --------------------------------------------

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._events)

    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)

    def quarantined(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._quarantine)

    def get(self, event_id: str) -> dict[str, Any] | None:
        return self._by_id.get(event_id)

    def effective_payloads(self) -> tuple[dict[str, Any], ...]:
        """Events with corrections applied, without editing stored history.

        A corrected event stays in the log. This projection simply reports the
        latest correction for each corrected subject alongside uncorrected
        events, in sequence order.
        """
        superseded = {e["correctsEventId"] for e in self._events if "correctsEventId" in e}
        return tuple(e for e in self._events if e["eventId"] not in superseded)

    def verify_chain(self) -> None:
        """Recompute the digest chain and sequence ordering."""
        prior = GENESIS_DIGEST
        for index, event in enumerate(self._events):
            if event["sequence"] != index:
                raise SequenceGap(
                    "event " + event["eventId"] + " has sequence " + str(event["sequence"])
                    + " at position " + str(index)
                )
            if event["priorEventDigest"] != prior:
                raise ChainBroken(
                    "event " + event["eventId"] + " does not chain to its predecessor"
                )
            recomputed = digest_with("continuity.core.v2", event["payload"])
            if recomputed != event["payloadDigest"]:
                raise ChainBroken(
                    "event " + event["eventId"] + " payload does not match its recorded digest"
                )
            prior = digest_with("continuity.core.v2", event)

    def replay(self, reducer, initial: Any) -> Any:
        """Fold the stream through ``reducer(state, event) -> state``.

        Deterministic: the same log always yields the same state, which is what
        makes resume-from-checkpoint verifiable rather than merely plausible.
        """
        state = initial
        for event in self._events:
            state = reducer(state, event)
        return state

    def tail_from(self, sequence: int) -> tuple[dict[str, Any], ...]:
        """Events after a sealed position, used to verify an open tail."""
        return tuple(e for e in self._events if e["sequence"] > sequence)
