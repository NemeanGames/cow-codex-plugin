"""Equivalence admission and leverage evaluation.

Order is the whole point: equivalence is established *before* any resource
comparison is computed. A workflow that is cheaper because it produced a worse
artifact is not an improvement, and this module will not return a ratio for it.

Cohort rules that are enforced rather than documented:

* failed attempts stay in the denominator -- excluding them is what makes a
  survivor-biased cohort look efficient;
* the baseline must not have received solved outputs or privileged cached
  context;
* warm and cold cache conditions are matched or form separate strata, never
  silently mixed;
* leverage is computed from aggregate matched resources, not from the mean of
  per-pair ratios, which over-weights small pairs;
* setup cost is reported amortized and non-amortized, separately.

A pilot cohort is labelled a pilot. It is a debugging cohort and cannot carry a
published leverage claim regardless of what it measures.
"""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Iterable, Mapping, Sequence

from ..metrics.evaluators import measurement, ratio
from ..validate.validator import RecordValidator

__all__ = [
    "EquivalenceError",
    "ContractNotFrozen",
    "admit_pair",
    "evaluate_equivalence",
    "evaluate_leverage",
]


class EquivalenceError(ValueError):
    """Raised when an equivalence comparison cannot be made as asked."""


class ContractNotFrozen(EquivalenceError):
    """Comparison conditions must be frozen before a cohort is measured."""


VERIFICATION_COST_FIELDS = ('managerTokens', 'auditorTokens', 'recoveryTokens')


def refuse_guessed_savings(value: Any, path: str = 'input') -> None:
    """Refuse guessed avoided tokens anywhere, including nested receipt fields."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            field = path + '.' + str(key)
            if re.search(r'avoided|saved|estimatedSaving', str(key), re.IGNORECASE):
                raise EquivalenceError('guessed avoided tokens field refused: ' + field)
            refuse_guessed_savings(child, field)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            refuse_guessed_savings(child, path + '[' + str(index) + ']')


def _arm_escalation(pair: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for arm in ('baseline', 'assisted'):
        receipts = pair.get('receipts', {}).get(arm, [])
        if isinstance(receipts, Mapping):
            receipts = [receipts]
        usage = [r.get('usage', r) for r in receipts]
        models = sorted({str(v) for r in usage for v in r.get('models', [])})
        efforts = sorted({str(v) for r in usage for v in r.get('efforts', [])})
        result[arm] = {'models': models, 'efforts': efforts,
                       'escalated': len(models) > 1 or len(efforts) > 1,
                       'observationAvailable': bool(receipts)}
    return result


def admit_pair(
    pair: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Decide whether one benchmark pair is admissible under the contract."""
    reasons: list[str] = []
    refuse_guessed_savings(pair)
    escalation = _arm_escalation(pair)
    if contract.get('escalationPermitted') is False and any(a['escalated'] for a in escalation.values()):
        reasons.append('model escalation is prohibited by the equivalence contract')

    if not pair.get("baselineAccepted"):
        reasons.append("the baseline execution was not accepted")
    if not pair.get("assistedAccepted"):
        reasons.append("the assisted execution was not accepted")

    stratum = pair.get("cacheStratum")
    contract_stratum = contract.get("cacheStratum")
    if contract_stratum == "mixed_rejected" and stratum == "mixed":
        reasons.append("the pair mixes warm and cold cache conditions")
    elif contract_stratum in ("warm", "cold") and stratum != contract_stratum:
        reasons.append(
            "pair stratum " + str(stratum) + " does not match the contract stratum "
            + str(contract_stratum)
        )

    failed_checks = [
        c for c in pair.get("contaminationChecks", []) if c.get("status") != "PASS"
    ]
    for check in failed_checks:
        reasons.append(
            "contamination check " + str(check.get("checkId")) + " is "
            + str(check.get("status")) + ": " + str(check.get("reason"))
        )
    if not pair.get("contaminationChecks"):
        reasons.append(
            "no baseline-contamination checks were run; an unchecked baseline may have "
            "received solved outputs or privileged cached context"
        )

    return {
        "pairId": pair.get("pairId"),
        "admissible": not reasons,
        "reasons": reasons,
        "includedInCohort": True,
        "escalation": escalation,
        "note": (
            "an inadmissible pair stays in the cohort record; it is excluded from the "
            "numerator and denominator only where the contract says so, and its "
            "exclusion is always named"
        ),
    }


