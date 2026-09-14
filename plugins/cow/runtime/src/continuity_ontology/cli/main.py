"""``ont20`` -- the operator command line.

Every command emits machine-readable JSON on stdout and uses the stable exit
codes inherited from the CityQA suite, so a caller can branch on the result
without parsing prose:

    0  PASS / APPROVE          3  UNKNOWN
    2  FAIL / REJECT           4  ERROR
    5  INVALID_CONTRACT        6  BLOCKED_BY_PRIOR_STATE

Detailed artifacts are written to disk and referenced by digest rather than
printed, so a routine successful run stays small.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from cityqa.engine.statuses import ExitCode

from ..canonical.profiles import describe_all, digest_with
from ..model.metamodel import KERNEL_CONCEPTS, load_metamodel
from ..projection.queries import answer, query_ids, competency_corpus, COMPETENCY_QUERIES
from ..projection.views import compact_status, render_html_report
from ..validate.validator import RecordValidator

__all__ = ["main", "build_parser"]


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ontology" / "metamodel.json").exists():
            return parent
    raise FileNotFoundError("could not locate the repository root")


def cmd_model(args: argparse.Namespace) -> int:
    model = load_metamodel()
    _emit(
        {
            "metamodelVersion": model.version,
            "semanticModelDigest": model.digest,
            "entityCount": len(model.entities),
            "kernelConcepts": list(KERNEL_CONCEPTS),
            "kernelComplete": all(c in model.entities for c in KERNEL_CONCEPTS),
            "relationCount": len(model.relations),
            "vocabularyCount": len(model.vocabularies),
            "extensionDigests": model.extension_digests,
            "allowedClosures": model.inference["allowedClosures"],
        }
    )
    return ExitCode.PASS


def cmd_profiles(args: argparse.Namespace) -> int:
    _emit({"hashProfiles": describe_all()})
    return ExitCode.PASS


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        value = json.loads(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    result = RecordValidator().validate(args.record_type, value)
    _emit(result.as_dict())
    return ExitCode.PASS if result.ok else ExitCode.FAIL


def cmd_run_e2e(args: argparse.Namespace) -> int:
    from .pipeline import run_end_to_end

    source = Path(args.source)
    members = args.member or sorted(
        str(p.relative_to(source)).replace("\\", "/")
        for p in source.rglob("*")
        if p.is_file()
    )
    if not members:
        _emit({"status": "ERROR", "reason": "no members to package under " + str(source)})
        return ExitCode.ERROR
    result = run_end_to_end(args.run_root, source, members)
    summary = {
        "status": result["verification"]["status"],
        "runId": result["runId"],
        "synthetic": result["synthetic"],
        "candidateDigest": result["candidateDigest"],
        "bundleDigest": result["bundleDigest"],
        "auditVerdict": result["audit"]["verdict"],
        "auditDigest": result["audit"]["resultDigest"],
        "promotionState": result["promotionDecision"]["state"],
        "acceptedWorkTotal": result["acceptedWork"]["totalWeight"],
        "activeElapsedMs": result["timing"]["activeElapsed"]["valueMs"],
        "vendorTokens": _resource_line(result["resourceTotals"]["VENDOR_INPUT_TOKENS"]),
        "resourceLedger": result["resourceLedgerPath"],
        "checkpointRevision": result["checkpoint"]["revisionId"],
        "eventStream": result["eventStreamPath"],
        "auditReceipt": result["auditReceipt"]["path"],
    }
    _emit(summary)
    return ExitCode.PASS if summary["status"] == "PASS" else ExitCode.FAIL


def _resource_line(total: dict) -> str:
    """Render a ledger total without collapsing UNKNOWN into a number."""
    if total.get("unknownCount"):
        return "UNKNOWN (" + "; ".join(total.get("unknownReasons") or ["not measured"]) + ")"
    if total.get("observedTotal") is not None:
        return str(total["observedTotal"]) + " OBSERVED"
    return "NOT_RUN (no measurement)"


def cmd_resume(args: argparse.Namespace) -> int:
    from ..checkpoints.store import CheckpointError, CheckpointStore

    try:
        store = CheckpointStore(args.checkpoint_root)
        observed = json.loads(args.observed) if args.observed else {}
        report = store.resume(args.checkpoint_id, observed_environment=observed)
    except CheckpointError as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    _emit(report.as_dict())
    return ExitCode.PASS if report.resumable else ExitCode.BLOCKED_BY_PRIOR_STATE


def cmd_query(args: argparse.Namespace) -> int:
    if args.list:
        _emit({'questions': [{k: r[k] for k in ('number', 'question', 'queryId')}
                             for r in competency_corpus()['questions']]})
        return ExitCode.PASS
    if not args.corpus:
        _emit({'status': 'ERROR', 'reason': 'corpus is required unless --list is supplied'})
        return ExitCode.ERROR
    try:
        corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    if args.query_id:
        result = answer(args.query_id, corpus)
        _emit(result)
        return ExitCode.PASS if result["available"] else ExitCode.UNKNOWN
    results = [answer(q, corpus) for q in query_ids()]
    _emit({"answers": results})
    return ExitCode.PASS


def cmd_status(args: argparse.Namespace) -> int:
    try:
        state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    _emit(compact_status(state, word_budget=args.word_budget))
    return ExitCode.PASS


def cmd_report(args: argparse.Namespace) -> int:
    try:
        state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return ExitCode.ERROR
    view = render_html_report(state)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(view["document"], encoding="utf-8")
    failures = [c for c in view["accessibilityResults"] if c["status"] != "PASS"]
    _emit(
        {
            "status": "PASS" if not failures else "FAIL",
            "path": str(out),
            "viewId": view["viewId"],
            "semanticInputDigest": view["semanticInputDigest"],
            "lifecycle": view["lifecycle"],
            "accessibilityFailures": failures,
        }
    )
    return ExitCode.PASS if not failures else ExitCode.FAIL


def cmd_pershing(args: argparse.Namespace) -> int:
    from continuity_integrations.unreal_cityreference.program_profile import (
        load_program_profile,
        render_runbook,
        validate_program_invariants,
    )

    profile = load_program_profile(_repo_root() / "profiles" / "pershing" / "program.json")
    if args.runbook:
        sys.stdout.write(render_runbook(profile, args.runbook))
        return ExitCode.PASS
    result = validate_program_invariants(profile)
    _emit(result)
    return ExitCode.PASS if result["status"] == "PASS" else ExitCode.FAIL


def cmd_sfd(args: argparse.Namespace) -> int:
    from continuity_integrations.unreal_cityreference.sfd import compatibility_status

    status = compatibility_status()
    _emit(status)
    return ExitCode.PASS if status["status"] == "PASS" else ExitCode.UNKNOWN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ont20", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("model", help="report the resolved semantic model").set_defaults(func=cmd_model)
    sub.add_parser("profiles", help="describe every hash profile").set_defaults(func=cmd_profiles)

    p = sub.add_parser("validate", help="validate a record against the model")
    p.add_argument("record_type")
    p.add_argument("path")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("run-e2e", help="run the real end-to-end workflow")
    p.add_argument("--source", required=True, help="directory whose files are packaged")
    p.add_argument("--run-root", required=True, help="directory for events, CAS and receipts")
    p.add_argument("--member", action="append", help="explicit member (repeatable)")
    p.set_defaults(func=cmd_run_e2e)

    p = sub.add_parser("resume", help="resume from a committed checkpoint")
    p.add_argument("--checkpoint-root", required=True)
    p.add_argument("--checkpoint-id", required=True)
    p.add_argument("--observed", help="JSON object of freshly observed ephemeral bindings")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("query", help="answer competency questions from a corpus")
    p.add_argument("corpus", nargs='?')
    p.add_argument("--list", action='store_true')
    p.add_argument("--query-id", choices=tuple(COMPETENCY_QUERIES))
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("status", help="render a compact machine status")
    p.add_argument("state")
    p.add_argument("--word-budget", type=int, default=500)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("report", help="render the accessible HTML report")
    p.add_argument("state")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("pershing", help="validate the integration profile or render a runbook")
    p.add_argument("--runbook", help="gate id, e.g. PG5")
    p.set_defaults(func=cmd_pershing)

    sub.add_parser("sfd", help="report SFD v1 compatibility qualification").set_defaults(func=cmd_sfd)

    from .task import add_task_parser

    add_task_parser(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - the CLI reports, it does not crash
        _emit({"status": "ERROR", "reason": type(exc).__name__ + ": " + str(exc)})
        return ExitCode.ERROR


if __name__ == "__main__":
    raise SystemExit(main())
