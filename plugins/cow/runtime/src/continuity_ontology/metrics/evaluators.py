"""Typed metric evaluation.

Every result is a Measurement: value, unit, scope, availability, formula
version, input references and -- when there is no value -- a reason. There is
no path through this module that returns NaN, positive infinity, or a zero
standing in for a missing denominator.

A ratio whose numerator and denominator come from different unit domains is
refused rather than computed. Rework tax over tokens and rework tax over time
are two metrics, not one metric with a flexible denominator.
"""

from __future__ import annotations

import json
from decimal import Decimal, DecimalException, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "MetricError",
    "UnitDomainMismatch",
    "MetricRegistry",
    "measurement",
    "ratio",
    "load_registry",
]


class MetricError(ValueError):
    """Raised when a metric cannot be evaluated as specified."""


class UnitDomainMismatch(MetricError):
    """Raised when a ratio would divide unlike units."""


def _finite(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MetricError(label + " must be numeric") from exc
    if not result.is_finite():
        raise MetricError(label + " must be finite")
    return result


def measurement(
    metric_id: str,
    *,
    formula_version: str,
    availability: str,
    unit: str,
    scope: Mapping[str, Any],
    input_refs: Sequence[str] = (),
    value: Decimal | None = None,
    numerator: Decimal | None = None,
    denominator: Decimal | None = None,
    unavailable_reason: str | None = None,
    admissibility: str = "ADMISSIBLE",
    uncertainty: Decimal | None = None,
) -> dict[str, Any]:
    """Build a Measurement; non-finite decimal fields raise MetricError.

    Zero denominators remain typed unavailable in ratio(); non-finite inputs
    are invalid contracts, including supplied fields on unavailable records.
    """
    for label, item in (("value", value), ("numerator", numerator),
                        ("denominator", denominator), ("uncertainty", uncertainty)):
        if item is not None:
            _finite(item, label)
    if availability == "AVAILABLE" and value is None:
        raise MetricError(metric_id + " is AVAILABLE but carries no value")
    if availability != "AVAILABLE" and value is not None:
        raise MetricError(metric_id + " is " + availability + " but carries a value")
    if availability != "AVAILABLE" and not unavailable_reason:
        raise MetricError(metric_id + " is " + availability + " and must state why")

    record: dict[str, Any] = {
        "recordType": "Measurement",
        "metricId": metric_id,
        "formulaVersion": formula_version,
        "availability": availability,
        "unit": unit,
        "scope": dict(scope),
        "inputRefs": sorted(input_refs),
        "admissibility": admissibility,
    }
    if value is not None:
        record["value"] = str(value)
    if numerator is not None:
        record["numerator"] = str(numerator)
    if denominator is not None:
        record["denominator"] = str(denominator)
    if unavailable_reason:
        record["unavailableReason"] = unavailable_reason
    if uncertainty is not None:
        record["uncertainty"] = str(uncertainty)
    return record


def ratio(
    metric_id: str,
    numerator: Decimal | int | str | None,
    denominator: Decimal | int | str | None,
    *,
    formula_version: str,
    unit: str,
    scope: Mapping[str, Any],
    input_refs: Sequence[str] = (),
    scale: Decimal | int = 1,
    zero_denominator: str = "UNDEFINED_ZERO_DENOMINATOR",
    numerator_domain: str | None = None,
    denominator_domain: str | None = None,
    admissible: bool = True,
    inadmissible_reason: str | None = None,
) -> dict[str, Any]:
    """Evaluate a ratio, or return a typed unavailable result.

    ``numerator_domain`` and ``denominator_domain`` guard against dividing
    unlike units. Rework tax is the motivating case: dividing rework tokens by
    total active time produces a number with no meaning, so it raises rather
    than returning one.
    """
    # Validate supplied inputs before absence/admissibility can short-circuit.
    num = _finite(numerator, "numerator") if numerator is not None else None
    den = _finite(denominator, "denominator") if denominator is not None else None
    factor = _finite(scale, "scale")
    if numerator_domain is not None and denominator_domain is not None:
        if numerator_domain != denominator_domain:
            raise UnitDomainMismatch(
                metric_id + " would divide " + numerator_domain + " by " + denominator_domain
                + "; publish one metric per unit domain instead"
            )

    if not admissible:
        return measurement(
            metric_id, formula_version=formula_version, availability="INADMISSIBLE_INPUTS",
            unit=unit, scope=scope, input_refs=input_refs,
            unavailable_reason=inadmissible_reason or "inputs are inadmissible",
            admissibility="INADMISSIBLE_SCOPE",
        )

    if numerator is None or denominator is None:
        return measurement(
            metric_id, formula_version=formula_version, availability="INSUFFICIENT_EVIDENCE",
            unit=unit, scope=scope, input_refs=input_refs,
            unavailable_reason="numerator or denominator is not observed",
        )

    if den == 0:
        return measurement(
            metric_id, formula_version=formula_version, availability=zero_denominator,
            unit=unit, scope=scope, input_refs=input_refs, numerator=num, denominator=den,
            unavailable_reason=(
                "the denominator is zero; this is an undefined measurement, not an "
                "unbounded improvement"
            ),
        )

    try:
        value = (num / den) * factor
    except DecimalException as exc:
        raise MetricError(metric_id + " arithmetic failed") from exc
    return measurement(
        metric_id, formula_version=formula_version, availability="AVAILABLE",
        unit=unit, scope=scope, input_refs=input_refs,
        value=value, numerator=num, denominator=den,
    )


class MetricRegistry:
    """Metric definitions loaded from registries/metrics.json."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self.document = dict(document)
        self.metrics: dict[str, Mapping[str, Any]] = dict(document.get("metrics", {}))

    def definition(self, metric_id: str) -> Mapping[str, Any]:
        try:
            return self.metrics[metric_id]
        except KeyError as exc:
            raise MetricError("no metric definition for " + repr(metric_id)) from exc

    def metric_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.metrics))

    def evaluate(
        self,
        metric_id: str,
        numerator: Decimal | int | str | None,
        denominator: Decimal | int | str | None,
        *,
        scope: Mapping[str, Any],
        input_refs: Sequence[str] = (),
        admissible: bool = True,
        inadmissible_reason: str | None = None,
    ) -> dict[str, Any]:
        definition = self.definition(metric_id)
        return ratio(
            metric_id,
            numerator,
            denominator,
            formula_version=str(definition["formulaVersion"]),
            unit=str(definition["unit"]),
            scope=scope,
            input_refs=input_refs,
            scale=definition.get("scale", 1),
            zero_denominator=str(definition.get("zeroDenominator", "UNDEFINED_ZERO_DENOMINATOR")),
            numerator_domain=definition.get("unitDomain"),
            denominator_domain=definition.get("unitDomain"),
            admissible=admissible,
            inadmissible_reason=inadmissible_reason,
        )


def load_registry(path: str | Path) -> MetricRegistry:
    return MetricRegistry(json.loads(Path(path).read_text(encoding="utf-8")))
