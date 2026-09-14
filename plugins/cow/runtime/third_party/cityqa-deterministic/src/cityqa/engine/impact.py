"""Impact-based rerun (IMPLEMENTATION DIRECTIVE section 12).

Given a set of changed files, decide the smallest set of probes that must run
again. The point is ordering as much as economy: a plugin descriptor change must
not trigger spatial or visual probes before environment and graph-provider
checks have passed, because a spatial result computed under a broken environment
is not a cheaper answer, it is a wrong one.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Iterable, Mapping, Sequence

from .canonical import canonical_path

__all__ = ["ImpactPlan", "plan_rerun", "matches_any"]


def matches_any(logical: str, patterns: Iterable[str]) -> bool:
    """True when a logical path matches any glob pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(logical, pattern):
            return True
        # ``**/`` prefixes are common in contract patterns; fnmatch does not
        # treat them as optional, so allow the bare-suffix reading too.
        if pattern.startswith("**/") and fnmatch.fnmatch(logical, pattern[3:]):
            return True
    return False


class ImpactPlan:
    """Which probes rerun, which phases they gate, and why."""

    __slots__ = ("changed_files", "directly_impacted", "invalidated", "required_first",
                 "probes_to_run", "gated_phases", "reasons")

    def __init__(
        self,
        changed_files: Sequence[str],
        directly_impacted: Sequence[str],
        invalidated: Sequence[str],
        required_first: Sequence[str],
        probes_to_run: Sequence[str],
        gated_phases: Sequence[str],
        reasons: Mapping[str, str],
    ) -> None:
        self.changed_files = list(changed_files)
        self.directly_impacted = list(directly_impacted)
        self.invalidated = list(invalidated)
        self.required_first = list(required_first)
        self.probes_to_run = list(probes_to_run)
        self.gated_phases = list(gated_phases)
        self.reasons = dict(reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "changedFiles": self.changed_files,
            "directlyImpactedProbes": self.directly_impacted,
            "invalidatedProbes": self.invalidated,
            "prerequisiteProbes": self.required_first,
            "probesToRun": self.probes_to_run,
            "gatedPhases": self.gated_phases,
            "reasons": self.reasons,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ImpactPlan(%d changed -> %d probes)" % (
            len(self.changed_files), len(self.probes_to_run)
        )


def plan_rerun(contract: Any, changed_files: Iterable[str]) -> ImpactPlan:
    """Compute the rerun plan for a set of changed files.

    ``contract`` is a :class:`~cityqa.engine.contracts.ContractSet`.
    """
    changed = sorted({canonical_path(str(path)) for path in changed_files})
    specs = contract.probes()
    by_id = {spec.probe_id: spec for spec in specs}
    phase_index = {phase: index for index, phase in enumerate(contract.phase_order)}

    reasons: dict[str, str] = {}
    directly: list[str] = []
    for spec in specs:
        if not spec.input_patterns:
            continue
        for logical in changed:
            if matches_any(logical, spec.input_patterns):
                directly.append(spec.probe_id)
                reasons[spec.probe_id] = "input " + logical + " matched a declared pattern"
                break

    # Probes the impacted probes declare they invalidate.
    invalidated: list[str] = []
    for probe_id in directly:
        for target in by_id[probe_id].invalidated_probes:
            if target in by_id and target not in invalidated and target not in directly:
                invalidated.append(target)
                reasons[target] = "invalidated by " + probe_id

    # Prerequisites, walked transitively so ordering holds for chains.
    required: list[str] = []
    frontier = list(directly) + list(invalidated)
    seen: set[str] = set(frontier)
    while frontier:
        current = frontier.pop()
        for prerequisite in by_id[current].required_probes:
            if prerequisite in by_id and prerequisite not in seen:
                seen.add(prerequisite)
                required.append(prerequisite)
                reasons[prerequisite] = "prerequisite of " + current
                frontier.append(prerequisite)

    to_run = sorted(
        set(directly) | set(invalidated) | set(required),
        key=lambda pid: (phase_index.get(by_id[pid].phase, 1 << 16), pid),
    )

    # Downstream phases the impacted probes gate. A probe in an earlier phase
    # gates the later phases it declares; those phases are not evaluated until
    # the gating probe passes.
    gated: set[str] = set()
    for probe_id in set(directly) | set(invalidated):
        gated.update(by_id[probe_id].downstream_phases)
    gated_phases = sorted(gated, key=lambda phase: phase_index.get(phase, 1 << 16))

    return ImpactPlan(
        changed_files=changed,
        directly_impacted=sorted(set(directly)),
        invalidated=sorted(set(invalidated)),
        required_first=sorted(set(required)),
        probes_to_run=to_run,
        gated_phases=gated_phases,
        reasons=reasons,
    )


def ordering_violations(plan: ImpactPlan, contract: Any) -> list[str]:
    """Report probes scheduled ahead of a prerequisite they declare.

    Used by the repository verifier: a contract whose ``requiredProbes`` point
    forward in phase order cannot be executed in a single serial pass.
    """
    by_id = {spec.probe_id: spec for spec in contract.probes()}
    phase_index = {phase: index for index, phase in enumerate(contract.phase_order)}
    violations: list[str] = []
    for probe_id in plan.probes_to_run:
        spec = by_id[probe_id]
        own = (phase_index.get(spec.phase, 1 << 16), spec.probe_id)
        for prerequisite in spec.required_probes:
            other = by_id.get(prerequisite)
            if other is None:
                violations.append(probe_id + " requires unknown probe " + prerequisite)
                continue
            theirs = (phase_index.get(other.phase, 1 << 16), other.probe_id)
            if theirs > own:
                violations.append(
                    probe_id + " requires " + prerequisite + ", which runs later in "
                    "contract order"
                )
    return violations
