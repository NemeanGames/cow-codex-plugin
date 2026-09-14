"""Span accounting.

Two numbers that are routinely confused are kept separate here:

**Active elapsed time** is the union of active intervals in one clock domain.
Eight workers running concurrently for ten minutes produce ten minutes of
active elapsed time, not eighty.

**Aggregate effort** is the sum of non-overlapping *leaf* actor spans. The same
eight workers produce eighty minutes of effort. Summing parent and child spans
would count the same work twice, so only leaves contribute.

Verification and rework are *purposes*, not additional states. A verification
span that lies inside an active-execution span is reported as a labelled subset
of active time, never added to it.

Spans from different clock domains cannot be unioned into a precise interval.
Rather than inventing an alignment, :func:`active_elapsed_ms` returns a typed
unavailable result and effort is reported with its uncertainty.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "TimingError",
    "Interval",
    "union_ms",
    "active_elapsed_ms",
    "aggregate_effort_ms",
    "purpose_subset_ms",
    "timing_summary",
]

_ACTIVE = "ACTIVE_EXECUTION"


class TimingError(ValueError):
    """Raised when spans are malformed."""


class Interval:
    __slots__ = ("start", "end")

    def __init__(self, start: int, end: int) -> None:
        if end < start:
            raise TimingError("span ends before it starts")
        self.start = start
        self.end = end

    @property
    def length(self) -> int:
        return self.end - self.start

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Interval(" + str(self.start) + ", " + str(self.end) + ")"


def _as_intervals(spans: Iterable[Mapping[str, Any]]) -> list[Interval]:
    out = []
    for span in spans:
        try:
            out.append(Interval(int(span["startNs"]), int(span["endNs"])))
        except KeyError as exc:
            raise TimingError("span is missing " + str(exc)) from exc
    return out


def union_ms(intervals: Sequence[Interval]) -> float:
    """Total length of the union of intervals, in milliseconds."""
    if not intervals:
        return 0.0
    ordered = sorted(intervals, key=lambda i: (i.start, i.end))
    total = 0
    current_start = ordered[0].start
    current_end = ordered[0].end
    for interval in ordered[1:]:
        if interval.start <= current_end:
            current_end = max(current_end, interval.end)
        else:
            total += current_end - current_start
            current_start, current_end = interval.start, interval.end
    total += current_end - current_start
    return total / 1_000_000.0


def _clock_domains(spans: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(s.get("clockDomain", "UNKNOWN")) for s in spans}


def active_elapsed_ms(spans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Union of ACTIVE_EXECUTION intervals within a single clock domain.

    Returns a typed result. When spans span more than one clock domain the
    value is unavailable rather than approximate: an interval union across
    unaligned hosts would be a fabricated precision.
    """
    active = [s for s in spans if s.get("state") == _ACTIVE]
    if not active:
        return {
            "availability": "AVAILABLE",
            "valueMs": 0.0,
            "clockDomain": None,
            "spanCount": 0,
        }
    domains = _clock_domains(active)
    if len(domains) > 1:
        return {
            "availability": "NOT_APPLICABLE",
            "valueMs": None,
            "clockDomains": sorted(domains),
            "spanCount": len(active),
            "unavailableReason": (
                "active elapsed time is a union within one clock domain; spans span "
                + str(len(domains)) + " domains, so report effort and uncertainty instead"
            ),
        }
    return {
        "availability": "AVAILABLE",
        "valueMs": union_ms(_as_intervals(active)),
        "clockDomain": next(iter(domains)),
        "spanCount": len(active),
    }


