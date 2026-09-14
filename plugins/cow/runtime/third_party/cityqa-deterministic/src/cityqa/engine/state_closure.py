"""State closure (IMPLEMENTATION DIRECTIVE section 2).

Closure runs on every exit path: PASS, FAIL, UNKNOWN, ERROR, timeout, keyboard
interrupt and unexpected exception. It is implemented as a context manager whose
``__exit__`` does the work, because ``finally`` is the only construct that
survives all of those paths.

A run that does not close leaves processes, locks and partial outputs behind,
and the next run inherits them. That is why a previous run left open blocks a
new generation rather than merely warning.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Callable, Mapping

from .atomic import AtomicWriteError, write_json
from .hashing import digest_value
from .process_control import ProcessRegistry
from .statuses import SCHEMA_VERSION, Status

__all__ = [
    "ClosureScope",
    "exit_path_for",
    "utc_now",
]


def utc_now() -> str:
    """Current UTC time in the canonical timestamp form.

    Timestamps appear in receipts for the human record. They are excluded from
    semantic identity digests by the canonicalization policy, so their presence
    never makes two otherwise identical runs disagree.
    """
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def exit_path_for(exception: BaseException | None, terminal_status: str) -> str:
    """Classify how a run left its scope."""
    if exception is None:
        return Status(terminal_status).value
    if isinstance(exception, KeyboardInterrupt):
        return "KEYBOARD_INTERRUPT"
    if isinstance(exception, TimeoutError):
        return "TIMEOUT"
    return "UNEXPECTED_EXCEPTION"


class ClosureScope:
    """Context manager that guarantees a state closure receipt.

    Usage mirrors the directive's required pattern::

        with ClosureScope(run_id, registry, receipt_path) as scope:
            run_pipeline()
            scope.set_terminal_status(status)

    The receipt is written in ``__exit__``. If writing it fails, the failure is
    recorded on the scope and re-raised only when no exception is already in
    flight -- a closure failure must not mask the original error.
    """

    def __init__(
        self,
        run_id: str,
        registry: ProcessRegistry | None = None,
        receipt_path: str | Path | None = None,
        finalize: Callable[[], Mapping[str, Any]] | None = None,
        write: Callable[[Any, Any], Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.registry = registry or ProcessRegistry()
        self.receipt_path = Path(receipt_path) if receipt_path else None
        self.finalize = finalize
        self._write = write or write_json
        self.terminal_status: str = Status.UNKNOWN.value
        self.receipt: dict[str, Any] | None = None
        self.closure_failures: list[str] = []
        self.atomic_outputs_finalized = 0
        self.atomic_outputs_abandoned: list[str] = []

    def set_terminal_status(self, status: str) -> None:
        self.terminal_status = Status(status).value

    def note_finalized(self, count: int = 1) -> None:
        self.atomic_outputs_finalized += count

    def note_abandoned(self, path: str) -> None:
        self.atomic_outputs_abandoned.append(path)

    def __enter__(self) -> "ClosureScope":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Nothing here re-raises or swallows the incoming exception: returning
        # False lets it propagate after closure has run.
        self.receipt = self._close(exc_value)
        return False

    def _close(self, exception: BaseException | None) -> dict[str, Any]:
        processes: list[dict[str, Any]] = []
        locks: list[str] = []
        handles = 0
        temporary: list[str] = []

        for label, action in (
            ("terminate_processes", lambda: processes.extend(self.registry.terminate_processes())),
            ("release_locks", lambda: locks.extend(self.registry.release_locks())),
            ("close_handles", lambda: None),
            ("remove_temporary", lambda: temporary.extend(self.registry.remove_temporary())),
        ):
            try:
                if label == "close_handles":
                    handles = self.registry.close_handles()
                else:
                    action()
            except Exception as exc:  # closure is best-effort but always reported
                self.closure_failures.append(label + ": " + repr(exc))

        if self.finalize is not None:
            try:
                extra = self.finalize()
                self.atomic_outputs_finalized += int(extra.get("finalized", 0))
                self.atomic_outputs_abandoned.extend(extra.get("abandoned", []))
            except Exception as exc:
                self.closure_failures.append("finalize: " + repr(exc))

        still_running = [
            entry for entry in processes if entry["terminationState"] == "STILL_RUNNING"
        ]
        if still_running or self.closure_failures:
            closure_state = "OPEN"
        else:
            closure_state = "CLOSED"

        receipt: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "receiptType": "StateClosureReceipt",
            "runId": self.run_id,
            "closedAt": utc_now(),
            "exitPath": exit_path_for(exception, self.terminal_status),
            "stateClosure": closure_state,
            "runOwnedProcesses": processes,
            "locksReleased": sorted(locks),
            "handlesClosed": handles,
            "temporaryStateRemoved": sorted(temporary),
            "atomicOutputsFinalized": self.atomic_outputs_finalized,
            "atomicOutputsAbandoned": sorted(self.atomic_outputs_abandoned),
            "closureFailures": list(self.closure_failures),
        }
        receipt["receiptDigest"] = digest_value(
            {k: v for k, v in receipt.items() if k not in {"closedAt", "receiptDigest"}}
        )

        if self.receipt_path is not None:
            try:
                self._write(self.receipt_path, receipt)
            except (AtomicWriteError, OSError) as exc:
                self.closure_failures.append("write_receipt: " + repr(exc))
                receipt["closureFailures"] = list(self.closure_failures)
                receipt["stateClosure"] = "OPEN"
        return receipt


def read_closure_state(receipt_path: str | Path) -> str:
    """Read a previous run's closure state.

    A missing or unreadable receipt is UNKNOWN, never CLOSED. Treating an absent
    receipt as closed would let a crashed run's leftovers into the next one.
    """
    import json

    path = Path(receipt_path)
    if not path.is_file():
        return "UNKNOWN"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return "UNKNOWN"
    state = document.get("stateClosure")
    if state in {"CLOSED", "OPEN", "UNKNOWN"}:
        return str(state)
    return "UNKNOWN"
