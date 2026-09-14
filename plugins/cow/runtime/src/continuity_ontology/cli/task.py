"""``ont20 task`` -- structure one unit of work through the ontology in three calls.

An agent doing a task should not have to learn the record shapes. It writes a
small manifest naming the outcome, the work item, the evidence files and the
claim, and then:

    ont20 task init   --root ontology --manifest task.json
    ont20 task step   --root ontology <stepId> --status PASS   (once per plan step)
    ont20 task finish --root ontology --manifest task.json

``init`` writes the Outcome, WorkItem and ExecutionPlan and opens the event
stream. ``step`` appends one observed event and one observed span -- the
timing is taken by this process, not asserted by the caller. ``finish`` stores
every evidence file by content digest, compiles the Claim, writes the
ExecutionTrace, commits the Checkpoint, validates every record against the
semantic model and prints the compact status. Detailed records go to disk;
stdout carries a few lines.

Everything here is producer-side. The claim's status is a producer assertion
and is labelled as such; nothing in this module can record a verified result.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cityqa.engine.statuses import ExitCode

from ..canonical.profiles import digest_with
from ..checkpoints.store import CheckpointStore
from ..claims.bundle import compile_claim
from ..claims.cas import ContentStore
from ..events.store import EventStore
from ..model.metamodel import load_metamodel
from ..projection.views import compact_status
from ..validate.validator import RecordValidator

__all__ = ["add_task_parser", "cmd_task_init", "cmd_task_step", "cmd_task_finish", "cmd_task_record"]

PROFILE = "continuity.core.v2"
SCHEMA_VERSION = "2.0.0"

EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "plan.frozen": ("1",),
    "step.completed": ("1",),
    "artifact.produced": ("1",),
    "claim.compiled": ("1",),
    "checkpoint.committed": ("1",),
}

_PURPOSES = ("PLANNING", "RETRIEVAL", "GENERATION", "VERIFICATION", "AUDIT", "PACKAGING", "RECOVERY_REWORK")
_STATUSES = ("PASS", "FAIL", "UNKNOWN", "ERROR", "NOT_RUN")

_MEDIA = {".json": "application/json", ".md": "text/markdown", ".txt": "text/plain",
          ".csv": "text/csv", ".py": "text/x-python"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock_domain() -> str:
    return "host:" + platform.node()


def _emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _provenance(origin: str, authority: str, method: str, channel: str, *,
                actor: str = "worker", source_refs: Sequence[str] | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {
        "actor": actor,
        "origin": origin,
        "authorityClass": authority,
        "productionMethod": method,
        "observationChannel": channel,
        "operationalOwnership": "DIRECTLY_OWNED",
        "verificationStatus": "PRODUCER_ASSERTED",
        "syntheticFixture": False,
    }
    if source_refs:
        p["sourceRefs"] = list(source_refs)
    return p


PROV_ASSERTED = ("HUMAN_INPUT", "CALLER_ASSERTION", "ASSERTED", "NOT_OBSERVED")
PROV_POLICY = ("POLICY", "POLICY_OR_SYNTHETIC_AID", "ASSERTED", "NOT_OBSERVED")
PROV_SOURCE = ("SOURCE_ARTIFACT", "AUTHORITATIVE_SOURCE", "TRANSCRIBED", "FILE_BYTES")
PROV_DERIVED = ("DERIVATION", "DETERMINISTIC_DERIVATION", "RECOMPUTED", "FILE_BYTES")
PROV_MEASURED = ("LIVE_OBSERVATION", "OPERATION_OWNED_RESULT", "MEASURED", "PROCESS_API")


def _bare_events(store: EventStore) -> list[dict[str, Any]]:
    """Event envelopes as nested ExecutionEvent values: without the stream's own record header."""
    return [{k: v for k, v in e.items() if k not in ("recordType", "schemaVersion")} for e in store.events()]