def evaluate_equivalence(
    contract: Mapping[str, Any],
    baseline_quality: Mapping[str, Any],
    assisted_quality: Mapping[str, Any],
) -> dict[str, Any]:
    """Check that the assisted workflow meets the same quality bar.

    Returns a five-state status. UNKNOWN when a required quality predicate has
    no observation; FAIL when the assisted path fell below the bar. Only PASS
    permits a resource comparison downstream.
    """
    if not contract.get("frozen"):
        raise ContractNotFrozen(
            "equivalence contract " + str(contract.get("name")) + " is not frozen; "
            "comparison conditions are frozen before a cohort is measured"
        )

    predicate_results: list[dict[str, Any]] = []
    statuses: list[str] = []

    for predicate in contract.get("qualityThresholds", []):
        predicate_id = str(predicate.get("predicateId"))
        path = str(predicate.get("subjectPath"))
        expected = predicate.get("expected")
        operator = str(predicate.get("operator"))
        observed_assisted = assisted_quality.get(path)
        observed_baseline = baseline_quality.get(path)

        if observed_assisted is None:
            status, reason = "UNKNOWN", "assisted workflow has no observation for " + path
        elif observed_baseline is None:
            status, reason = "UNKNOWN", "baseline has no observation for " + path
        else:
            status, reason = _apply_operator(
                operator, observed_assisted, observed_baseline, expected, path
            )
        predicate_results.append(
            {
                "predicateId": predicate_id,
                "status": status,
                "expected": expected,
                "observed": observed_assisted,
                "baselineObserved": observed_baseline,
                "reason": reason,
                "mandatory": bool(predicate.get("mandatory", True)),
            }
        )
        if predicate.get("mandatory", True):
            statuses.append(status)

    for kind in contract.get("requiredArtifactKinds", []):
        produced = assisted_quality.get("artifactKinds", [])
        if kind not in produced:
            predicate_results.append(
                {
                    "predicateId": "artifact:" + kind,
                    "status": "FAIL",
                    "expected": kind,
                    "observed": list(produced),
                    "reason": "the assisted workflow did not produce a required artifact kind",
                    "mandatory": True,
                }
            )
            statuses.append("FAIL")

    if "FAIL" in statuses:
        overall = "FAIL"
    elif "ERROR" in statuses:
        overall = "ERROR"
    elif "UNKNOWN" in statuses:
        overall = "UNKNOWN"
    elif statuses:
        overall = "PASS"
    else:
        overall = "UNKNOWN"

    return {
        "status": overall,
        "contractName": contract.get("name"),
        "predicateResults": predicate_results,
        "equivalenceEstablished": overall == "PASS",
        "reason": (
            "quality and evidence requirements met; resource comparison may proceed"
            if overall == "PASS"
            else "equivalence is not established, so no leverage figure is produced"
        ),
    }


