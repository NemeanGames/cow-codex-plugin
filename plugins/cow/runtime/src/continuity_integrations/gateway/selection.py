"""Deterministic capability/provider selection.

The pipeline is fixed: generate the candidate universe, apply hard predicates,
compute features, rank, budget-select, commit. Ranking never rescues a
candidate a hard predicate pruned -- a high score does not make an unqualified
provider eligible.

Selection is order-independent. Shuffling the input candidates produces an
identical receipt, because the universe is sorted before anything else happens
and ties break on a declared key rather than on arrival order.

A mandatory node with no qualified provider stays in the plan as BLOCKED. It is
never dropped: a missing capability that vanishes from the DAG is a plan that
silently got easier.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from continuity_ontology.canonical.profiles import digest_with

__all__ = [
    "SelectionError",
    "select_provider",
    "build_plan",
]

_ELIGIBLE_QUALIFICATIONS = frozenset({"QUALIFIED", "PROVISIONAL"})


class SelectionError(ValueError):
    """Raised when a selection cannot be made deterministically."""


def _hard_predicates(capability_id: str, budget: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    predicates = [
        {
            "predicateId": "hp.realizes",
            "subjectPath": "realizes",
            "operator": "PRESENT",
            "expected": capability_id,
            "mandatory": True,
        },
        {
            "predicateId": "hp.qualified",
            "subjectPath": "qualification",
            "operator": "PRESENT",
            "expected": sorted(_ELIGIBLE_QUALIFICATIONS),
            "mandatory": True,
        },
        {
            "predicateId": "hp.authorized_scope",
            "subjectPath": "authorizedScope",
            "operator": "PRESENT",
            "expected": "non-empty",
            "mandatory": True,
        },
    ]
    if budget:
        predicates.append(
            {
                "predicateId": "hp.budget",
                "subjectPath": "resourceProfile",
                "operator": "LESS_THAN_OR_EQUAL",
                "expected": dict(budget),
                "mandatory": True,
            }
        )
    return predicates


def _prune(
    candidate_id: str,
    candidate: Mapping[str, Any],
    capability_id: str,
) -> str | None:
    """Return the id of the first hard predicate this candidate fails."""
    if capability_id not in candidate.get("realizes", []):
        return "hp.realizes"
    if candidate.get("qualification") not in _ELIGIBLE_QUALIFICATIONS:
        return "hp.qualified"
    if not candidate.get("authorizedScope"):
        return "hp.authorized_scope"
    return None


def _default_score(candidate: Mapping[str, Any]) -> Decimal:
    """A small, declared feature function. Quantized so ties are explicit."""
    score = Decimal(0)
    if candidate.get("qualification") == "QUALIFIED":
        score += Decimal(100)
    elif candidate.get("qualification") == "PROVISIONAL":
        score += Decimal(50)
    if candidate.get("qualificationReceipt"):
        score += Decimal(10)
    score += Decimal(len(candidate.get("realizes", [])))
    return score


def select_provider(
    node_id: str,
    capability_id: str,
    implementations: Mapping[str, Mapping[str, Any]],
    *,
    mandatory: bool = True,
    budget: Mapping[str, Any] | None = None,
    score_fn: Callable[[Mapping[str, Any]], Decimal] | None = None,
    quantization: int = 2,
    tie_break: str = "lexicographic_candidate_id",
) -> dict[str, Any]:
    """Produce a SelectionReceipt for one plan node."""
    universe = sorted(implementations)
    predicates = _hard_predicates(capability_id, budget)
    scorer = score_fn or _default_score

    pruned: list[dict[str, str]] = []
    survivors: list[str] = []
    for candidate_id in universe:
        failed = _prune(candidate_id, implementations[candidate_id], capability_id)
        if failed:
            pruned.append({"candidateId": candidate_id, "predicateId": failed})
        else:
            survivors.append(candidate_id)

    ranked = [
        {
            "candidateId": candidate_id,
            "score": str(round(scorer(implementations[candidate_id]), quantization)),
        }
        for candidate_id in survivors
    ]
    # Deterministic ordering: score descending, then the declared tie-break.
    ranked.sort(key=lambda r: (-Decimal(r["score"]), r["candidateId"]))

    committed = ranked[0]["candidateId"] if ranked else None
    blocked = committed is None and mandatory

    terminal: dict[str, str] = {}
    for entry in pruned:
        terminal[entry["candidateId"]] = "PRUNED:" + entry["predicateId"]
    for entry in ranked:
        terminal[entry["candidateId"]] = "RANKED"
    if committed:
        terminal[committed] = "COMMITTED"
    for candidate_id in universe:
        terminal.setdefault(candidate_id, "NOT_CONSIDERED")

    receipt: dict[str, Any] = {
        "recordType": "SelectionReceipt",
        "nodeId": node_id,
        "capabilityId": capability_id,
        "candidateUniverse": universe,
        "hardPredicates": predicates,
        "prunedCandidates": sorted(pruned, key=lambda p: p["candidateId"]),
        "rankedCandidates": ranked,
        "tieBreak": tie_break,
        "quantization": quantization,
        "terminalDecisionByCandidate": terminal,
        "blocked": blocked,
    }
    if committed:
        receipt["committed"] = committed
    else:
        receipt["blockedReason"] = (
            "no candidate survives the hard predicates for " + capability_id
            + "; ranking cannot override a hard predicate"
        )
    receipt["receiptDigest"] = digest_with("continuity.core.v2", receipt)
    return receipt


def build_plan(
    outcome_id: str,
    nodes: Sequence[Mapping[str, Any]],
    implementations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a frozen ExecutionPlan, preserving mandatory blocked nodes."""
    plan_nodes: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []

    for node in nodes:
        receipt = select_provider(
            str(node["nodeId"]),
            str(node["capabilityId"]),
            implementations,
            mandatory=bool(node.get("mandatory", True)),
            budget=node.get("budget"),
        )
        receipts.append(receipt)
        entry: dict[str, Any] = {
            "nodeId": str(node["nodeId"]),
            "workItem": str(node["workItem"]),
            "mandatory": bool(node.get("mandatory", True)),
            "dependsOn": sorted(node.get("dependsOn", [])),
            "blocked": bool(receipt["blocked"]),
        }
        if receipt.get("committed"):
            entry["selectedImplementation"] = receipt["committed"]
        if receipt["blocked"]:
            entry["blockedReason"] = receipt["blockedReason"]
        plan_nodes.append(entry)

    plan_nodes.sort(key=lambda n: n["nodeId"])
    _check_acyclic(plan_nodes)

    plan = {
        "recordType": "ExecutionPlan",
        "outcome": outcome_id,
        "nodes": plan_nodes,
        "selectionReceipts": receipts,
        "frozen": True,
        "blockedMandatoryNodes": sorted(
            n["nodeId"] for n in plan_nodes if n["blocked"] and n["mandatory"]
        ),
    }
    plan["planDigest"] = digest_with("continuity.core.v2", plan)
    return plan


def _check_acyclic(nodes: Sequence[Mapping[str, Any]]) -> None:
    edges = {n["nodeId"]: list(n.get("dependsOn", [])) for n in nodes}
    unknown = {d for deps in edges.values() for d in deps} - set(edges)
    if unknown:
        raise SelectionError("plan references unknown nodes: " + ", ".join(sorted(unknown)))
    state: dict[str, int] = {}

    def visit(node_id: str, path: list[str]) -> None:
        if state.get(node_id) == 2:
            return
        if state.get(node_id) == 1:
            raise SelectionError("plan contains a cycle: " + " -> ".join(path + [node_id]))
        state[node_id] = 1
        for dependency in sorted(edges[node_id]):
            visit(dependency, path + [node_id])
        state[node_id] = 2

    for node_id in sorted(edges):
        visit(node_id, [])
