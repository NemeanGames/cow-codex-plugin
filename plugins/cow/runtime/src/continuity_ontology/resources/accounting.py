"""Resource admission and accounting.

Three rules do most of the work here:

1. **Missing is UNKNOWN, not zero.** A measurement with basis ``UNKNOWN``
   carries no value at all, and any total that depends on it is reported with
   an explicit unknown count rather than silently reduced.

2. **A declared subset is not added again.** Provider APIs commonly report
   cached input tokens and reasoning output tokens *inside* the input and
   output totals. A measurement that names a ``parentKind`` with rule
   ``SUBSET_OF_*`` is excluded from the sum and reported separately.

3. **The same measurement is counted once.** Manager, worker and nested traces
   frequently reference one provider response. Deduplication is by
   ``dedupKey``, and a conflicting value under an existing key is a rejection,
   not a silent overwrite.

Raw token counts from different tokenizer or accounting domains are not
comparable. :func:`comparable_totals` refuses to merge them unless an explicit
normalization contract is supplied.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "ResourceAdmissionError",
    "SubsetAccountingError",
    "DedupConflict",
    "admit",
    "ResourceLedger",
    "comparable_totals",
]

_SUBSET_RULES = frozenset({"SUBSET_OF_INPUT", "SUBSET_OF_OUTPUT"})

_PARENT_FOR_RULE = {
    "SUBSET_OF_INPUT": {"VENDOR_INPUT_TOKENS", "LOCAL_MODEL_INPUT_TOKENS"},
    "SUBSET_OF_OUTPUT": {"VENDOR_OUTPUT_TOKENS", "LOCAL_MODEL_OUTPUT_TOKENS"},
}

_VENDOR_KINDS = frozenset(
    {
        "VENDOR_INPUT_TOKENS",
        "VENDOR_OUTPUT_TOKENS",
        "VENDOR_CACHED_INPUT_TOKENS",
        "VENDOR_CACHE_READ_INPUT_TOKENS",
        "VENDOR_CACHE_CREATION_INPUT_TOKENS",
        "VENDOR_REASONING_OUTPUT_TOKENS",
    }
)


class ResourceAdmissionError(ValueError):
    """Raised when a resource measurement cannot be admitted as recorded."""


class SubsetAccountingError(ResourceAdmissionError):
    """Raised when a subset declaration is inconsistent with its parent."""


class DedupConflict(ResourceAdmissionError):
    """Raised when one dedup key carries two different values."""


def admit(measurement: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one measurement's accounting semantics and normalize its value.

    An OBSERVED or ESTIMATED measurement must carry a value; an UNKNOWN one
    must not. That asymmetry is deliberate: it makes ``"we did not measure"``
    structurally different from ``"we measured zero"``.
    """
    for key in ("kind", "basis", "unit", "accountingRule", "dedupKey"):
        if key not in measurement:
            raise ResourceAdmissionError("resource measurement is missing " + key)
    basis = measurement["basis"]
    has_value = measurement.get("value") is not None

    if basis in ("OBSERVED", "ESTIMATED"):
        if not has_value:
            raise ResourceAdmissionError(
                basis + " measurement of " + str(measurement["kind"]) + " carries no value"
            )
    elif basis in ("UNKNOWN", "NOT_APPLICABLE"):
        if has_value:
            raise ResourceAdmissionError(
                basis + " measurement of " + str(measurement["kind"])
                + " must not carry a value; a missing measurement is not zero"
            )
        if basis == "UNKNOWN" and not measurement.get("unknownReason"):
            raise ResourceAdmissionError("an UNKNOWN measurement must state its unknownReason")
    else:
        raise ResourceAdmissionError("unrecognized measurement basis " + repr(basis))

    rule = measurement["accountingRule"]
    parent = measurement.get("parentKind")
    if rule in _SUBSET_RULES:
        if parent is None:
            raise SubsetAccountingError(
                str(measurement["kind"]) + " declares " + rule + " but names no parentKind"
            )
        if parent not in _PARENT_FOR_RULE[rule]:
            raise SubsetAccountingError(
                str(measurement["kind"]) + " declares " + rule + " with parent " + str(parent)
                + ", which is not an input/output total for that rule"
            )
    elif parent is not None:
        raise SubsetAccountingError(
            str(measurement["kind"]) + " names a parentKind but its rule is " + rule
        )

    if measurement["kind"] in _VENDOR_KINDS and basis == "OBSERVED":
        if not measurement.get("providerName"):
            raise ResourceAdmissionError("an observed vendor measurement must name its provider")
        if not measurement.get("providerAccountingVersion"):
            raise ResourceAdmissionError(
                "an observed vendor measurement must pin its provider accounting version"
            )

    admitted = dict(measurement)
    if has_value:
        value = measurement["value"]
        if isinstance(value, float):
            raise ResourceAdmissionError(
                "resource values travel as exact decimal strings or integers, not binary floats"
            )
        admitted["value"] = Decimal(str(value))
    return admitted