def aggregate_effort_ms(spans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Sum of non-overlapping leaf actor spans, per actor then summed.

    Only leaves contribute, so a parent span that merely brackets its children
    cannot double-count them. Within one actor, overlapping leaves are unioned:
    a single actor cannot be doing two things at once, and if the instrumentation
    says otherwise the overlap is a measurement artefact, not extra effort.
    """
    leaves = [s for s in spans if s.get("leaf")]
    if not leaves:
        return {"availability": "AVAILABLE", "valueMs": 0.0, "actorCount": 0, "spanCount": 0}
    by_actor: dict[str, list[Interval]] = {}
    for span in leaves:
        by_actor.setdefault(str(span.get("actorId", "UNKNOWN")), []).append(
            Interval(int(span["startNs"]), int(span["endNs"]))
        )
    total = 0.0
    for actor in sorted(by_actor):
        total += union_ms(by_actor[actor])
    unknown_allocation = sum(1 for s in leaves if s.get("allocationUnknown"))
    result: dict[str, Any] = {
        "availability": "AVAILABLE",
        "valueMs": total,
        "actorCount": len(by_actor),
        "spanCount": len(leaves),
        "clockDomains": sorted(_clock_domains(leaves)),
    }
    if unknown_allocation:
        result["allocationUnknownSpans"] = unknown_allocation
        result["uncertaintyNote"] = (
            str(unknown_allocation) + " leaf span(s) mix provider work and waiting without "
            "instrumented children; their internal allocation is unknown"
        )
    return result


def purpose_subset_ms(spans: Sequence[Mapping[str, Any]], purpose: str) -> dict[str, Any]:
    """Time spent on one purpose, reported as a subset of active time.

    ``withinActiveMs`` is the part that lies inside an active-execution
    interval. That is the number to quote when describing verification or
    rework cost; adding it to active elapsed time would count it twice.
    """
    matching = [s for s in spans if s.get("purpose") == purpose]
    if not matching:
        return {
            "purpose": purpose,
            "totalMs": 0.0,
            "withinActiveMs": 0.0,
            "outsideActiveMs": 0.0,
            "isSubsetOfActive": True,
            "spanCount": 0,
        }
    domains = _clock_domains(matching) | _clock_domains(
        [s for s in spans if s.get("state") == _ACTIVE]
    )
    if len(domains) > 1:
        return {
            "purpose": purpose,
            "availability": "NOT_APPLICABLE",
            "unavailableReason": "purpose subsets require a single clock domain",
            "clockDomains": sorted(domains),
            "spanCount": len(matching),
        }
    active_intervals = _as_intervals([s for s in spans if s.get("state") == _ACTIVE])
    matched_intervals = _as_intervals(matching)
    total = union_ms(matched_intervals)
    inside = 0.0
    for interval in matched_intervals:
        clipped: list[Interval] = []
        for active in active_intervals:
            start = max(interval.start, active.start)
            end = min(interval.end, active.end)
            if end > start:
                clipped.append(Interval(start, end))
        inside += union_ms(clipped)
    # Recompute the inside total over the union to avoid counting an overlap
    # between two matching spans twice.
    clipped_all: list[Interval] = []
    for interval in matched_intervals:
        for active in active_intervals:
            start = max(interval.start, active.start)
            end = min(interval.end, active.end)
            if end > start:
                clipped_all.append(Interval(start, end))
    inside = union_ms(clipped_all)
    return {
        "purpose": purpose,
        "totalMs": total,
        "withinActiveMs": inside,
        "outsideActiveMs": round(total - inside, 6),
        "isSubsetOfActive": abs(total - inside) < 1e-9,
        "spanCount": len(matching),
        "note": "withinActiveMs is a labelled subset of active elapsed time, not an addition to it",
    }


def timing_summary(spans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The full timing projection for a trace."""
    for span in spans:
        if "startNs" not in span or "endNs" not in span:
            raise TimingError("every span needs startNs and endNs")
        if int(span["endNs"]) < int(span["startNs"]):
            raise TimingError("span " + str(span.get("spanId")) + " ends before it starts")
    active = active_elapsed_ms(spans)
    effort = aggregate_effort_ms(spans)
    by_state: dict[str, float] = {}
    for state in sorted({str(s.get("state", "UNKNOWN")) for s in spans}):
        by_state[state] = union_ms(_as_intervals([s for s in spans if s.get("state") == state]))
    subsets = {
        purpose: purpose_subset_ms(spans, purpose)
        for purpose in sorted({str(s.get("purpose", "UNKNOWN")) for s in spans})
    }
    resolutions = [s.get('clockResolutionNs') for s in spans]
    resolution = max(resolutions) if resolutions and all(r is not None for r in resolutions) else None
    for record in [active, effort, *subsets.values()]:
        value = record.get('valueMs', record.get('totalMs'))
        record['clockResolutionNs'] = resolution
        record['belowResolution'] = value * 1_000_000 < resolution if value is not None and resolution else None
        record['uncertaintyMs'] = resolution / 1_000_000 if resolution else None
        if resolution is None:
            record['precisionUnknownReason'] = 'one or more source spans lack clock resolution'
    return {
        "activeElapsed": active,
        "aggregateEffort": effort,
        "unionByState": by_state,
        "purposeSubsets": subsets,
        "spanCount": len(spans),
        "clockResolutionNs": resolution,
        "unionByStatePrecision": {state: {'clockResolutionNs': resolution,
            'belowResolution': value * 1_000_000 < resolution if resolution else None,
            'uncertaintyMs': resolution / 1_000_000 if resolution else None} for state, value in by_state.items()},
        "contract": (
            "activeElapsed is a union in one clock domain; aggregateEffort sums "
            "non-overlapping leaf actor spans. They are different measurements and "
            "neither is derived from the other."
        ),
    }
