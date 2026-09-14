"""Stop rules (IMPLEMENTATION DIRECTIVE section 2).

A pipeline does not stop on every mismatch. Stopping is a function of four
contract-declared properties -- required, status, severity and stop scope -- and
nothing else. Minor and major findings continue so that the run collects the
additional evidence the contract asks for, which is what makes one run's worker
packet worth more than three runs of a fail-fast-on-everything harness.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .statuses import STOPPING_SEVERITIES, Severity, Status, StopScope

__all__ = [
    "StopDecision",
    "should_stop",
    "blocked_phases_after",
    "downstream_phase_status",
]

#: Scopes whose expansion halts the currently running pipeline.
_PIPELINE_SCOPES = frozenset({"generation", "audit", "promotion"})


class StopDecision:
    """Whether a result halts the current pipeline, and why."""

    __slots__ = ("stop", "reason", "scopes")

    def __init__(self, stop: bool, reason: str, scopes: tuple[str, ...] = ()) -> None:
        self.stop = stop
        self.reason = reason
        self.scopes = scopes

    def __bool__(self) -> bool:
        return self.stop

    def as_dict(self) -> dict[str, Any]:
        return {"stop": self.stop, "reason": self.reason, "scopes": list(self.scopes)}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "StopDecision(%r, %r)" % (self.stop, self.reason)


def should_stop(
    status: str,
    required: bool,
    severity: str,
    stop_scope: str,
    scope_expansion: Sequence[str],
    pipeline: str = "generation",
) -> StopDecision:
    """Decide whether one result stops ``pipeline``.

    ``scope_expansion`` is the contract's expansion of ``stop_scope``. It is
    passed in rather than derived here because ``both`` is not self-describing
    against three named scopes; only the contract knows what it covers.
    """
    status_value = Status(status).value
    severity_value = Severity(severity).value
    StopScope(stop_scope)  # rejects a scope outside the vocabulary
    scopes = tuple(scope_expansion)

    if status_value == Status.ERROR.value:
        return StopDecision(
            True,
            "ERROR halts the pipeline regardless of scope: the harness cannot "
            "vouch for anything it runs afterwards",
            scopes,
        )

    if required and status_value == Status.UNKNOWN.value:
        return StopDecision(
            True,
            "a required probe returned UNKNOWN, so no downstream result could be "
            "concluded from it",
            scopes,
        )

    if status_value == Status.FAIL.value:
        if severity_value not in {member.value for member in STOPPING_SEVERITIES}:
            return StopDecision(
                False,
                "FAIL at severity " + severity_value + " continues so the run can "
                "collect the remaining contract-permitted evidence",
                scopes,
            )
        if pipeline in scopes:
            return StopDecision(
                True,
                "FAIL at severity " + severity_value + " with stop scope covering "
                + pipeline,
                scopes,
            )
        return StopDecision(
            False,
            "FAIL at severity " + severity_value + " but its stop scope "
            + str(scopes) + " does not cover " + pipeline,
            scopes,
        )

    return StopDecision(False, "status " + status_value + " does not stop a pipeline", scopes)


def blocked_phases_after(
    stopping_phase: str,
    phase_order: Sequence[str],
) -> tuple[str, ...]:
    """Every phase after ``stopping_phase`` in contract order.

    These become NOT_RUN. Their product state is unknown, not passing.
    """
    order = list(phase_order)
    if stopping_phase not in order:
        return ()
    index = order.index(stopping_phase)
    return tuple(order[index + 1:])


def downstream_phase_status(_phase: str) -> str:
    """The status a phase carries when a prior stop prevented its execution."""
    return Status.NOT_RUN.value


def summarize_stop(
    results: Iterable[Mapping[str, Any]],
    phase_order: Sequence[str],
) -> dict[str, Any]:
    """Describe which phases ran, which were blocked, and by what."""
    executed: list[str] = []
    blocked: list[str] = []
    stopped_by: str | None = None
    seen: set[str] = set()
    for result in results:
        phase = str(result.get("phase", ""))
        if phase and phase not in seen:
            seen.add(phase)
            if result.get("status") == Status.NOT_RUN.value:
                blocked.append(phase)
            else:
                executed.append(phase)
        if stopped_by is None and result.get("stoppedPipeline"):
            stopped_by = str(result.get("probeId"))
    order = {phase: index for index, phase in enumerate(phase_order)}
    executed.sort(key=lambda phase: order.get(phase, 1 << 16))
    blocked.sort(key=lambda phase: order.get(phase, 1 << 16))
    return {
        "phasesExecuted": executed,
        "phasesBlocked": blocked,
        "stoppedByProbeId": stopped_by,
    }
