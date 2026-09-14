"""Accepted-work accounting.

Every counted unit has a stable accounting id, a frozen weight, required
gates, an acceptance receipt and a partition. Credit is granted once. The
inflation routes this guards against are all real ones seen in practice:

* the same unit accepted twice under two receipts;
* a retry credited alongside the attempt it replaced;
* a parent outcome credited alongside its own children in one partition;
* two artifact versions of one deliverable credited separately;
* a re-render of an unchanged committed view credited as new work.

Revocation appends an invalidation entry. The original credit stays in the
ledger, so both the original and the corrected view remain readable, and W is
recomputed rather than edited.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "WorkAccountingError",
    "PolicyNotFrozen",
    "DuplicateCredit",
    "WorkUnitPolicy",
    "AcceptedWorkLedger",
]


class WorkAccountingError(ValueError):
    """Base class for accepted-work failures."""


class PolicyNotFrozen(WorkAccountingError):
    """Weighting must be frozen before a benchmark or release measurement."""


class DuplicateCredit(WorkAccountingError):
    """A unit would be credited more than once."""


class WorkUnitPolicy:
    """A predeclared, versioned acceptance universe with frozen weights."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.version = str(document.get("policyVersion", ""))
        self.frozen = bool(document.get("frozen", False))
        self._units: dict[str, dict[str, Any]] = {}
        for unit in document.get("acceptanceUniverse", []):
            accounting_id = str(unit["accountingId"])
            if accounting_id in self._units:
                raise WorkAccountingError(
                    "duplicate accounting id in the acceptance universe: " + accounting_id
                )
            self._units[accounting_id] = {
                "accountingId": accounting_id,
                "weight": Decimal(str(unit["weight"])),
                "requiredGateIds": tuple(unit.get("requiredGateIds", ())),
                "partition": str(unit["partition"]),
                "partialCreditDefined": bool(unit.get("partialCreditDefined", False)),
            }
        self._parents: dict[str, str] = dict(document.get("parentOf", {}))

    def knows(self, accounting_id: str) -> bool:
        return accounting_id in self._units

    def unit(self, accounting_id: str) -> Mapping[str, Any]:
        try:
            return self._units[accounting_id]
        except KeyError as exc:
            raise WorkAccountingError(
                "accounting id " + repr(accounting_id) + " is outside the predeclared "
                "acceptance universe; work that was not declared cannot be credited"
            ) from exc

    def parent_of(self, accounting_id: str) -> str | None:
        return self._parents.get(accounting_id)

    def unit_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._units))