def _apply_operator(
    operator: str, assisted: Any, baseline: Any, expected: Any, path: str
) -> tuple[str, str]:
    if assisted is None or baseline is None:
        return "UNKNOWN", "required quality observation is missing for " + path
    if operator == "NONINFERIOR_TO_BASELINE":
        if _num(assisted) >= _num(baseline):
            return "PASS", path + " is not inferior to the baseline"
        return "FAIL", (
            path + " fell from " + str(baseline) + " to " + str(assisted)
            + "; a cheaper but lower-quality result is not equivalent"
        )
    if operator == "GREATER_THAN_OR_EQUAL":
        if _num(assisted) >= _num(expected):
            return "PASS", path + " meets the threshold"
        return "FAIL", path + " is " + str(assisted) + ", below the required " + str(expected)
    if operator == "EQUAL":
        if assisted == expected:
            return "PASS", path + " equals the required value"
        return "FAIL", path + " is " + str(assisted) + ", expected " + str(expected)
    if operator == "SET_EQUAL":
        if set(assisted) == set(expected or []):
            return "PASS", path + " matches the required set"
        return "FAIL", path + " differs from the required set"
    return "ERROR", "operator " + repr(operator) + " is not in the allowlist"


def _num(value: Any) -> Decimal:
    return Decimal(str(value))