class _Task:
    """Paths and the small cross-call state of one task."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.records = self.root / "records"
        self.state_path = self.root / "task-state.json"
        self.model = load_metamodel()
        self.validator = RecordValidator(self.model)

    # -- state -------------------------------------------------------------

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError("no task has been initialised under " + str(self.root) + "; run `task init` first")
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: Mapping[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def events(self, task_id: str) -> EventStore:
        return EventStore(self.root / "events", task_id, known_event_types=EVENT_TYPES)

    # -- records -----------------------------------------------------------

    def seal(self, record_type: str, logical_id: str, body: Mapping[str, Any],
             provenance: Mapping[str, Any]) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "semanticModelDigest": self.model.digest,
            "recordType": record_type,
            "logicalId": logical_id,
            "hashProfile": PROFILE,
            "provenance": dict(provenance),
            "createdAt": _utc(),
        }
        record.update(body)
        record["revisionId"] = digest_with(PROFILE, record)
        return record

    def write(self, name: str, record: Mapping[str, Any]) -> Path:
        self.records.mkdir(parents=True, exist_ok=True)
        path = self.records / (name + ".json")
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def validate_all(self, named: Sequence[tuple[str, str, Mapping[str, Any]]]) -> dict[str, Any]:
        """Validate every (name, recordType, record) and write validation.json."""
        rows = []
        for name, record_type, record in named:
            result = self.validator.validate(record_type, record)
            rows.append({
                "recordType": record_type,
                "path": "records/" + name + ".json",
                "valid": result.ok,
                "issues": [i.as_dict() for i in result.issues],
            })
        report = {"semanticModelDigest": self.model.digest, "records": rows,
                  "allValid": all(r["valid"] for r in rows)}
        (self.root / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report


def _read_manifest(path: str) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("taskId", "outcome", "workItem", "evidence", "claim", "checkpoint"):
        if key not in manifest:
            raise ValueError("manifest is missing " + repr(key))
    return manifest


def _contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The acceptance contract: given in the manifest, or one predicate from the claim."""
    claim = manifest["claim"]
    given = manifest.get("contract") or {}
    predicates = given.get("predicates") or [{
        "predicateId": "p." + str(claim["id"]).split(".", 1)[-1],
        "subjectPath": "$." + str(claim.get("subject", "artifact")),
        "operator": "EQUAL",
        "expected": claim.get("expectedValue"),
        "mandatory": True,
    }]
    evidence_by_id = {e["id"]: e for e in manifest["evidence"]}
    required = []
    for ev_id in claim.get("evidence", []):
        e = evidence_by_id[ev_id]
        required.append({
            "requirementId": "r." + str(ev_id).split(".", 1)[-1],
            "evidenceKind": e["kind"],
            "mandatory": bool(e.get("required", True)),
            "minimumAuthorityClasses": ["AUTHORITATIVE_SOURCE" if e.get("source") else "DETERMINISTIC_DERIVATION"],
            "syntheticAcceptable": False,
        })
    return {
        "name": given.get("name") or str(manifest["taskId"]),
        "contractVersion": given.get("contractVersion", "1.0.0"),
        "predicates": predicates,
        "requiredEvidence": required,
        "scope": list(given.get("scope") or manifest["outcome"].get("subjectUniverse", [])),
    }


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def _manifest_for(args: argparse.Namespace) -> dict[str, Any]:
    preloaded = getattr(args, "_manifest_obj", None)
    return dict(preloaded) if preloaded is not None else _read_manifest(args.manifest)


