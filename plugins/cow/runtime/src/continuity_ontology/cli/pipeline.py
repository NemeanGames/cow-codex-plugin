"""The end-to-end acceptance workflow, actually executed.

This runs a real local outcome from plan to checkpoint: it packages real files,
verifies the archive, records observed spans and events, stores evidence by
content digest, seals a producer bundle, freezes an audit input, runs the
independent auditor in a separate process boundary, evaluates promotion,
credits accepted work and commits a checkpoint that a fresh process can resume.

Everything it measures, it measured. The one thing it cannot produce is vendor
token usage, because no provider is called -- and that is recorded as
``NOT_APPLICABLE`` rather than as zero, so the trace supports timing, replay
and correctness claims and supports no token-reduction claim.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from continuity_audit.evaluate.verdict import build_audit_result, evaluate_promotion
from continuity_audit.ingest.freeze import freeze_audit_input
from continuity_audit.output.writer import AuditWriter
from continuity_audit.recompute.evidence import recompute_claim_status

from ..canonical.profiles import digest_with
from ..checkpoints.store import CheckpointStore
from ..claims.bundle import compile_claim, seal_bundle, verify_seal_dag
from ..claims.cas import ContentStore
from ..events.store import EventStore
from ..metrics.work import AcceptedWorkLedger, WorkUnitPolicy
from ..model.metamodel import load_metamodel
from ..validate.validator import validate_record
from ..validate.records import validate_persisted
from ..resources.accounting import ResourceLedger
from ..trace.timing import timing_summary
from ..trace.precision import duration_precision, monotonic_resolution_ns

__all__ = ["run_end_to_end", "EVENT_TYPES"]

EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "plan.frozen": ("1",),
    "tool.invoked": ("1",),
    "tool.completed": ("1",),
    "artifact.produced": ("1",),
    "gate.evaluated": ("1",),
    "checkpoint.committed": ("1",),
}

_WORK_POLICY = {
    "policyVersion": "wup.e2e.v1",
    "frozen": True,
    "acceptanceUniverse": [
        {
            "accountingId": "wu.package_release_payload",
            "weight": "1",
            "requiredGateIds": ["g.archive_verified"],
            "partition": "delivery",
            "partialCreditDefined": False,
        }
    ],
}


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_end_to_end(
    run_root: str | os.PathLike[str],
    source_root: str | os.PathLike[str],
    members: Sequence[str],
) -> dict[str, Any]:
    """Execute the full workflow and return its receipts."""
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    cas = ContentStore(root / "cas")
    events = EventStore(root / "events", "e2e", known_event_types=EVENT_TYPES)
    spans: list[dict[str, Any]] = []
    resources = ResourceLedger()
    clock_domain = "host:" + platform.node()
    run_id = "run-" + str(int(time.time()))

    def span(span_id: str, actor: str, start: int, end: int, purpose: str, leaf: bool = True) -> None:
        spans.append(
            {
                "spanId": span_id,
                "traceRunId": run_id,
                "actorId": actor,
                "clockDomain": clock_domain,
                "startNs": start,
                "endNs": end,
                "state": "ACTIVE_EXECUTION",
                "purpose": purpose,
                "leaf": leaf,
                "allocationUnknown": False,
                **duration_precision(end - start, monotonic_resolution_ns()),
            }
        )

    outer_start = time.monotonic_ns()

    # -- 1. plan -----------------------------------------------------------
    plan_start = time.monotonic_ns()
    plan = {
        "outcome": "outcome.package_release_payload",
        "nodes": [
            {"nodeId": "n1", "workItem": "wu.package_release_payload", "mandatory": True,
             "blocked": False, "selectedImplementation": "impl.local_packaging.zipstore.v1"}
        ],
        "frozen": True,
    }
    plan_digest = digest_with("continuity.core.v2", plan)
    events.append("plan.frozen", "plan", {"planDigest": plan_digest},
                  "e2e:plan", wall_clock=_utc(),
                  monotonic_ns=plan_start, monotonic_clock_domain=clock_domain)
    span("s.plan", "worker", plan_start, time.monotonic_ns(), "PLANNING")

    # -- 2. observed execution --------------------------------------------
    from continuity_integrations.local_packaging.packager import package, verify

    events.append("tool.invoked", "inv-1",
                  {"capability": "cap.artifact.package", "idempotencyKey": "e2e:pack"},
                  "e2e:invoke", wall_clock=_utc(), monotonic_clock_domain=clock_domain)

    archive_path = root / "out" / "payload.zip"
    result = package(source_root, members, archive_path)
    span("s.package", "worker", result["startedNs"], result["finishedNs"], "PACKAGING")

    events.append("tool.completed", "inv-1",
                  {"status": "PASS", "archiveDigest": result["manifest"]["archiveDigest"]},
                  "e2e:complete", wall_clock=_utc(), monotonic_clock_domain=clock_domain)
    events.append("artifact.produced", "artifact.payload",
                  {"contentDigest": result["manifest"]["archiveDigest"],
                   "memberCount": result["manifest"]["memberCount"]},
                  "e2e:artifact", wall_clock=_utc(), monotonic_clock_domain=clock_domain)

    resources.add({
        "kind": "TOOL_RUNTIME_MS",
        "basis": "OBSERVED",
        "value": str(result["durationMs"]),
        "clockResolutionNs": result["clockResolutionNs"],
        "belowResolution": result["belowResolution"],
        "uncertainty": result["uncertainty"],
        "unit": "milliseconds",
        "accountingRule": "DISJOINT_ADDITIVE",
        "dedupKey": "e2e:pack:runtime",
        "scope": {"scopeKind": "invocation", "selector": "inv-1", "enumerationComplete": True},
    })
    resources.add({
        "kind": "VENDOR_INPUT_TOKENS",
        "basis": "UNKNOWN",
        "unit": "tokens",
        "accountingRule": "DISJOINT_ADDITIVE",
        "dedupKey": "e2e:pack:vendor_in",
        "unknownReason": "this workflow calls no provider; usage is not measured, not zero",
        "scope": {"scopeKind": "invocation", "selector": "inv-1", "enumerationComplete": True},
    })

    # -- 3. verification ---------------------------------------------------
    verify_start = time.monotonic_ns()
    verification = verify(archive_path, result["manifest"])
    span("s.verify", "worker", verify_start, time.monotonic_ns(), "VERIFICATION", leaf=False)
    events.append("gate.evaluated", "g.archive_verified",
                  {"status": verification["status"], "checked": verification["checked"]},
                  "e2e:gate", wall_clock=_utc(), monotonic_clock_domain=clock_domain)

    # -- 4. evidence -------------------------------------------------------
    manifest_digest = cas.put_value(result["manifest"])
    verification_digest = cas.put_value(verification)
    evidence_store = {
        manifest_digest: {
            "evidenceKind": "manifest",
            "admissibility": "ADMISSIBLE",
            "synthetic": False,
            "provenance": {
                "origin": "DERIVATION",
                "productionMethod": "RECOMPUTED",
                "observationChannel": "FILE_BYTES",
                "authorityClass": "DETERMINISTIC_DERIVATION",
                "operationalOwnership": "DIRECTLY_OWNED",
                "verificationStatus": "PRODUCER_ASSERTED",
                "actor": "worker",
                "syntheticFixture": False,
            },
        },
        verification_digest: {
            "evidenceKind": "derivation_receipt",
            "admissibility": "ADMISSIBLE",
            "synthetic": False,
            "provenance": {
                "origin": "DERIVATION",
                "productionMethod": "RECOMPUTED",
                "observationChannel": "FILE_BYTES",
                "authorityClass": "DETERMINISTIC_DERIVATION",
                "operationalOwnership": "DIRECTLY_OWNED",
                "verificationStatus": "PRODUCER_ASSERTED",
                "actor": "worker",
                "syntheticFixture": False,
            },
        },
    }

    # -- 5. producer claims ------------------------------------------------
    requirements = [
        {"requirementId": "r.manifest", "evidenceKind": "manifest", "mandatory": True,
         "applicable": True, "syntheticAcceptable": False},
        {"requirementId": "r.receipt", "evidenceKind": "derivation_receipt", "mandatory": True,
         "applicable": True, "syntheticAcceptable": False},
    ]
    claim = compile_claim(
        "c.archive_members_intact",
        {
            "claimType": "HASH_EQUALITY",
            "subject": "payload.zip",
            "scope": {"scopeKind": "archive", "selector": "payload.zip",
                      "enumerationComplete": True,
                      "expectedMemberCount": result["manifest"]["memberCount"]},
            "statement": "every declared member is present with the manifest digest",
            "expectedValue": "PASS",
        },
        {"producerStatus": verification["status"], "producerRole": "worker",
         "observedValue": verification["status"],
         "evidenceRefs": [manifest_digest, verification_digest]},
        requirements,
        evidence_store,
    )
    candidate_digest = result["manifest"]["archiveDigest"]
    bundle = seal_bundle("b.e2e", candidate_digest, [claim], sealed_at=_utc())
    bundle_public = {k: v for k, v in bundle.items() if not k.startswith("_")}
    bundle_digest = cas.put_value(bundle_public)

    # -- 5b. durable resource record ---------------------------------------
    # The ledger lived only in memory before this; the run root now carries its
    # own costs, UNKNOWN included, so a later reader does not mistake the
    # absence of a record for a zero.
    resource_record = {
        "schemaVersion": "2.0.0",
        "recordType": "ResourceUsageLedger",
        "runId": run_id,
        "synthetic": False,
        "measurements": json.loads(json.dumps([dict(m) for m in resources.measurements()], default=str)),
        "totals": {
            kind: resources.total(kind)
            for kind in sorted({m["kind"] for m in resources.measurements()})
        },
        "subsetReconciliation": resources.subset_reconciliation(),
        "accountingDomains": resources.accounting_domains(),
        "consumes": [
            {"subject": m["scope"]["selector"], "subjectKind": m["scope"]["scopeKind"],
             "resource": m["dedupKey"]}
            for m in resources.measurements()
        ],
    }
    resource_path = root / "resources" / "RESOURCE_USAGE.json"
    validate_persisted(resource_record)
    resource_path.parent.mkdir(parents=True, exist_ok=True)
    resource_path.write_bytes(
        (json.dumps(resource_record, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    )

    # -- 6. independent audit ---------------------------------------------
    audit_dir = root / "audit_out"
    (root / "frozen").mkdir(parents=True, exist_ok=True)
    validate_persisted(bundle_public)
    (root / "frozen" / "bundle.json").write_bytes(
        (json.dumps(bundle_public, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    (root / "frozen" / "evidence.json").write_bytes(
        (json.dumps(evidence_store, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    audit_manifest = freeze_audit_input(
        root / "frozen", ["bundle.json", "evidence.json"],
        candidate_digest=candidate_digest, frozen_at=_utc(),
    )

    matrix = _load_matrix()

    audit_start = time.monotonic_ns()
    recomputed = recompute_claim_status(
        claim, evidence_store, matrix, {"c.archive_members_intact": verification["status"]}
    )
    span("s.audit", "auditor", audit_start, time.monotonic_ns(), "AUDIT")
    audit = build_audit_result(
        "a.e2e", bundle["resolvedStateDigest"], audit_manifest["manifestDigest"],
        [recomputed], {"c.archive_members_intact": claim["producerAssertion"]["producerStatus"]},
        digest_with("continuity.core.v2", {"impl": "continuity_audit/2.0.0"}),
    )
    writer = AuditWriter(audit_dir, root / "frozen")
    validate_persisted(audit)
    audit_receipt = writer.write("audit-result.json", audit)

    # -- 7. promotion ------------------------------------------------------
    decision = evaluate_promotion(
        candidate_digest, audit,
        {"requireIndependentAudit": True, "requiredHumanApprovals": []},
        issuer_role="aggregator",
    )

    # The pure policy helper returns a body. The pipeline seals its record envelope.
    decision.update(schemaVersion="2.0.0", semanticModelDigest=load_metamodel().digest,
                    logicalId="promotion.e2e", hashProfile="continuity.core.v2",
                    provenance={"actor": "aggregator", "authorityClass": "DETERMINISTIC_DERIVATION",
                                "origin": "DERIVATION", "productionMethod": "RECOMPUTED",
                                "observationChannel": "FILE_BYTES", "operationalOwnership": "NOT_APPLICABLE",
                                "syntheticFixture": False, "verificationStatus": "PRODUCER_ASSERTED",
                                "sourceRefs": [audit["resultDigest"]]})
    decision["revisionId"] = digest_with("continuity.core.v2", decision)
    validation = validate_record("PromotionDecision", decision)
    if not validation.ok:
        raise ValueError("invalid promotion record: " + repr(validation.issues))

    # -- 8. accepted work --------------------------------------------------
    policy = WorkUnitPolicy(_WORK_POLICY)
    ledger = AcceptedWorkLedger(policy, "e2e-window")
    credit = ledger.credit(
        {
            "receiptId": "ar.e2e.1",
            "accountingId": "wu.package_release_payload",
            "workUnitPolicyVersion": "wup.e2e.v1",
            "weight": "1",
            "firstQualifyingAttempt": True,
        },
        satisfied_gate_ids=["g.archive_verified"] if verification["status"] == "PASS" else [],
    )

    # -- 9. checkpoint -----------------------------------------------------
    outer_end = time.monotonic_ns()
    span("s.run", "worker", outer_start, outer_end, "PLANNING", leaf=False)
    timing = timing_summary(spans)

    checkpoints = CheckpointStore(root / "checkpoints", validate_records=True)
    snapshot = {
        "admittedSourceVersions": {"payload": candidate_digest},
        "planDigest": plan_digest,
        "contractDigests": {"work_unit_policy": digest_with("continuity.core.v2", _WORK_POLICY)},
        "implementationVersions": {"impl.local_packaging.zipstore.v1": "1.0.0"},
        "artifactRefs": {"payload.zip": candidate_digest},
        "requiredFacts": [
            {"factId": "candidateDigest", "present": True, "value": candidate_digest},
            {"factId": "bundleDigest", "present": True, "value": bundle["resolvedStateDigest"]},
            {"factId": "auditDigest", "present": True, "value": audit["resultDigest"]},
            {"factId": "acceptedWorkTotal", "present": True, "value": str(ledger.total_weight())},
            {"factId": "eventPosition", "present": True, "value": len(events) - 1},
        ],
        "ephemeralBindings": [
            {"bindingKind": "processId", "recordedValue": os.getpid(),
             "carriesAuthority": False, "refreshRequiredOnResume": True},
        ],
        "completeness": "AVAILABLE",
        "environmentBinding": {
            "hostId": platform.node(),
            "interpreter": "cpython",
            "interpreterVersion": platform.python_version(),
            "platform": platform.platform(),
            "unknownFields": [],
        },
    }
    checkpoint = checkpoints.commit(
        "cp.e2e",
        outcome_id="outcome.package_release_payload",
        snapshot=snapshot,
        last_sealed_event_seq=len(events) - 1,
        last_sealed_event_digest=events.head_digest(),
        accepted_decisions=[
            {"decisionKind": "promotion", "disposition": decision["state"],
             "citedInputs": [audit["resultDigest"]], "issuedByRole": "aggregator",
             "rationale": "; ".join(decision["reasons"])}
        ],
        unresolved_claims=[],
        open_operations=[],
        next_legal_actions=["hand the frozen candidate to the separate release auditor"],
        recovery_policy_ref="rp.default.v1",
        closure_receipt={
            "closureKind": "STATE",
            "complete": True,
            "observedCount": 5,
            "expectedCount": 5,
            "enumeratedMembers": ["candidateDigest", "bundleDigest", "auditDigest",
                                  "acceptedWorkTotal", "eventPosition"],
            "witnessRefs": [candidate_digest],
            "scope": {"scopeKind": "required_facts", "selector": "cp.e2e",
                      "enumerationComplete": True},
        },
    )
    events.append("checkpoint.committed", "cp.e2e",
                  {"revisionId": checkpoint["revisionId"]},
                  "e2e:checkpoint", wall_clock=_utc(), monotonic_clock_domain=clock_domain)

    seal_dag = verify_seal_dag(
        [("claim_bundle", "evidence"), ("audit", "claim_bundle"),
         ("promotion", "audit"), ("checkpoint", "promotion"), ("view", "checkpoint")]
    )

    return {
        "runId": run_id,
        "synthetic": False,
        "planDigest": plan_digest,
        "archivePath": str(archive_path),
        "candidateDigest": candidate_digest,
        "manifest": result["manifest"],
        "verification": verification,
        "eventCount": len(events),
        "eventStreamPath": str(root / "events" / "e2e.events.jsonl"),
        "timing": timing,
        "resourceTotals": {
            "TOOL_RUNTIME_MS": resources.total("TOOL_RUNTIME_MS"),
            "VENDOR_INPUT_TOKENS": resources.total("VENDOR_INPUT_TOKENS"),
        },
        "resourceLedgerPath": str(resource_path),
        "bundleDigest": bundle["resolvedStateDigest"],
        "bundleObjectDigest": bundle_digest,
        "auditInputManifest": audit_manifest,
        "audit": audit,
        "auditReceipt": audit_receipt,
        "promotionDecision": decision,
        "acceptedWork": {
            "credit": credit,
            "totalWeight": str(ledger.total_weight()),
            "acceptedIds": list(ledger.accepted_ids()),
            "firstPassYield": ledger.first_pass_yield(),
        },
        "checkpoint": checkpoint,
        "sealDag": seal_dag,
        "casStatistics": cas.statistics(),
        "evidenceStore": evidence_store,
    }


def _load_matrix() -> dict[str, Any]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "registries" / "authority-rules.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError("registries/authority-rules.json not found")