def _evaluate_arm_leverage(
    claim: Mapping[str, Any],
    contract: Mapping[str, Any],
    pairs: Sequence[Mapping[str, Any]],
    equivalence_result: Mapping[str, Any],
    resources_by_pair: Mapping[str, Mapping[str, Any]],
    *,
    protocol: Mapping[str, Any] | None = None,
    scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute cohort leverage, or explain why no number is admissible.

    The producer never sets the verdict. This function is the evaluator, and
    the value it returns is the only place a verdict is written.
    """
    scope = scope or {"scopeKind": "cohort", "selector": str(claim.get("metricId")), "enumerationComplete": True}
    blockers: list[str] = []

    if not equivalence_result.get("equivalenceEstablished"):
        blockers.append(
            "equivalence is " + str(equivalence_result.get("status"))
            + "; resource comparison requires accepted matched work first"
        )

    if protocol is not None:
        if not protocol.get("frozen"):
            blockers.append("the benchmark protocol is not pre-registered and frozen")
        if str(protocol.get("protocolKind")) == "PILOT":
            blockers.append(
                "this is an instrumentation pilot cohort; a pilot is a debugging cohort "
                "and cannot carry a published leverage claim"
            )
    else:
        blockers.append("no pre-registered benchmark protocol accompanies this claim")

    admissions = [admit_pair(p, contract) for p in pairs]
    inadmissible = [a for a in admissions if not a["admissible"]]
    if inadmissible:
        blockers.append(
            str(len(inadmissible)) + " of " + str(len(pairs)) + " pair(s) are inadmissible: "
            + "; ".join(sorted({r for a in inadmissible for r in a["reasons"]}))
        )

    excluded_failures = [
        p for p in pairs
        if not p.get("includedInCohort", True)
        and (not p.get("baselineAccepted") or not p.get("assistedAccepted"))
    ]
    if excluded_failures:
        blockers.append(
            str(len(excluded_failures)) + " failed attempt(s) were excluded from the cohort; "
            "removing failures from the denominator invalidates the claim"
        )

    minimum = int(contract.get("minimumMatchedPairs", 0))
    if len(pairs) < minimum:
        blockers.append(
            "cohort has " + str(len(pairs)) + " matched pair(s), below the contract minimum of "
            + str(minimum)
        )

    if blockers:
        # A pilot is blocked by design: by its kind, and -- because a pilot is
        # never sized to the contract minimum -- by its cohort size. Those two
        # blockers together mean "not a claim, as expected", which is
        # INDETERMINATE. Any other blocker (equivalence, admissibility,
        # excluded failures, an unfrozen protocol) is a defect and is REJECT.
        is_pilot = protocol is not None and str(protocol.get("protocolKind")) == "PILOT"
        by_design = all(
            b.startswith("this is an instrumentation pilot cohort")
            or (b.startswith("cohort has ") and "below the contract minimum" in b)
            for b in blockers
        )
        return {
            "recordType": "EfficiencyClaimEvaluation",
            "metricId": claim.get("metricId"),
            "status": ("FAIL" if equivalence_result.get("status") == "FAIL" or inadmissible or excluded_failures
                       else "ERROR" if equivalence_result.get("status") == "ERROR" else "UNKNOWN"),
            "verdict": "INDETERMINATE" if is_pilot and by_design else "REJECT",
            "measurement": measurement(
                str(claim.get("metricId")),
                formula_version="1.0.0",
                availability="INSUFFICIENT_EVIDENCE",
                unit="ratio",
                scope=scope,
                unavailable_reason="; ".join(blockers),
                admissibility="INADMISSIBLE_INCOMPLETE",
            ),
            "blockers": blockers,
            "pairAdmissions": admissions,
            "cohortSize": len(pairs),
        }

    missing_resources = [str(p["pairId"]) + ":" + field for p in pairs
                         for field in (["baselineTokens", "assistedTokens"]
                                       + ([] if p.get("setupAmortized") else ["setupTokens"]))
                         if resources_by_pair.get(str(p["pairId"]), {}).get(field) is None]
    if missing_resources:
        reason = "resource observations are missing: " + ", ".join(missing_resources)
        return {"status": "UNKNOWN", "verdict": "INDETERMINATE", "blockers": [reason],
                "measurement": measurement(str(claim.get("metricId")), formula_version="1.0.0",
                    unit="ratio", scope=scope, availability="INSUFFICIENT_EVIDENCE", unavailable_reason=reason)}
    baseline_total = Decimal(0)
    assisted_total = Decimal(0)
    setup_total = Decimal(0)
    for pair in pairs:
        resources = resources_by_pair.get(str(pair["pairId"]), {})
        baseline_total += Decimal(str(resources.get("baselineTokens", 0)))
        assisted_total += Decimal(str(resources.get("assistedTokens", 0)))
        if not pair.get("setupAmortized"):
            setup_total += Decimal(str(resources.get("setupTokens", 0)))

    leverage = ratio(
        str(claim.get("metricId")),
        baseline_total,
        assisted_total,
        formula_version="1.0.0",
        unit="ratio",
        scope=scope,
        input_refs=[str(p["pairId"]) for p in pairs],
    )
    leverage_with_setup = ratio(
        str(claim.get("metricId")) + ".non_amortized_setup",
        baseline_total,
        assisted_total + setup_total,
        formula_version="1.0.0",
        unit="ratio",
        scope=scope,
        input_refs=[str(p["pairId"]) for p in pairs],
    )

    return {
        "recordType": "EfficiencyClaimEvaluation",
        "metricId": claim.get("metricId"),
        "status": "PASS" if leverage["availability"] == "AVAILABLE" else "UNKNOWN",
        "verdict": "APPROVE" if leverage["availability"] == "AVAILABLE" else "INDETERMINATE",
        "measurement": leverage,
        "nonAmortizedSetupMeasurement": leverage_with_setup,
        "blockers": [],
        "pairAdmissions": admissions,
        "cohortSize": len(pairs),
        "aggregation": (
            "computed from aggregate matched resources across the cohort, not from the "
            "unweighted mean of per-pair ratios"
        ),
        "baselineTotal": str(baseline_total),
        "assistedTotal": str(assisted_total),
        "nonAmortizedSetupTotal": str(setup_total),
    }


def evaluate_leverage(claim, contract, pairs, equivalence_result, resources_by_pair, *, protocol=None, scope=None):
    """Account full verification cost before approving an equivalent cohort.

    Legacy scalar arm totals remain readable. Verification costs are typed
    ResourceUsage records; absent, UNKNOWN and ESTIMATED are never zero.
    """
    refuse_guessed_savings(claim, 'claim')
    refuse_guessed_savings(pairs, 'pairs')
    refuse_guessed_savings(resources_by_pair, 'resources')
    converted = {}
    missing = []
    unaccounted = set()
    excluded = []
    pending = [(str(pid), row) for pid, row in resources_by_pair.items()] + [('pairs', pairs)]
    while pending:
        path, node = pending.pop()
        if isinstance(node, Mapping):
            if node.get('basis') == 'ESTIMATED':
                excluded.append(path)
            pending.extend((path + ':' + str(key), value) for key, value in node.items())
        elif isinstance(node, (list, tuple)):
            pending.extend((path + ':' + str(index), value) for index, value in enumerate(node))
    validator = RecordValidator()
    for pair in pairs:
        pid = str(pair['pairId'])
        original = resources_by_pair.get(pid, {})
        row = {}
        for field in ('baselineTokens', 'assistedTokens', 'setupTokens') + VERIFICATION_COST_FIELDS:
            value = original.get(field)
            if field in VERIFICATION_COST_FIELDS:
                if field not in original:
                    missing.append((pid, field))
                if not isinstance(value, Mapping):
                    unaccounted.add(field)
                    row[field] = None
                    continue
                validation = validator.validate('ResourceUsage', value, with_envelope=False)
                if not validation.ok:
                    raise EquivalenceError(pid + ':' + field + ' invalid ResourceUsage: ' + repr(validation.issues))
                if value.get('basis') == 'UNKNOWN' and (value.get('value') is not None or not value.get('unknownReason')):
                    raise EquivalenceError(pid + ':' + field + ' UNKNOWN requires a reason and no value')
            if isinstance(value, Mapping):
                basis = value.get('basis')
                if basis == 'ESTIMATED':
                    excluded.append(pid + ':' + field)
                if basis != 'OBSERVED':
                    value = None
                else:
                    value = value.get('value')
                    if value is None:
                        raise EquivalenceError(pid + ':' + field + ' OBSERVED requires value')
            if value is not None:
                value = Decimal(str(value))
                if not value.is_finite() or value < 0:
                    raise EquivalenceError(pid + ':' + field + ' requires finite nonnegative observed cost')
            if field in VERIFICATION_COST_FIELDS and value is None:
                unaccounted.add(field)
            row[field] = value
        converted[pid] = row
    bare = _evaluate_arm_leverage(claim, contract, pairs, equivalence_result, converted, protocol=protocol, scope=scope)
    adjusted = {pid: dict(row) for pid, row in converted.items()}
    for row in adjusted.values():
        if row['assistedTokens'] is not None and all(row[f] is not None for f in VERIFICATION_COST_FIELDS):
            row['assistedTokens'] += sum((row[f] for f in VERIFICATION_COST_FIELDS), Decimal(0))
        else:
            row['assistedTokens'] = None
    result = _evaluate_arm_leverage(claim, contract, pairs, equivalence_result, adjusted, protocol=protocol, scope=scope)
    result['bareArmMeasurement'] = bare.get('measurement')
    result['bareArmLabel'] = 'baseline / assisted arm tokens, excluding manager, auditor and recovery; not full-cost leverage'
    result['excludedEstimatedMeasurements'] = sorted(set(excluded))
    admissions = result.setdefault('pairAdmissions', [admit_pair(p, contract) for p in pairs])
    for admission in admissions:
        fields = [f for pid, f in missing if pid == str(admission['pairId'])]
        if fields:
            admission['admissible'] = False
            admission['reasons'].append('absent verification costs: ' + ', '.join(fields))
    result['escalation'] = {str(a['pairId']): a['escalation'] for a in admissions}
    if unaccounted:
        blocker = 'verification cost not accounted: ' + ', '.join(f for f in VERIFICATION_COST_FIELDS if f in unaccounted)
        result.setdefault('blockers', []).append(blocker)
        if result['verdict'] != 'REJECT':
            result.update(status='UNKNOWN', verdict='INDETERMINATE')
        result['measurement'] = measurement(str(claim.get('metricId')), formula_version='1.0.0',
            availability='INSUFFICIENT_EVIDENCE', unit='ratio', scope=scope or {},
            unavailable_reason=blocker, admissibility='INADMISSIBLE_INCOMPLETE')
    return result