def cmd_task_init(args: argparse.Namespace) -> int:
    task = _Task(args.root)
    manifest = _manifest_for(args)
    task_id = str(manifest["taskId"])
    if task.state_path.exists():
        _emit({"status": "ERROR", "reason": "task already initialised under " + str(task.root)})
        return ExitCode.ERROR

    outcome_m, work_m = manifest["outcome"], manifest["workItem"]
    contract = _contract(manifest)
    evidence_kinds = sorted({e["kind"] for e in manifest["evidence"]})

    outcome = task.seal("Outcome", outcome_m["id"], {
        "title": outcome_m["title"],
        "requestedResult": outcome_m["requestedResult"],
        "lifecycle": "RUNNING",
        "subjectUniverse": list(outcome_m.get("subjectUniverse", [])),
        "requiredArtifactKinds": list(outcome_m.get("requiredArtifacts", [])),
        "requiredEvidenceKinds": evidence_kinds,
        "acceptanceCriteria": [contract],
        "workUnitPolicyRef": outcome_m.get("workUnitPolicyRef", "wup." + task_id + ".v1"),
    }, _provenance(*PROV_ASSERTED))

    work_item = task.seal("WorkItem", work_m["id"], {
        "title": work_m["title"],
        "parentOutcome": outcome_m["id"],
        "accountingId": work_m["id"],
        "accountingPartition": work_m.get("partition", task_id),
        "lifecycle": "RUNNING",
        "contracts": [contract],
        "requiredCapabilities": [work_m["capability"]],
        "permittedSideEffects": list(work_m.get("permittedSideEffects", ["local_write:" + str(task.root.parent)])),
    }, _provenance(*PROV_ASSERTED))

    impl = work_m.get("implementation", "impl." + task_id + ".v1")
    plan_id = "plan." + task_id
    plan = task.seal("ExecutionPlan", plan_id, {
        "outcome": outcome_m["id"],
        "frozen": True,
        "nodes": [{"nodeId": "n1", "workItem": work_m["id"], "mandatory": True,
                   "blocked": False, "selectedImplementation": impl}],
        "selectionReceipts": [{
            "nodeId": "n1", "blocked": False, "candidateUniverse": [impl],
            "hardPredicates": [], "prunedCandidates": [],
            "rankedCandidates": [{"candidateId": impl, "score": "1"}],
            "terminalDecisionByCandidate": {impl: "SELECTED"},
            "quantization": 0, "tieBreak": "single_candidate", "committed": impl,
        }],
    }, _provenance(*PROV_POLICY))

    for name, rec in (("outcome", outcome), ("work_item", work_item), ("plan", plan)):
        task.write(name, rec)

    now = int(getattr(args, "_start_ns", None) or time.monotonic_ns())
    events = task.events(task_id)
    events.append("plan.frozen", plan_id,
                  {"planDigest": plan["revisionId"], "outcome": outcome_m["id"], "workItem": work_m["id"]},
                  task_id + ":plan", wall_clock=_utc(), monotonic_ns=now,
                  monotonic_clock_domain=_clock_domain())

    run_id = "run-" + task_id + "-" + str(int(time.time()))
    task.save_state({
        "taskId": task_id, "runId": run_id, "planId": plan_id,
        "planDigest": plan["revisionId"], "contractDigest": digest_with(PROFILE, contract),
        "outcomeId": outcome_m["id"], "workItemId": work_m["id"], "implementation": impl,
        "clockDomain": _clock_domain(), "startNs": now, "lastNs": now,
        "steps": [],
        "python": sys.executable,
    })
    _emit({"status": "PASS", "runId": run_id, "records": 3, "events": len(events),
           "next": "run each plan step, then `task step <id> --status PASS` after it"})
    return ExitCode.PASS


# ---------------------------------------------------------------------------
# step
# ---------------------------------------------------------------------------

def cmd_task_step(args: argparse.Namespace) -> int:
    task = _Task(args.root)
    state = task.load_state()
    if any(s["stepId"] == args.step_id for s in state["steps"]):
        _emit({"status": "ERROR", "reason": "step " + repr(args.step_id) + " was already recorded"})
        return ExitCode.ERROR
    now = time.monotonic_ns()
    payload: dict[str, Any] = {"stepId": args.step_id, "status": args.status}
    if args.note:
        payload["note"] = args.note
    events = task.events(state["taskId"])
    event = events.append("step.completed", args.step_id, payload,
                          state["taskId"] + ":step:" + args.step_id,
                          wall_clock=_utc(), monotonic_ns=now, monotonic_clock_domain=state["clockDomain"])
    state["steps"].append({
        "stepId": args.step_id, "status": args.status, "purpose": args.purpose,
        "startNs": state["lastNs"], "endNs": now, "eventId": event["eventId"],
    })
    state["lastNs"] = now
    task.save_state(state)
    _emit({"status": args.status, "step": args.step_id, "seq": event["sequence"],
           "elapsedMs": round((now - state["steps"][-1]["startNs"]) / 1e6, 1)})
    return ExitCode.PASS if args.status == "PASS" else ExitCode.FAIL


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------

