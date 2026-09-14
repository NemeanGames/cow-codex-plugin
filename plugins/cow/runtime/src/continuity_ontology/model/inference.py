"""Bounded inference with entailment receipts.

Only three general closures exist: derivation ancestry, prerequisite
reachability and temporal precedence. Authorization, ownership, rollback
scope, hash binding, observation, measurement, validation, gate passage,
save/reload, equivalence and promotion are *not* transitive, and asking for a
closure over any of them raises rather than returning an empty result -- a
silent empty answer is how a non-transitive relation gets treated as one.

Every closure that is used to prune, rank, authorize or accept emits an
EntailmentReceipt carrying the exact witness path, so a downstream reader can
check the derivation instead of trusting the label.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with
from .metamodel import Metamodel

__all__ = [
    "InferenceError",
    "NonTransitiveRelation",
    "ClosureBoundExceeded",
    "InferenceEngine",
]

_IMPLEMENTATION_VERSION = "continuity_ontology.model.inference/2.0.0"


class InferenceError(ValueError):
    """Raised when a closure request is not permitted or is malformed."""


class NonTransitiveRelation(InferenceError):
    """Raised when a closure is requested over a relation that is not transitive."""


class ClosureBoundExceeded(InferenceError):
    """Raised when a closure exceeds the model's declared depth bound."""


class InferenceEngine:
    """Computes only the closures the model declares, with witnesses."""

    def __init__(self, model: Metamodel) -> None:
        self.model = model
        self.allowed: dict[str, str] = {
            closure: direct for direct, closure in model.closure_pairs()
        }
        self.non_transitive = tuple(model.inference.get("nonTransitive", ()))
        self.max_depth = int(model.inference.get("maxClosureDepth", 64))
        self.receipt_required = bool(model.inference.get("entailmentReceiptRequired", True))
        self._rule_digest = digest_with(
            "continuity.core.v2",
            {
                "allowedClosures": dict(sorted(self.allowed.items())),
                "nonTransitive": list(self.non_transitive),
                "maxClosureDepth": self.max_depth,
                "implementation": _IMPLEMENTATION_VERSION,
            },
        )

    # -- queries -----------------------------------------------------------

    def closure(
        self,
        closure_relation: str,
        edges: Mapping[str, Sequence[str]],
        start: str,
    ) -> tuple[str, ...]:
        """All nodes reachable from ``start`` under the declared direct relation."""
        self._require_allowed(closure_relation)
        reached: list[str] = []
        seen = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth > self.max_depth:
                raise ClosureBoundExceeded(
                    closure_relation + " exceeded the declared depth bound of " + str(self.max_depth)
                )
            for nxt in edges.get(node, ()):  # deterministic: caller supplies order
                if nxt in seen:
                    continue
                seen.add(nxt)
                reached.append(nxt)
                queue.append((nxt, depth + 1))
        return tuple(reached)

    def witness_path(
        self,
        closure_relation: str,
        edges: Mapping[str, Sequence[str]],
        start: str,
        target: str,
    ) -> tuple[str, ...] | None:
        """The exact path that entails ``start -> target``, or None."""
        self._require_allowed(closure_relation)
        parents: dict[str, str] = {}
        seen = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if node == target and node != start:
                path = [node]
                while path[-1] != start:
                    path.append(parents[path[-1]])
                return tuple(reversed(path))
            if depth >= self.max_depth:
                continue
            for nxt in edges.get(node, ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                parents[nxt] = node
                queue.append((nxt, depth + 1))
        return None

    def entail(
        self,
        closure_relation: str,
        edges: Mapping[str, Sequence[str]],
        start: str,
        target: str,
        *,
        authority_classes: Sequence[str],
        intended_use: str,
        source_graph_digest: str | None = None,
    ) -> dict[str, Any]:
        """Return an EntailmentReceipt for one derived edge.

        Raises when the edge is not entailed: an unsupported inference must not
        return a receipt with an empty witness.
        """
        path = self.witness_path(closure_relation, edges, start, target)
        if path is None:
            raise InferenceError(
                "no witness path entails " + start + " " + closure_relation + " " + target
            )
        graph_digest = source_graph_digest or digest_with(
            "continuity.core.v2",
            {"edges": {k: list(v) for k, v in sorted(edges.items())}},
        )
        receipt = {
            "recordType": "EntailmentReceipt",
            "receiptId": closure_relation + ":" + start + "->" + target,
            "relation": closure_relation,
            "sourceGraphDigest": graph_digest,
            "metamodelDigest": self.model.digest,
            "ruleDigest": self._rule_digest,
            "implementationDigest": digest_with("continuity.core.v2", {"impl": _IMPLEMENTATION_VERSION}),
            "witnessPath": list(path),
            "authorityClasses": list(authority_classes),
            "intendedUse": intended_use,
            "depth": len(path) - 1,
        }
        return receipt

    # -- guards ------------------------------------------------------------

    def _require_allowed(self, closure_relation: str) -> None:
        if closure_relation in self.allowed:
            return
        relation = self.model.relations.get(closure_relation)
        if relation is None:
            raise InferenceError("unknown relation " + repr(closure_relation))
        raise NonTransitiveRelation(
            repr(closure_relation) + " is not a permitted closure. Permitted closures: "
            + ", ".join(sorted(self.allowed))
            + ". Authorization, ownership, rollback scope, hash binding, observation, "
            "measurement, validation, gate passage, save/reload, equivalence and promotion "
            "do not propagate along edges."
        )

    def is_closure_permitted(self, name: str) -> bool:
        return name in self.allowed

    def rule_digest(self) -> str:
        return self._rule_digest