class ResourceLedger:
    """Deduplicated accumulation of admitted measurements."""

    def __init__(self) -> None:
        self._by_key: dict[str, dict[str, Any]] = {}
        self._rejected: list[dict[str, Any]] = []

    def add(self, measurement: Mapping[str, Any]) -> dict[str, Any]:
        admitted = admit(measurement)
        key = admitted["dedupKey"]
        existing = self._by_key.get(key)
        if existing is not None:
            if (existing["kind"] != admitted["kind"] or existing.get("value") != admitted.get("value")
                    or existing["basis"] != admitted["basis"]):
                raise DedupConflict(
                    "dedup key " + repr(key) + " already carries a different measurement; "
                    "manager, worker and nested traces must reference one identity, not two values"
                )
            return existing
        self._by_key[key] = admitted
        return admitted

    def extend(self, measurements: Iterable[Mapping[str, Any]]) -> None:
        for measurement in measurements:
            self.add(measurement)

    def measurements(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._by_key[k] for k in sorted(self._by_key))

    def __len__(self) -> int:
        return len(self._by_key)

    # -- totals ------------------------------------------------------------

    def total(self, kind: str) -> dict[str, Any]:
        """Deduplicated total for one resource kind.

        Subset measurements are excluded from the sum and reported under
        ``declaredSubsets`` so the caller can see them without adding them.
        """
        rows = [m for m in self.measurements() if m["kind"] == kind]
        observed = [m for m in rows if m["basis"] == "OBSERVED" and m["accountingRule"] not in _SUBSET_RULES]
        estimated = [m for m in rows if m["basis"] == "ESTIMATED" and m["accountingRule"] not in _SUBSET_RULES]
        unknown = [m for m in rows if m["basis"] == "UNKNOWN"]
        subsets = [m for m in self.measurements() if m["accountingRule"] in _SUBSET_RULES
                   and (m.get("parentKind") == kind or m["kind"] == kind)]

        result: dict[str, Any] = {
            "kind": kind,
            "observedTotal": str(sum((m["value"] for m in observed), Decimal(0))) if observed else None,
            "observedCount": len(observed),
            "estimatedTotal": str(sum((m["value"] for m in estimated), Decimal(0))) if estimated else None,
            "estimatedCount": len(estimated),
            "unknownCount": len(unknown),
            "unknownReasons": sorted({str(m.get("unknownReason", "")) for m in unknown}) if unknown else [],
            "declaredSubsets": [
                {
                    "kind": m["kind"],
                    "parentKind": m["parentKind"],
                    "rule": m["accountingRule"],
                    "value": str(m["value"]) if m.get("value") is not None else None,
                }
                for m in subsets
            ],
            "admissible": len(unknown) == 0,
        }
        if unknown:
            result["inadmissibleReason"] = (
                str(len(unknown)) + " measurement(s) of " + kind + " are UNKNOWN; the total is "
                "incomplete and must not be treated as the observed value"
            )
        return result

    def subset_reconciliation(self) -> list[dict[str, Any]]:
        """Check every declared subset against its parent total."""
        findings: list[dict[str, Any]] = []
        for measurement in self.measurements():
            if measurement["accountingRule"] not in _SUBSET_RULES:
                continue
            parent_kind = measurement["parentKind"]
            parent_rows = [
                m
                for m in self.measurements()
                if m["kind"] == parent_kind and m["accountingRule"] not in _SUBSET_RULES
            ]
            parent_observed = [m for m in parent_rows if m["basis"] == "OBSERVED"]
            if not parent_observed:
                findings.append(
                    {
                        "kind": measurement["kind"],
                        "parentKind": parent_kind,
                        "status": "UNKNOWN",
                        "reason": "parent total is not observed, so the subset cannot be reconciled",
                    }
                )
                continue
            parent_total = sum((m["value"] for m in parent_observed), Decimal(0))
            value = measurement.get("value")
            if value is None:
                findings.append(
                    {
                        "kind": measurement["kind"],
                        "parentKind": parent_kind,
                        "status": "UNKNOWN",
                        "reason": "subset value is not observed",
                    }
                )
            elif value > parent_total:
                findings.append(
                    {
                        "kind": measurement["kind"],
                        "parentKind": parent_kind,
                        "status": "FAIL",
                        "reason": "declared subset " + str(value) + " exceeds its parent total "
                        + str(parent_total),
                    }
                )
            else:
                findings.append(
                    {
                        "kind": measurement["kind"],
                        "parentKind": parent_kind,
                        "status": "PASS",
                        "reason": "subset " + str(value) + " lies within parent total " + str(parent_total),
                        "note": "excluded from the parent sum; it is already inside it",
                    }
                )
        return findings

    def accounting_domains(self) -> list[dict[str, str]]:
        """Distinct (provider, accounting version, tokenizer) tuples present.

        Only observed measurements have an accounting domain. An UNKNOWN row
        records that a measurement is absent, so counting it as a domain would
        invent a second tokenizer out of a missing usage block.
        """
        seen: dict[tuple[str, str, str], dict[str, str]] = {}
        for measurement in self.measurements():
            if measurement["kind"] not in _VENDOR_KINDS:
                continue
            if measurement["basis"] != "OBSERVED":
                continue
            key = (
                str(measurement.get("providerName", "")),
                str(measurement.get("providerAccountingVersion", "")),
                str(measurement.get("tokenizerId", "")),
            )
            seen[key] = {
                "providerName": key[0],
                "providerAccountingVersion": key[1],
                "tokenizerId": key[2],
            }
        return [seen[k] for k in sorted(seen)]