def cmd_task_finish(args: argparse.Namespace) -> int:
    task = _Task(args.root)
    state = task.load_state()
    if state.get("finishedAt"):
        _emit({"status": "ERROR", "reason": "task was already finished at " + state["finishedAt"]
               + "; its records are under " + str(task.records) + " and the event chain is sealed"})
        return ExitCode.ERROR
    manifest = _manifest_for(args)
    task_id = state["taskId"]
    base = Path(getattr(args, "_base", None) or Path(args.manifest).resolve().parent)
    domain = state["clockDomain"]
    run_id = state["runId"]

    claim_m = dict(manifest["claim"])
    if args.claim_values:
        claim_m.update(json.loads(Path(args.claim_values).read_text(encoding="utf-8")))
    if args.producer_status:
        claim_m["producerStatus"] = args.producer_status
    producer_status = str(claim_m.get("producerStatus", "UNKNOWN"))

    # -- evidence: every listed file, stored by content digest -------------
    cas = ContentStore(task.root / "cas")
    ev_digest: dict[str, str] = {}
    ev_records: list[tuple[str, dict[str, Any]]] = []
    ev_store: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    missing = []
    for e in manifest["evidence"]:
        path = base / e["path"]
        if not path.exists():
            missing.append(e["path"])
            continue
        digest = cas.put_file(path)
        ev_digest[e["id"]] = digest
    if missing:
        _emit({"status": "FAIL", "reason": "evidence file(s) not found: " + ", ".join(missing)})
        return ExitCode.FAIL
    events = task.events(task_id)
    for e in manifest["evidence"]:
        path = base / e["path"]
        digest = ev_digest[e["id"]]
        derived_from = [ev_digest[d] for d in e.get("derivedFrom", []) if d in ev_digest]
        is_source = bool(e.get("source"))
        prov = _provenance(*(PROV_SOURCE if is_source else PROV_DERIVED), source_refs=derived_from or None)
        record = task.seal("Evidence", e["id"], {
            "evidenceKind": e["kind"],
            "subject": e["path"],
            "contentDigest": digest,
            "admissibility": "ADMISSIBLE",
            "method": e.get("method", ("source bytes read from disk" if is_source
                                       else "derived by the task's own script from its declared sources")),
            "scope": {"scopeKind": "file", "selector": e["path"], "enumerationComplete": True},
            "supportsClaimTypes": list(e.get("claimTypes", [claim_m["claimType"]] if not is_source else [claim_m["claimType"], "HASH_EQUALITY"])),
        }, prov)
        ev_records.append((e["id"].replace(".", "_"), record))
        ev_store[digest] = {"evidenceKind": e["kind"], "admissibility": "ADMISSIBLE", "synthetic": False, "provenance": prov}
        version = {"artifact": e["path"], "contentDigest": digest, "sizeBytes": path.stat().st_size,
                   "mediaType": _MEDIA.get(path.suffix.lower(), "application/octet-stream")}
        if is_source:
            sources.append(version)
        else:
            if derived_from:
                version["directlyDerivedFrom"] = derived_from
            artifacts.append(version)
            events.append("artifact.produced", e["path"], {"contentDigest": digest, "sizeBytes": version["sizeBytes"]},
                          task_id + ":artifact:" + e["id"], wall_clock=_utc(),
                          monotonic_ns=time.monotonic_ns(), monotonic_clock_domain=domain)

    # -- claim ---------------------------------------------------------------
    contract = _contract(manifest)
    proposition = {
        "claimType": claim_m["claimType"],
        "subject": claim_m["subject"],
        "statement": claim_m["statement"],
        "scope": dict(claim_m.get("scope") or {"scopeKind": "file", "selector": claim_m["subject"], "enumerationComplete": True}),
    }
    if "expectedValue" in claim_m:
        proposition["expectedValue"] = claim_m["expectedValue"]
    claim_refs = [ev_digest[i] for i in claim_m.get("evidence", []) if i in ev_digest]
    assertion: dict[str, Any] = {
        "producerStatus": producer_status,
        "producerRole": "worker",
        "evidenceRefs": claim_refs,
        "proposition": proposition,
        "note": "PRODUCER ASSERTION: the producer computed and self-checked this; it carries no verification authority and has not been independently audited.",
    }
    if "observedValue" in claim_m:
        assertion["observedValue"] = claim_m["observedValue"]
    compiled = compile_claim(claim_m["id"], proposition, assertion, contract["requiredEvidence"], ev_store)
    claim_body = {k: v for k, v in compiled.items() if k != "recordType"}
    claim_body["sufficiency"] = {k: v for k, v in compiled["sufficiency"].items() if k != "recordType"}
    claim = task.seal("Claim", claim_m["id"], claim_body, _provenance(*PROV_DERIVED, source_refs=claim_refs or None))
    events.append("claim.compiled", claim_m["id"],
                  {"claimDigest": claim["revisionId"], "producerStatus": producer_status,
                   "sufficient": bool(compiled["sufficiency"].get("closed"))},
                  task_id + ":claim", wall_clock=_utc(), monotonic_ns=time.monotonic_ns(), monotonic_clock_domain=domain)

    # -- trace -------------------------------------------------------------
    end_ns = time.monotonic_ns()
    spans = [{
        "spanId": "s." + s["stepId"], "traceRunId": run_id, "actorId": "worker", "clockDomain": domain,
        "startNs": s["startNs"], "endNs": s["endNs"], "state": "ACTIVE_EXECUTION",
        "purpose": s["purpose"], "leaf": True, "parentSpanId": "s.run", "allocationUnknown": False,
    } for s in state["steps"]]
    spans.append({"spanId": "s.run", "traceRunId": run_id, "actorId": "worker", "clockDomain": domain,
                  "startNs": state["startNs"], "endNs": end_ns, "state": "ACTIVE_EXECUTION",
                  "purpose": "GENERATION", "leaf": False, "allocationUnknown": False})
    step_statuses = [s["status"] for s in state["steps"]]
    terminal = "FAIL" if "FAIL" in step_statuses or producer_status == "FAIL" else (
        "ERROR" if "ERROR" in step_statuses else ("PASS" if step_statuses else "NOT_RUN"))
    env = {
        "hostId": platform.node(), "interpreter": platform.python_implementation().lower(),
        "interpreterVersion": platform.python_version(), "platform": platform.platform(),
        "processCreation": {"pid": os.getpid(), "executablePath": sys.executable},
        "unknownFields": ["moduleClosureDigest"],
    }
    resources = [
        {"kind": "TOOL_RUNTIME_MS", "basis": "OBSERVED", "unit": "milliseconds", "accountingRule": "DISJOINT_ADDITIVE",
         "dedupKey": run_id + ":runtime", "value": str(round((end_ns - state["startNs"]) / 1e6, 3)),
         "scope": {"scopeKind": "run", "selector": run_id, "enumerationComplete": True}},
        {"kind": "VENDOR_INPUT_TOKENS", "basis": "UNKNOWN", "unit": "tokens", "accountingRule": "DISJOINT_ADDITIVE",
         "dedupKey": run_id + ":vendor_in",
         "unknownReason": "the task CLI calls no provider; the agent's own usage is measured from its transcript, not here",
         "scope": {"scopeKind": "run", "selector": run_id, "enumerationComplete": True}},
    ]
    trace_body = {
        "runId": run_id, "attempt": 1, "plan": state["planId"], "workItem": state["workItemId"],
        "capability": manifest["workItem"]["capability"], "implementation": state["implementation"],
        "actualActor": "worker:" + task_id, "issuer": manifest.get("issuer", "agent"),
        "mutationScopeDeclared": True, "environmentBinding": env,
        "consumedArtifacts": sources, "producedArtifacts": artifacts,
        "events": _bare_events(events), "spans": spans, "resourceUsage": resources,
        "terminalStatus": terminal,
    }

    # -- checkpoint ----------------------------------------------------------
    cp_m = manifest["checkpoint"]
    facts = dict(cp_m.get("requiredFacts", {}))
    facts.update({"claimDigest": claim["revisionId"], "eventPosition": len(events) - 1})
    witnesses = [ev_digest[e["id"]] for e in manifest["evidence"] if not e.get("source")] or list(ev_digest.values())
    snapshot = {
        "admittedSourceVersions": {e["path"]: ev_digest[e["id"]] for e in manifest["evidence"] if e.get("source")},
        "artifactRefs": {e["path"]: ev_digest[e["id"]] for e in manifest["evidence"] if not e.get("source")},
        "planDigest": state["planDigest"],
        "contractDigests": {contract["name"]: state["contractDigest"]},
        "implementationVersions": {state["implementation"]: "1.0.0"},
        "requiredFacts": [{"factId": k, "present": True, "value": v} for k, v in facts.items()],
        "ephemeralBindings": [{"bindingKind": "processId", "recordedValue": os.getpid(),
                               "carriesAuthority": False, "refreshRequiredOnResume": True}],
        "completeness": "AVAILABLE",
        "environmentBinding": env,
    }
    checkpoint = CheckpointStore(task.root / "checkpoints").commit(
        cp_m["id"], outcome_id=state["outcomeId"], snapshot=snapshot,
        last_sealed_event_seq=len(events) - 1, last_sealed_event_digest=events.head_digest(),
        accepted_decisions=[{
            "decisionKind": "producer_self_check", "disposition": producer_status, "issuedByRole": "worker",
            "citedInputs": [claim["revisionId"]],
            "rationale": "producer-side status of claim " + claim_m["id"] + "; NOT an independent verification",
        }],
        unresolved_claims=[claim_m["id"]],
        open_operations=[],
        next_legal_actions=list(cp_m.get("nextLegalActions", ["hand the claim and its evidence to the independent auditor"])),
        recovery_policy_ref=cp_m.get("recoveryPolicyRef", "rp.default.v1"),
        closure_receipt={
            "closureKind": "STATE", "complete": True,
            "enumeratedMembers": list(facts), "expectedCount": len(facts), "observedCount": len(facts),
            "witnessRefs": witnesses,
            "scope": {"scopeKind": "required_facts", "selector": cp_m["id"], "enumerationComplete": True},
        },
    )
    events.append("checkpoint.committed", cp_m["id"], {"revisionId": checkpoint["revisionId"]},
                  task_id + ":checkpoint", wall_clock=_utc(), monotonic_ns=time.monotonic_ns(),
                  monotonic_clock_domain=domain)
    trace_body["events"] = _bare_events(events)
    trace = task.seal("ExecutionTrace", run_id, trace_body, _provenance(*PROV_MEASURED))

    # the checkpoint store's record lacks the identity envelope; the sealed copy carries it
    cp_body = {k: v for k, v in checkpoint.items()
               if k not in ("schemaVersion", "recordType", "logicalId", "hashProfile", "revisionId")}
    checkpoint_record = task.seal("Checkpoint", cp_m["id"], cp_body,
                                  _provenance(*PROV_DERIVED, source_refs=witnesses))

    # -- write, validate, project --------------------------------------------
    named: list[tuple[str, str, Mapping[str, Any]]] = [
        ("outcome", "Outcome", json.loads((task.records / "outcome.json").read_text(encoding="utf-8"))),
        ("work_item", "WorkItem", json.loads((task.records / "work_item.json").read_text(encoding="utf-8"))),
        ("plan", "ExecutionPlan", json.loads((task.records / "plan.json").read_text(encoding="utf-8"))),
    ]
    for name, rec in ev_records:
        task.write("evidence_" + name, rec)
        named.append(("evidence_" + name, "Evidence", rec))
    task.write("claim", claim)
    task.write("execution_trace", trace)
    task.write("checkpoint", checkpoint_record)
    named += [("claim", "Claim", claim), ("execution_trace", "ExecutionTrace", trace),
              ("checkpoint", "Checkpoint", checkpoint_record)]
    report = task.validate_all(named)

    blockers = [r["path"] + ": " + "; ".join(i["code"] + " at " + i["path"] for i in r["issues"])
                for r in report["records"] if not r["valid"]]
    if producer_status != "PASS":
        blockers.append("claim " + claim_m["id"] + " producer status is " + producer_status)
    proj_state = {
        "lifecycle": "CHECKPOINTED" if not blockers else "BLOCKED",
        "currentGate": "producer_self_check=" + producer_status + " (producer-asserted, not verified)",
        "mandatoryTotals": {"PASS": 1 if producer_status == "PASS" else 0, "FAIL": 1 if producer_status == "FAIL" else 0,
                            "UNKNOWN": 0, "ERROR": 0, "NOT_RUN": 1},
        "bundleDigest": "none (single producer claim " + claim["revisionId"] + ")",
        "auditDigest": "none (independent audit NOT_RUN)",
        "nextLegalAction": (cp_m.get("nextLegalActions") or ["hand the claim and its evidence to the independent auditor"])[0],
        "blockers": blockers,
        "evidenceReferences": [ev_digest[e["id"]] for e in manifest["evidence"]] + ["checkpoint " + checkpoint["revisionId"]],
    }
    (task.root / "state.json").write_text(json.dumps(proj_state, indent=2) + "\n", encoding="utf-8")
    status = compact_status(proj_state, word_budget=args.word_budget)
    (task.root / "status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    state["finishedAt"] = _utc()
    task.save_state(state)

    sys.stdout.write(status["text"] + "\n")
    sys.stdout.write("records: %d written, %d valid; events: %d; checkpoint: %s\n" % (
        len(named), sum(1 for r in report["records"] if r["valid"]), len(events), checkpoint["revisionId"]))
    if not report["allValid"]:
        return ExitCode.FAIL
    return ExitCode.PASS if producer_status == "PASS" else ExitCode.FAIL



# ---------------------------------------------------------------------------
# record -- init + steps + finish in one process, one line of output
# ---------------------------------------------------------------------------

def _parse_evidence_flag(spec: str) -> dict[str, Any]:
    """PATH[:KIND[:source]] -> evidence entry. Inputs are marked ':source'."""
    parts = spec.split(":")
    path = parts[0]
    is_source = len(parts) > 2 and parts[2].lower() in ("source", "src", "input")
    kind = parts[1] if len(parts) > 1 and parts[1] else ("source_bytes" if is_source else "derivation_receipt")
    entry: dict[str, Any] = {"id": "ev." + Path(path).stem.replace(" ", "_"), "path": path, "kind": kind}
    if is_source:
        entry["source"] = True
    return entry


def _manifest_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.manifest:
        return _read_manifest(args.manifest)
    if not args.evidence:
        raise ValueError("record needs --manifest or at least one --evidence PATH[:KIND[:source]]")
    task_id = args.task_id
    evidence = [_parse_evidence_flag(e) for e in args.evidence]
    sources = [e["id"] for e in evidence if e.get("source")]
    outputs = [e for e in evidence if not e.get("source")]
    for e in outputs:
        e["derivedFrom"] = sources
    primary = outputs[0] if outputs else evidence[0]
    subject = args.claim_subject or primary["path"]
    manifest: dict[str, Any] = {
        "taskId": task_id,
        "outcome": {
            "id": "outcome." + task_id,
            "title": args.title or task_id,
            "requestedResult": args.requested_result or ("produce " + primary["path"]),
            "subjectUniverse": [subject],
            "requiredArtifacts": [Path(e["path"]).suffix.lstrip(".") or "file" for e in outputs],
        },
        "workItem": {"id": "wi." + task_id, "title": args.title or task_id, "capability": args.capability},
        "evidence": evidence,
        "claim": {
            "id": "claim." + task_id,
            "claimType": args.claim_type,
            "subject": subject,
            "statement": args.claim_statement or (subject + " was produced from the declared sources and self-checked"),
            "evidence": [e["id"] for e in evidence],
        },
        "checkpoint": {"id": args.checkpoint_id or ("cp." + task_id), "requiredFacts": {}},
    }
    for kv in args.fact or []:
        k, _, v = kv.partition("=")
        manifest["checkpoint"]["requiredFacts"][k] = v
    return manifest


def _apply_steps_file(task: "_Task", path: Path) -> int:
    """Ingest steps the agent's own script appended while it worked.

    One JSON object per line: {"step": "<id>", "t_ns": time.monotonic_ns(),
    "status"?: ..., "purpose"?: ...}. A line whose step is "start" marks the
    run start and is not a step. A step's span runs from the previous
    timestamp to its own. None of this costs a model turn: the timestamps were
    written by the process that did the work.
    """
    state = task.load_state()
    events = task.events(state["taskId"])
    last = state["lastNs"]
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        step_id = str(row.get("step") or row.get("stepId"))
        t_ns = int(row["t_ns"])
        if step_id.lower() in ("start", "begin"):
            state["startNs"] = min(state["startNs"], t_ns)
            last = t_ns
            continue
        if any(s["stepId"] == step_id for s in state["steps"]):
            continue
        status = str(row.get("status", "PASS"))
        purpose = str(row.get("purpose", "GENERATION"))
        payload: dict[str, Any] = {"stepId": step_id, "status": status}
        if row.get("note"):
            payload["note"] = str(row["note"])
        event = events.append("step.completed", step_id, payload, state["taskId"] + ":step:" + step_id,
                              wall_clock=_utc(), monotonic_ns=t_ns, monotonic_clock_domain=state["clockDomain"])
        state["steps"].append({"stepId": step_id, "status": status, "purpose": purpose,
                               "startNs": min(last, t_ns), "endNs": t_ns, "eventId": event["eventId"]})
        last = t_ns
        count += 1
    state["lastNs"] = max(state["lastNs"], last)
    task.save_state(state)
    return count


def _first_start_ns(path: Path) -> int | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if str(row.get("step") or row.get("stepId")).lower() in ("start", "begin"):
                return int(row["t_ns"])
            return None
    return None


def cmd_task_record(args: argparse.Namespace) -> int:
    import contextlib
    import io

    try:
        manifest = _manifest_from_args(args)
    except (ValueError, KeyError) as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    args._manifest_obj = manifest
    args._base = str(Path(args.base or ".").resolve())

    steps_path = Path(args.steps) if args.steps else None
    if steps_path is not None and steps_path.exists():
        first = _first_start_ns(steps_path)
        if first is not None:
            args._start_ns = first

    sink = io.StringIO()
    steps_recorded = 0
    with contextlib.redirect_stdout(sink):
        code = cmd_task_init(args)
        if code == ExitCode.PASS:
            if steps_path is not None and steps_path.exists():
                steps_recorded = _apply_steps_file(_Task(args.root), steps_path)
            code = cmd_task_finish(args)
    full = sink.getvalue()

    if not args.quiet:
        sys.stdout.write(full)
        return code

    if code == ExitCode.ERROR:
        # A refusal is reported as its reason, never as the stale state of an
        # earlier run under the same root.
        reason = "error"
        for line in reversed(full.splitlines()):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("reason"):
                reason = str(obj["reason"])
                break
        sys.stdout.write(("ERROR " + reason)[:160] + "\n")
        return code

    task = _Task(args.root)
    state_path = task.root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    ref = next((r for r in state.get("evidenceReferences", []) if str(r).startswith("checkpoint ")), "")
    rev = ref.split(" ", 1)[1] if " " in ref else "?"
    rev = rev[7:19] if rev.startswith("sha256:") else rev[:12]
    blockers = state.get("blockers", [])
    tail = ("blockers=" + str(len(blockers))) if blockers else ("next=" + str(state.get("nextLegalAction", ""))[:48])
    line = "%s cp=%s rev=%s steps=%d %s" % (
        "PASS" if code == ExitCode.PASS else ("FAIL" if code == ExitCode.FAIL else "ERROR"),
        manifest["checkpoint"]["id"], rev, steps_recorded, tail,
    )
    sys.stdout.write(line[:160] + "\n")
    return code


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def add_task_parser(sub: Any) -> None:
    p = sub.add_parser("task", help="structure one unit of work: init, step, finish")
    tasks = p.add_subparsers(dest="task_command", required=True)

    i = tasks.add_parser("init", help="declare the outcome, work item and plan; open the event stream")
    i.add_argument("--root", required=True, help="directory for the ontology records (e.g. ./ontology)")
    i.add_argument("--manifest", required=True, help="task manifest JSON")
    i.set_defaults(func=cmd_task_init)

    s = tasks.add_parser("step", help="record one completed plan step with observed timing")
    s.add_argument("step_id")
    s.add_argument("--root", required=True)
    s.add_argument("--status", choices=_STATUSES, default="PASS")
    s.add_argument("--purpose", choices=_PURPOSES, default="GENERATION")
    s.add_argument("--note")
    s.set_defaults(func=cmd_task_step)

    f = tasks.add_parser("finish", help="store evidence, compile the claim, write the trace, commit the checkpoint")
    f.add_argument("--root", required=True)
    f.add_argument("--manifest", required=True)
    f.add_argument("--claim-values", help="JSON file merged into the claim: expectedValue, observedValue, producerStatus")
    f.add_argument("--producer-status", choices=_STATUSES)
    f.add_argument("--word-budget", type=int, default=200)
    f.set_defaults(func=cmd_task_finish)

    r = tasks.add_parser("record", help="init + steps + finish in ONE call; steps come from a file your own script appended to")
    r.add_argument("--root", required=True, help="directory for the ontology records (e.g. ./ontology)")
    r.add_argument("--task-id", required=True)
    r.add_argument("--manifest", help="optional manifest JSON; otherwise built from the flags below")
    r.add_argument("--evidence", action="append", help="PATH[:KIND[:source]] -- repeatable; mark inputs with :source")
    r.add_argument("--steps", help="steps.jsonl your own script appended to, one {step, t_ns} per line")
    r.add_argument("--base", help="directory evidence paths are relative to (default: cwd)")
    r.add_argument("--title")
    r.add_argument("--requested-result")
    r.add_argument("--capability", default="cap.artifact.derive")
    r.add_argument("--claim-type", default="HASH_EQUALITY")
    r.add_argument("--claim-subject")
    r.add_argument("--claim-statement")
    r.add_argument("--claim-values", help="JSON file merged into the claim: expectedValue, observedValue, producerStatus")
    r.add_argument("--producer-status", choices=_STATUSES, default="PASS")
    r.add_argument("--checkpoint-id")
    r.add_argument("--fact", action="append", help="KEY=VALUE required fact for the checkpoint; repeatable")
    r.add_argument("--word-budget", type=int, default=200)
    r.add_argument("--quiet", action="store_true", help="one line of output (<=160 chars)")
    r.set_defaults(func=cmd_task_record)