class AcceptedWorkLedger:
    """Append-only credit and invalidation ledger."""

    def __init__(self, policy: WorkUnitPolicy, measurement_window: str) -> None:
        self.policy = policy
        self.window = measurement_window
        self._entries: list[dict[str, Any]] = []
        self._credited: dict[str, dict[str, Any]] = {}
        self._rejections: list[dict[str, Any]] = []

    # -- crediting ---------------------------------------------------------

    def credit(
        self,
        receipt: Mapping[str, Any],
        *,
        satisfied_gate_ids: Sequence[str],
        for_measurement: bool = True,
    ) -> dict[str, Any]:
        """Credit one acceptance receipt, or record why it was refused."""
        accounting_id = str(receipt["accountingId"])
        if for_measurement and not self.policy.frozen:
            raise PolicyNotFrozen(
                "work-unit weighting must be frozen before a benchmark or release "
                "measurement; policy " + self.policy.version + " is still open"
            )
        unit = self.policy.unit(accounting_id)

        if receipt.get("workUnitPolicyVersion") != self.policy.version:
            return self._reject(
                receipt, "POLICY_VERSION_MISMATCH",
                "receipt cites policy " + str(receipt.get("workUnitPolicyVersion"))
                + " but the ledger is measuring under " + self.policy.version,
            )

        declared_weight = Decimal(str(receipt["weight"]))
        if declared_weight != unit["weight"]:
            return self._reject(
                receipt, "POST_HOC_REWEIGHTING",
                "receipt weight " + str(declared_weight) + " differs from the frozen weight "
                + str(unit["weight"]),
            )

        missing_gates = [g for g in unit["requiredGateIds"] if g not in set(satisfied_gate_ids)]
        if missing_gates:
            return self._reject(
                receipt, "REQUIRED_GATE_NOT_SATISFIED",
                "required gate(s) not satisfied: " + ", ".join(sorted(missing_gates)),
            )

        if accounting_id in self._credited:
            return self._reject(
                receipt, "DUPLICATE_CREDIT",
                "accounting id " + accounting_id + " is already credited under receipt "
                + str(self._credited[accounting_id]["receiptId"]),
            )

        parent = self.policy.parent_of(accounting_id)
        if parent and parent in self._credited:
            if self.policy.unit(parent)["partition"] == unit["partition"]:
                return self._reject(
                    receipt, "PARENT_CHILD_DOUBLE_CREDIT",
                    "parent " + parent + " is already credited in partition "
                    + unit["partition"] + "; a parent and its children cannot both be "
                    "credited in one accounting partition",
                )
        for credited_id in self._credited:
            if self.policy.parent_of(credited_id) == accounting_id:
                if self.policy.unit(credited_id)["partition"] == unit["partition"]:
                    return self._reject(
                        receipt, "PARENT_CHILD_DOUBLE_CREDIT",
                        "child " + credited_id + " is already credited in partition "
                        + unit["partition"],
                    )

        entry = {
            "recordType": "AcceptedWorkLedgerEntry",
            "sequence": len(self._entries),
            "receiptId": str(receipt["receiptId"]),
            "accountingId": accounting_id,
            "weight": str(unit["weight"]),
            "delta": "CREDIT",
            "measurementWindow": self.window,
            "partition": unit["partition"],
            "firstQualifyingAttempt": bool(receipt.get("firstQualifyingAttempt", False)),
        }
        self._entries.append(entry)
        self._credited[accounting_id] = entry
        return entry

    def _reject(self, receipt: Mapping[str, Any], code: str, reason: str) -> dict[str, Any]:
        rejection = {
            "receiptId": receipt.get("receiptId"),
            "accountingId": receipt.get("accountingId"),
            "credited": False,
            "code": code,
            "reason": reason,
        }
        self._rejections.append(rejection)
        return rejection

    def invalidate(self, accounting_id: str, reason: str) -> dict[str, Any]:
        """Append an accounting correction; the original credit is retained."""
        if accounting_id not in self._credited:
            raise WorkAccountingError(
                "cannot invalidate " + repr(accounting_id) + ": it is not credited"
            )
        original = self._credited.pop(accounting_id)
        entry = {
            "recordType": "AcceptedWorkLedgerEntry",
            "sequence": len(self._entries),
            "receiptId": original["receiptId"],
            "accountingId": accounting_id,
            "weight": original["weight"],
            "delta": "INVALIDATE",
            "measurementWindow": self.window,
            "partition": original["partition"],
            "reason": reason,
        }
        self._entries.append(entry)
        return entry

    # -- totals ------------------------------------------------------------

    def total_weight(self) -> Decimal:
        """W: the sum of frozen weights over unique currently-accepted units."""
        return sum((Decimal(e["weight"]) for e in self._credited.values()), Decimal(0))

    def accepted_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._credited))

    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._entries)

    def rejections(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._rejections)

    def first_pass_yield(self) -> dict[str, Any]:
        total = len(self._credited)
        if total == 0:
            return {
                "availability": "NOT_APPLICABLE",
                "value": None,
                "unavailableReason": "no accepted units in the cohort",
            }
        first_pass = sum(1 for e in self._credited.values() if e["firstQualifyingAttempt"])
        return {
            "availability": "AVAILABLE",
            "value": first_pass / total,
            "numerator": first_pass,
            "denominator": total,
            "unit": "fraction",
        }

    def reconcile(self, receipts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        """Check the ledger against the acceptance receipts that produced it."""
        receipt_ids = {str(r["receiptId"]) for r in receipts if not r.get("revoked")}
        ledger_ids = {e["receiptId"] for e in self._credited.values()}
        return {
            "reconciled": receipt_ids == ledger_ids,
            "inReceiptsOnly": sorted(receipt_ids - ledger_ids),
            "inLedgerOnly": sorted(ledger_ids - receipt_ids),
            "acceptedUnits": len(self._credited),
            "totalWeight": str(self.total_weight()),
        }