def comparable_totals(
    left: ResourceLedger,
    right: ResourceLedger,
    kind: str,
    normalization_contract: str | None = None,
) -> dict[str, Any]:
    """Compare one resource kind across two ledgers, or refuse to.

    Raw token counts from incompatible tokenizer or accounting domains are not
    a valid single comparison. Without a normalization contract this returns an
    inadmissible result naming both domains rather than a ratio.
    """
    left_domains = left.accounting_domains()
    right_domains = right.accounting_domains()
    left_total = left.total(kind)
    right_total = right.total(kind)

    if left_domains != right_domains and normalization_contract is None:
        return {
            "availability": "INADMISSIBLE_INPUTS",
            "value": None,
            "unavailableReason": (
                "token counts come from different accounting domains; a normalization "
                "contract is required before they can be compared"
            ),
            "leftDomains": left_domains,
            "rightDomains": right_domains,
        }
    if not left_total["admissible"] or not right_total["admissible"]:
        return {
            "availability": "INSUFFICIENT_EVIDENCE",
            "value": None,
            "unavailableReason": "one or both sides contain UNKNOWN measurements",
            "leftUnknown": left_total["unknownCount"],
            "rightUnknown": right_total["unknownCount"],
        }
    return {
        "availability": "AVAILABLE",
        "leftTotal": left_total["observedTotal"],
        "rightTotal": right_total["observedTotal"],
        "normalizationContract": normalization_contract,
        "accountingDomains": left_domains,
    }
