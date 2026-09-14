"""Competency queries.

Each query answers one question the ontology exists to answer, and each answer
carries the witness records it was computed from. An answer without witnesses
is not returned: plausible prose with no supporting query result is exactly the
failure mode these guard against.

Queries are deterministic and read-only. They sort their inputs, they never
consult wall-clock time, and running one twice over the same corpus gives the
same answer and the same witness list.
"""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

__all__ = ["QueryError", "COMPETENCY_QUERIES", "answer", "query_ids"]


class QueryError(ValueError):
    """Raised when a query cannot be answered from the corpus supplied."""


def _answer(
    query_id: str,
    value: Any,
    witnesses: Sequence[str],
    explanation: str,
    *,
    available: bool = True,
    unavailable_reason: str | None = None,
) -> dict[str, Any]:
    if available and not witnesses:
        raise QueryError(
            query_id + " produced an answer with no witness references; an unsupported "
            "answer is not returned"
        )
    return {
        "queryId": query_id,
        "available": available,
        "value": value if available else None,
        "witnessRefs": sorted(witnesses),
        "explanation": explanation,
        "unavailableReason": unavailable_reason,
    }


def _q_accepted_work(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """How much accepted work closed in this window?"""
    entries = [e for e in corpus.get("acceptedWorkLedger", []) if e.get("delta") == "CREDIT"]
    invalidated = {e["accountingId"] for e in corpus.get("acceptedWorkLedger", [])
                   if e.get("delta") == "INVALIDATE"}
    live = [e for e in entries if e["accountingId"] not in invalidated]
    if not live:
        return _answer(
            "q.accepted_work", None, [], "no credited units in the window",
            available=False, unavailable_reason="the accepted-work ledger has no live credits",
        )
    total = sum((Decimal(str(e["weight"])) for e in live), Decimal(0))
    return _answer(
        "q.accepted_work",
        {"totalWeight": str(total), "unitCount": len(live)},
        [str(e["receiptId"]) for e in live],
        "sum of frozen weights over unique currently-accepted units",
    )


def _q_which_units_were_not_credited(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Which submitted units were refused credit, and why?"""
    rejections = corpus.get("creditRejections", [])
    if not rejections:
        return _answer(
            "q.refused_credit", [], ["ledger:no-rejections"],
            "no submitted unit was refused credit",
        )
    return _answer(
        "q.refused_credit",
        [{"accountingId": r["accountingId"], "code": r["code"]} for r in rejections],
        [str(r["receiptId"]) for r in rejections],
        "each refusal names the accounting rule it violated",
    )


def _q_unverified_claims(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Which mandatory claims are not independently verified?"""
    results = corpus.get("auditClaimResults", [])
    if not results:
        return _answer(
            "q.unverified_claims", None, [], "no audit results in the corpus",
            available=False, unavailable_reason="the corpus contains no audit result",
        )
    unverified = [r for r in results if r.get("status") != "PASS"]
    return _answer(
        "q.unverified_claims",
        [{"claimId": r["claimId"], "status": r["status"], "reason": r.get("reason", "")}
         for r in sorted(unverified, key=lambda r: str(r["claimId"]))],
        [str(r["claimId"]) for r in results],
        "claims whose independent recomputation did not reach PASS",
    )


def _q_producer_auditor_disagreements(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Where did the auditor disagree with the producer?"""
    results = corpus.get("auditClaimResults", [])
    producer = corpus.get("producerStatuses", {})
    if not results:
        return _answer(
            "q.disagreements", None, [], "no audit results",
            available=False, unavailable_reason="the corpus contains no audit result",
        )
    disagreements = [
        {"claimId": r["claimId"], "producer": producer.get(r["claimId"]), "auditor": r["status"]}
        for r in sorted(results, key=lambda r: str(r["claimId"]))
        if producer.get(r["claimId"]) is not None and producer[r["claimId"]] != r["status"]
    ]
    return _answer(
        "q.disagreements", disagreements, [str(r["claimId"]) for r in results],
        "claims where independent recomputation reached a different status",
    )


def _q_resource_unknowns(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Which resources were not measured?"""
    rows = corpus.get("resourceMeasurements", [])
    if not rows:
        return _answer(
            "q.resource_unknowns", None, [], "no resource measurements",
            available=False, unavailable_reason="the corpus contains no resource measurements",
        )
    unknown = [r for r in rows if r.get("basis") == "UNKNOWN"]
    return _answer(
        "q.resource_unknowns",
        [{"kind": r["kind"], "reason": r.get("unknownReason", "")}
         for r in sorted(unknown, key=lambda r: str(r["kind"]))],
        [str(r["dedupKey"]) for r in rows],
        "measurements explicitly recorded as not observed; these are not zero",
    )


def _q_blocked_plan_nodes(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Which mandatory plan nodes have no qualified provider?"""
    nodes = corpus.get("planNodes", [])
    if not nodes:
        return _answer(
            "q.blocked_nodes", None, [], "no plan in the corpus",
            available=False, unavailable_reason="the corpus contains no execution plan",
        )
    blocked = [
        {"nodeId": n["nodeId"], "reason": n.get("blockedReason", "")}
        for n in sorted(nodes, key=lambda n: str(n["nodeId"]))
        if n.get("blocked") and n.get("mandatory")
    ]
    return _answer(
        "q.blocked_nodes", blocked, [str(n["nodeId"]) for n in nodes],
        "mandatory nodes preserved as BLOCKED rather than dropped from the DAG",
    )


def _q_resume_readiness(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Can a replacement agent resume from the latest checkpoint?"""
    report = corpus.get("resumeReport")
    if report is None:
        return _answer(
            "q.resume_readiness", None, [], "no resume report",
            available=False, unavailable_reason="the corpus contains no resume report",
        )
    return _answer(
        "q.resume_readiness",
        {
            "resumable": report.get("resumable"),
            "blockers": report.get("blockers", []),
            "retention": report.get("continuityRetention", {}).get("value"),
        },
        [str(report.get("checkpointId"))],
        "resume decision and the required-fact retention behind it",
    )


def _q_efficiency_status(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Is any efficiency claim verified?"""
    evaluations = corpus.get("efficiencyEvaluations", [])
    if not evaluations:
        return _answer(
            "q.efficiency_status",
            {"verifiedClaims": 0, "note": "no efficiency claim has been evaluated"},
            ["registry:metrics"],
            "no matched cohort has been measured, so no leverage figure exists",
        )
    verified = [e for e in evaluations if e.get("verdict") == "APPROVE"]
    return _answer(
        "q.efficiency_status",
        {
            "verifiedClaims": len(verified),
            "blockedClaims": len(evaluations) - len(verified),
            "blockers": sorted({b for e in evaluations for b in e.get("blockers", [])}),
        },
        [str(e.get("metricId")) for e in evaluations],
        "efficiency verification is a separate dimension from software acceptance",
    )


def _q_evidence_closure(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """What fraction of mandatory evidence requirements are closed?"""
    receipts = corpus.get("sufficiencyReceipts", [])
    if not receipts:
        return _answer(
            "q.evidence_closure", None, [], "no sufficiency receipts",
            available=False, unavailable_reason="the corpus contains no sufficiency receipts",
        )
    applicable = sum(int(r.get("mandatoryApplicable", 0)) for r in receipts)
    satisfied = sum(int(r.get("mandatorySatisfied", 0)) for r in receipts)
    if applicable == 0:
        return _answer(
            "q.evidence_closure", None, [str(i) for i in range(len(receipts))],
            "no mandatory applicable requirements",
            available=False, unavailable_reason="zero mandatory applicable requirements",
        )
    return _answer(
        "q.evidence_closure",
        {"satisfied": satisfied, "applicable": applicable, "fraction": satisfied / applicable},
        [str(r.get("recordType", "receipt")) + ":" + str(index)
         for index, r in enumerate(receipts)],
        "mandatory evidence requirements satisfied over those applicable",
    )


def _q_release_dimensions(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """What is accepted, separately, across the four release dimensions?"""
    dimensions = corpus.get("acceptanceByDimension", [])
    if not dimensions:
        return _answer(
            "q.release_dimensions", None, [], "no release manifest",
            available=False, unavailable_reason="the corpus contains no release manifest",
        )
    return _answer(
        "q.release_dimensions",
        {str(d["dimension"]): str(d["status"]) for d in dimensions},
        [str(d["dimension"]) for d in dimensions],
        "software acceptance, efficiency verification, deployment and live qualification "
        "are reported independently",
    )


COMPETENCY_QUERIES: dict[str, tuple[str, Callable[[Mapping[str, Any]], dict[str, Any]]]] = {
    "q.accepted_work": ("How much accepted work closed in this window?", _q_accepted_work),
    "q.refused_credit": ("Which submitted units were refused credit, and why?",
                         _q_which_units_were_not_credited),
    "q.unverified_claims": ("Which mandatory claims are not independently verified?",
                            _q_unverified_claims),
    "q.disagreements": ("Where did the auditor disagree with the producer?",
                        _q_producer_auditor_disagreements),
    "q.resource_unknowns": ("Which resources were not measured?", _q_resource_unknowns),
    "q.blocked_nodes": ("Which mandatory plan nodes have no qualified provider?",
                        _q_blocked_plan_nodes),
    "q.resume_readiness": ("Can a replacement agent resume from the latest checkpoint?",
                           _q_resume_readiness),
    "q.efficiency_status": ("Is any efficiency claim verified?", _q_efficiency_status),
    "q.evidence_closure": ("What fraction of mandatory evidence requirements are closed?",
                           _q_evidence_closure),
    "q.release_dimensions": ("What is accepted across the four release dimensions?",
                             _q_release_dimensions),
}


def query_ids() -> tuple[str, ...]:
    return tuple(row['queryId'] for row in competency_corpus()['questions'])


def answer(query_id: str, corpus: Mapping[str, Any]) -> dict[str, Any]:
    if query_id not in COMPETENCY_QUERIES:
        raise QueryError("no competency query named " + repr(query_id))
    question, handler = COMPETENCY_QUERIES[query_id]
    result = handler(corpus)
    result["question"] = question
    return result


def competency_corpus() -> dict[str, Any]:
    return json.loads((Path(__file__).resolve().parents[3] / 'registries/competency_corpus.json').read_text(encoding='utf-8'))


def _missing(query_id, corpus, key, reason):
    if key not in corpus or not corpus[key]:
        return _answer(query_id, None, [str(corpus['corpusId'])] if corpus.get('corpusId') else [],
                       'UNAVAILABLE', available=False, unavailable_reason=reason)
    return None


def _q_capability_ranking(corpus):
    missing = _missing('q.capability_ranking', corpus, 'capabilityMeasurements', 'no accepted capability work with admissible vendor-token observations')
    if missing: return missing
    groups, unavailable = {}, []
    for row in corpus['capabilityMeasurements']:
        usage = row['tokens']
        if usage.get('basis') != 'OBSERVED' or not row.get('accepted') or not row.get('admissible') or Decimal(str(usage['value'])) <= 0:
            unavailable.append(row['receiptId'])
            continue
        domain = row['accountingDomain']
        key = (domain, row['capabilityId'])
        work, tokens = groups.get(key, (Decimal(0), Decimal(0)))
        groups[key] = (work + Decimal(str(row['acceptedWeightedWork'])), tokens + Decimal(str(usage['value'])))
    rankings = [{'accountingDomain': domain, 'capabilityId': capability, 'workPerToken': str(work / tokens)}
                for (domain, capability), (work, tokens) in sorted(groups.items())]
    rankings.sort(key=lambda r: (r['accountingDomain'], -Decimal(r['workPerToken']), r['capabilityId']))
    return _answer('q.capability_ranking', {'rankingsWithinDomain': rankings, 'excluded': sorted(unavailable),
                   'notComparableAcrossDomains': sorted({k[0] for k in groups})},
                   [r['receiptId'] for r in corpus['capabilityMeasurements']], 'aggregate accepted weighted work / observed tokens; no cross-domain ranking')


def _q_equivalent_lower_cost(corpus):
    missing = _missing('q.equivalent_lower_cost', corpus, 'implementationComparisons', 'no frozen equivalent-output implementation comparisons')
    if missing: return missing
    rows = []
    for r in sorted(corpus['implementationComparisons'], key=lambda r: r['receiptId']):
        e = r['evaluation']
        m = e.get('measurement', {})
        if e.get('verdict') == 'APPROVE' and m.get('availability') == 'AVAILABLE' and Decimal(str(m['value'])) > 1:
            rows.append({'implementationId': r['implementationId'], 'contractId': r['contractId'], 'fullCostRatio': m['value']})
    return _answer('q.equivalent_lower_cost', rows, [r['receiptId'] for r in corpus['implementationComparisons']], 'approved equivalent-output comparisons with a full observed-cost ratio above one')


def _q_session_time(corpus):
    from ..trace.timing import timing_summary
    missing = _missing('q.session_time', corpus, 'traceSpans', 'no instrumented session spans')
    if missing: return missing
    return _answer('q.session_time', timing_summary(corpus['traceSpans']), [s['spanId'] for s in corpus['traceSpans']], 'interval unions, leaf effort, waiting states and labelled verification/rework subsets')


def _q_human_approvals(corpus):
    missing = _missing('q.human_approvals', corpus, 'humanGates', 'no human-judgment gate and candidate-binding records')
    if missing: return missing
    rows = []
    for gate in sorted(corpus['humanGates'], key=lambda g: g['gateId']):
        if gate['humanJudgmentRequired']:
            rows.append({'gateId': gate['gateId'], 'approvals': [dict(a, stale=a['candidateDigest'] != gate['candidateDigest'])
                for a in sorted(gate.get('approvals', []), key=lambda a: a['approvalId'])]})
    return _answer('q.human_approvals', rows, [g['gateId'] for g in corpus['humanGates']], 'human approvals are bound to a candidate; changed candidate makes the approval stale')


def _q_cache_invalidation(corpus):
    from continuity_integrations.cityqa.identity_and_freshness import freshness_decision
    missing = _missing('q.cache_invalidation', corpus, 'cacheRequests', 'no cache dependencies, policy and age observations')
    if missing: return missing
    rows = [dict(requestId=r['requestId'], decision=freshness_decision(r['claimType'], r['observationDomain'], r['policy'],
                bound_inputs=r['boundInputs'], cached_entry_age_seconds=r.get('ageSeconds'), dependency_changed=r.get('changed', [])))
            for r in sorted(corpus['cacheRequests'], key=lambda r: r['requestId'])]
    return _answer('q.cache_invalidation', rows, [r['requestId'] for r in corpus['cacheRequests']], 'recompute reuse from frozen dependencies, explicit age and freshness policy')


def _q_bundle_delta(corpus):
    from ..claims.bundle import materialize
    missing = _missing('q.bundle_delta', corpus, 'bundleComparison', 'no sealed base, delta chain and independently materialized full bundle')
    if missing: return missing
    data = corpus['bundleComparison']
    resolved = materialize(data['base'], data['deltas'])
    before = {r['claimId']: r['revisionDigest'] for r in data['base']['memberIndex']}
    after = {r['claimId']: r['revisionDigest'] for r in resolved['memberIndex']}
    return _answer('q.bundle_delta', {'changedClaimIds': sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k)),
        'materializationEquivalent': resolved['resolvedStateDigest'] == data['full']['resolvedStateDigest'],
        'resolvedStateDigest': resolved['resolvedStateDigest']},
        [data['base']['bundleId'], data['full']['bundleId']] + [d['deltaId'] for d in data['deltas']], 'resolve the delta chain and compare its state digest with the supplied full materialization')


def _q_evidence_dimensions(corpus):
    dimensions = ('savedStateSelfConsistency', 'crossMapShapeEquivalence', 'sitePlacement', 'historicalPersistence')
    evidence = corpus.get('evidenceDimensions', {})
    absent = [d for d in dimensions if d not in evidence]
    if absent:
        return _answer('q.evidence_dimensions', None, [str(corpus['corpusId'])] if corpus.get('corpusId') else [],
            'UNAVAILABLE', available=False, unavailable_reason='no admissible dimension-specific observations for: ' + ', '.join(absent))
    return _answer('q.evidence_dimensions', {d: evidence[d]['status'] for d in dimensions},
        [evidence[d]['witnessRef'] for d in dimensions], 'each evidence dimension stands alone; self-consistency does not establish historical persistence')


def _q_promotion_boundaries(corpus):
    from continuity_audit.evaluate.verdict import evaluate_promotion
    missing = _missing('q.promotion_boundaries', corpus, 'promotionRequests', 'no proposed promotions with bound audit and authority inputs')
    if missing: return missing
    rows = []
    for r in sorted(corpus['promotionRequests'], key=lambda r: r['requestId']):
        decision = evaluate_promotion(r['candidateDigest'], r['audit'], r['policy'], issuer_role=r['issuerRole'])
        rows.append({'requestId': r['requestId'], 'decision': decision,
                     'crossesAuthorityBoundary': r.get('actuatorRole') == r['issuerRole'],
                     'comparisonOnlyProducerResult': r.get('producerResultKind') == 'COMPARISON_ONLY'})
    return _answer('q.promotion_boundaries', rows, [r['requestId'] for r in corpus['promotionRequests']], 'pure promotion policy plus issuer/actuator separation and comparison-only qualification; no actuation')


def _q_legacy_migration(corpus):
    from ..migration.legacy import migrate_record
    missing = _missing('q.legacy_migration', corpus, 'legacyRecords', 'no legacy records and original byte identities')
    if missing: return missing
    rows = [migrate_record(r['record'], record_type=r['recordType'], source_path=r['sourcePath'],
                          synthetic=r['synthetic']) for r in sorted(corpus['legacyRecords'], key=lambda r: r['receiptId'])]
    return _answer('q.legacy_migration', rows, [r['receiptId'] for r in corpus['legacyRecords']], 'migration preserves producer status, original identity, authority ceiling and synthetic qualification')


_NEW_HANDLERS = {f'q.{name}': handler for name, handler in (
    ('capability_ranking', _q_capability_ranking), ('equivalent_lower_cost', _q_equivalent_lower_cost),
    ('session_time', _q_session_time), ('human_approvals', _q_human_approvals),
    ('cache_invalidation', _q_cache_invalidation), ('bundle_delta', _q_bundle_delta),
    ('evidence_dimensions', _q_evidence_dimensions), ('promotion_boundaries', _q_promotion_boundaries),
    ('legacy_migration', _q_legacy_migration))}
for _row in competency_corpus()['questions']:
    _id = _row['queryId']
    COMPETENCY_QUERIES[_id] = (_row['question'], _NEW_HANDLERS[_id] if _id in _NEW_HANDLERS else COMPETENCY_QUERIES[_id][1])
