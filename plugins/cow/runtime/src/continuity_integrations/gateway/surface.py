"""The public Continuity control surface: exactly five tools.

New functionality routes *internally*. There is no sixth public tool for
verification, Python execution, repair, rollback, filesystem access or
promotion, and :data:`PUBLIC_TOOLS` is compared for set equality by a
conformance test, so adding one fails the build rather than shipping.

Read and write are separated inside the surface too:

* ``get_status`` and ``explain`` are read-only;
* ``advance_task`` dispatches only the transition that was already authorized;
* ``cancel_task`` records a cancellation and invalidates pending dispatch
  authority -- it does not delete evidence and it does not imply that any
  rollback occurred.

The offline command lines under ``scripts/`` and the ``ont20`` CLI are
developer and operator interfaces under local authorization. They are
deliberately not reachable from this surface.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "GatewayError",
    "UnknownTool",
    "UnauthorizedTransition",
    "PUBLIC_TOOLS",
    "READ_ONLY_TOOLS",
    "ContinuityGateway",
]


class GatewayError(ValueError):
    """Base class for gateway refusals."""


class UnknownTool(GatewayError):
    """Raised when a caller names a tool outside the public surface."""


class UnauthorizedTransition(GatewayError):
    """Raised when advance_task is asked for a transition that is not authorized."""


#: The complete public surface. This tuple is the contract.
PUBLIC_TOOLS: tuple[str, ...] = (
    "continuity.start_task",
    "continuity.advance_task",
    "continuity.get_status",
    "continuity.explain",
    "continuity.cancel_task",
)

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {"continuity.get_status", "continuity.explain"}
)

#: Names that must never appear on the public surface, with the reason. Kept as
#: data so the conformance test can assert each one individually.
REFUSED_TOOL_NAMES: dict[str, str] = {
    "continuity.verify": "verification routes internally through the audit boundary",
    "continuity.execute_python": "arbitrary execution is not a public agent capability",
    "continuity.repair": "repair is a governed operation, not a public tool",
    "continuity.rollback": "rollback requires a separately authorized actuator",
    "continuity.filesystem": "filesystem access is not a public agent capability",
    "continuity.promote": "promotion is a separate role with its own authorization",
}


class ContinuityGateway:
    """Routes the five public tools onto internal handlers."""

    def __init__(
        self,
        handlers: Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]],
        *,
        authorized_transitions: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        missing = [name for name in PUBLIC_TOOLS if name not in handlers]
        if missing:
            raise GatewayError("no handler bound for: " + ", ".join(missing))
        extra = [name for name in handlers if name not in PUBLIC_TOOLS]
        if extra:
            raise GatewayError(
                "handlers bound for tools outside the public surface: " + ", ".join(sorted(extra))
                + ". New functionality routes internally, not through a sixth public tool."
            )
        self._handlers = dict(handlers)
        self._authorized = {k: tuple(v) for k, v in (authorized_transitions or {}).items()}
        self._canceled: set[str] = set()

    # -- surface -----------------------------------------------------------

    def tools(self) -> tuple[str, ...]:
        return PUBLIC_TOOLS

    def call(self, tool: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if tool not in PUBLIC_TOOLS:
            raise UnknownTool(
                repr(tool) + " is not part of the public Continuity surface; the surface is "
                + ", ".join(PUBLIC_TOOLS)
            )
        if tool == "continuity.advance_task":
            self._check_transition(request)
        if tool == "continuity.cancel_task":
            task_id = str(request.get("taskId", ""))
            self._canceled.add(task_id)
            result = dict(self._handlers[tool](request))
            result.setdefault("canceled", True)
            result.setdefault(
                "note",
                "cancellation recorded and pending dispatch authority invalidated; "
                "no evidence was deleted and no rollback is implied",
            )
            return result
        result = dict(self._handlers[tool](request))
        if tool in READ_ONLY_TOOLS:
            result.setdefault("readOnly", True)
        return result

    def _check_transition(self, request: Mapping[str, Any]) -> None:
        task_id = str(request.get("taskId", ""))
        transition = str(request.get("transition", ""))
        if task_id in self._canceled:
            raise UnauthorizedTransition(
                "task " + task_id + " was canceled; its pending dispatch authority is invalid"
            )
        allowed = self._authorized.get(task_id)
        if allowed is None:
            raise UnauthorizedTransition(
                "no authorized transitions are recorded for task " + repr(task_id)
            )
        if transition not in allowed:
            raise UnauthorizedTransition(
                repr(transition) + " is not an already-authorized next transition for "
                + task_id + "; authorized: " + ", ".join(allowed)
            )

    def is_read_only(self, tool: str) -> bool:
        return tool in READ_ONLY_TOOLS
