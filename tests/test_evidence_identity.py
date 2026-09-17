"""Evidence identity: one path, one ID, one digest -- and resume checks it.

Regression coverage for the recorder collision observed on 2026-09-16: two
evidence files sharing a stem (``reopen_receipt.json`` and
``reopen_receipt.py``) were given one logical ID, the second record
overwrote the first, and the checkpoint snapshot bound the ``.json`` path to
the ``.py`` digest while ``resume`` reported ``resumable: true``.

Classes map onto the fix packet: F1 regression, F2 identity scheme, F3
preflight refusal, F4 full-association check, F5 integrity on resume and
``task verify``, F6 pre-fix checkpoints, A1 record-seal and ambiguity, A2
the no-CAS branches, A4 argument order. F7 (producer-status exit codes)
lives in ``test_producer_status_exit.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from cityqa.engine.statuses import ExitCode

from continuity_ontology.canonical.profiles import digest_with
from continuity_ontology.checkpoints.evidence_integrity import (
    EvidenceManifestError,
    EvidencePathError,
    evidence_id,
    evidence_record_name,
    normalize_evidence_path,
    normalize_manifest_evidence,
    unescape,
    verify_evidence_bindings,
)
from continuity_ontology.checkpoints.store import CheckpointStore
from continuity_ontology.claims.cas import ContentStore
from continuity_ontology.cli.main import main

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "evidence_identity" / "pre_fix_run"
# The fixture's content store lives under objects/ rather than cas/ because
# .gitignore excludes every cas/ directory; the test passes it explicitly.
FIXTURE_CAS = FIXTURE / "objects"
RUN_ARTIFACTS = ("records", "events", "cas", "checkpoints", "state.json", "task-state.json")


def _run(*argv: str, cwd: Path, capsys) -> tuple[int, str]:
    prior = os.getcwd()
    os.chdir(cwd)
    try:
        code = main(list(argv))
    finally:
        os.chdir(prior)
    return code, capsys.readouterr().out


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _record(workdir: Path, capsys, *evidence: str, root: str = "ontology", task_id: str = "t1",
            extra: tuple[str, ...] = ()) -> tuple[int, str]:
    argv = ["task", "record", "--root", root, "--task-id", task_id]
    for spec in evidence:
        argv += ["--evidence", spec]
    return _run(*argv, *extra, cwd=workdir, capsys=capsys)


def _checkpoint(workdir: Path, root: str = "ontology", cp: str = "cp.t1") -> dict:
    return json.loads((workdir / root / "checkpoints" / (cp + ".checkpoint.json")).read_text(encoding="utf-8"))


def _resume(workdir: Path, capsys, root: str = "ontology", cp: str = "cp.t1", *extra: str) -> tuple[int, dict]:
    code, out = _run("resume", "--checkpoint-root", root + "/checkpoints", "--checkpoint-id", cp,
                     "--observed", '{"processId": 1}', *extra, cwd=workdir, capsys=capsys)
    return code, json.loads(out)


def _evidence_records(workdir: Path, root: str = "ontology") -> dict[str, dict]:
    records = {}
    for path in sorted((workdir / root / "records").glob("evidence_*.json")):
        records[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return records


def _cas_path(workdir: Path, digest: str, root: str = "ontology") -> Path:
    hexpart = digest[len("sha256:"):]
    return workdir / root / "cas" / hexpart[:2] / hexpart[2:4] / hexpart


def _reseal(record: dict) -> dict:
    body = {k: v for k, v in record.items() if k != "revisionId"}
    body["revisionId"] = digest_with(record["hashProfile"], body)
    return body


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "reopen_receipt.json").write_bytes(b'{"reopened": true}\n')
    (tmp_path / "a" / "reopen_receipt.py").write_bytes(b"print('reopen')\n")
    return tmp_path


# ---------------------------------------------------------------------------
# F1
# ---------------------------------------------------------------------------

class TestF1SameStemDifferentExtension:
    def test_each_path_is_bound_to_the_digest_of_its_own_bytes(self, workdir, capsys):
        code, out = _run("task", "record", "--root", "ontology", "--task-id", "t1",
                         "--evidence", "a/reopen_receipt.json::source",
                         "--evidence", "a/reopen_receipt.py",
                         cwd=workdir, capsys=capsys)
        assert code == 0, out
        checkpoint = json.loads(
            (workdir / "ontology" / "checkpoints" / "cp.t1.checkpoint.json").read_text(encoding="utf-8"))
        snapshot = checkpoint["snapshot"]
        json_digest = _sha256(workdir / "a" / "reopen_receipt.json")
        py_digest = _sha256(workdir / "a" / "reopen_receipt.py")
        assert json_digest != py_digest
        assert snapshot["admittedSourceVersions"] == {"a/reopen_receipt.json": json_digest}
        assert snapshot["artifactRefs"] == {"a/reopen_receipt.py": py_digest}


# ---------------------------------------------------------------------------
# F2 (and A3): deterministic, path-complete, injective IDs
# ---------------------------------------------------------------------------

class TestF2PathCompleteIds:
    @pytest.mark.parametrize("left,right", [
        ("a/reopen_receipt.json", "a/reopen_receipt.py"),   # same stem, different extension
        ("a/receipt.json", "b/receipt.json"),               # same filename, different directory
        ("a b.txt", "a_b.txt"),                             # whitespace vs underscore
        ("x.y.z", "x_y.z"),                                 # dot vs underscore
        ("a.b", "a_b"),                                     # the record-file-name trap
        ("README.md", "readme.md"),                         # case is preserved
    ])
    def test_distinct_relative_paths_never_share_an_id_or_a_record_name(self, left, right):
        assert evidence_id(left) != evidence_id(right)
        assert evidence_record_name(evidence_id(left)) != evidence_record_name(evidence_id(right))
        # the record names remain distinct on a case-folding filesystem
        assert (evidence_record_name(evidence_id(left)).lower()
                != evidence_record_name(evidence_id(right)).lower())

    @pytest.mark.parametrize("path", [
        "evidence/reopen-record-inputs/reopen_receipt.json", "a b.txt", "x.y.z", "README.md",
        "Ã¼nÃ¯code+.txt", "deep/er/path/with.many.dots.tar.gz",
    ])
    def test_the_id_is_reversible_and_keeps_the_ev_prefix(self, path):
        ev_id = evidence_id(path)
        assert ev_id.startswith("ev.")
        assert unescape(ev_id[len("ev."):]) == path
        name = evidence_record_name(ev_id)
        assert name.startswith("evidence_")
        assert unescape(name[len("evidence_"):]) == ev_id

    def test_the_repro_paths_get_two_ids(self):
        assert evidence_id("evidence/reopen-record-inputs/reopen_receipt.json") == \
            "ev.evidence/reopen-record-inputs/reopen_receipt.json"
        assert evidence_id("evidence/reopen-record-inputs/reopen_receipt.py") == \
            "ev.evidence/reopen-record-inputs/reopen_receipt.py"

    def test_normalization_is_lexical_and_platform_independent(self, tmp_path):
        assert normalize_evidence_path("./a/x.json", tmp_path) == "a/x.json"
        assert normalize_evidence_path("a\\x.json", tmp_path) == "a/x.json"
        assert normalize_evidence_path("a//x.json", tmp_path) == "a/x.json"
        assert normalize_evidence_path("A/X.JSON", tmp_path) == "A/X.JSON"
        with pytest.raises(EvidencePathError):
            normalize_evidence_path("../x.json", tmp_path)
        with pytest.raises(EvidencePathError):
            normalize_evidence_path("a/../../x.json", tmp_path)

    def test_an_overlong_path_keeps_a_reversible_id_and_a_bounded_record_name(self):
        long_path = "/".join(["segment"] * 40) + "/file.txt"
        ev_id = evidence_id(long_path)
        assert ev_id == "ev." + long_path and unescape(ev_id[3:]) == long_path
        assert ev_id == evidence_id(long_path)
        name = evidence_record_name(ev_id)
        assert len(name) + len(".json") <= 120
        assert "~" in name and name.endswith(hashlib.sha256(ev_id.encode("utf-8")).hexdigest())

    def test_two_records_exist_with_their_own_subjects(self, workdir, capsys):
        code, out = _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")
        assert code == 0, out
        records = _evidence_records(workdir)
        assert len(records) == 2
        by_subject = {r["subject"]: r for r in records.values()}
        assert set(by_subject) == {"a/reopen_receipt.json", "a/reopen_receipt.py"}
        assert by_subject["a/reopen_receipt.json"]["contentDigest"] == _sha256(workdir / "a" / "reopen_receipt.json")
        assert by_subject["a/reopen_receipt.py"]["contentDigest"] == _sha256(workdir / "a" / "reopen_receipt.py")
        assert by_subject["a/reopen_receipt.json"]["logicalId"] == "ev.a/reopen_receipt.json"
        assert by_subject["a/reopen_receipt.py"]["logicalId"] == "ev.a/reopen_receipt.py"
        claim = json.loads((workdir / "ontology" / "records" / "claim.json").read_text(encoding="utf-8"))
        assert len(set(claim["producerAssertion"]["evidenceRefs"])) == 2

    def test_ids_are_identical_across_two_runs_on_the_same_tree(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py", root="r1")[0] == 0
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py", root="r2")[0] == 0
        first = {r["subject"]: r["logicalId"] for r in _evidence_records(workdir, "r1").values()}
        second = {r["subject"]: r["logicalId"] for r in _evidence_records(workdir, "r2").values()}
        assert first == second
        assert sorted(_evidence_records(workdir, "r1")) == sorted(_evidence_records(workdir, "r2"))


# ---------------------------------------------------------------------------
# A4: argument order is a success case, not a refusal
# ---------------------------------------------------------------------------

class TestA4ArgumentOrder:
    @pytest.mark.parametrize("order", [
        ("a/reopen_receipt.json::source", "a/reopen_receipt.py"),
        ("a/reopen_receipt.py", "a/reopen_receipt.json::source"),
    ])
    def test_a_source_and_an_output_sharing_a_stem_record_cleanly_in_either_order(self, workdir, capsys, order):
        code, out = _record(workdir, capsys, *order)
        assert code == 0, out
        snapshot = _checkpoint(workdir)["snapshot"]
        assert snapshot["admittedSourceVersions"] == {
            "a/reopen_receipt.json": _sha256(workdir / "a" / "reopen_receipt.json")}
        assert snapshot["artifactRefs"] == {"a/reopen_receipt.py": _sha256(workdir / "a" / "reopen_receipt.py")}
        ids = sorted(r["logicalId"] for r in _evidence_records(workdir).values())
        assert ids == ["ev.a/reopen_receipt.json", "ev.a/reopen_receipt.py"]


# ---------------------------------------------------------------------------
# F3: preflight refusal, nothing written
# ---------------------------------------------------------------------------

def _manifest(evidence: list[dict]) -> dict:
    return {
        "taskId": "m1",
        "outcome": {"id": "outcome.m1", "title": "m1", "requestedResult": "r", "subjectUniverse": ["a"],
                    "requiredArtifacts": ["py"]},
        "workItem": {"id": "wi.m1", "title": "m1", "capability": "cap.demo.v1"},
        "evidence": evidence,
        "claim": {"id": "claim.m1", "claimType": "HASH_EQUALITY", "subject": "a/reopen_receipt.py",
                  "statement": "s", "evidence": [e["id"] for e in evidence]},
        "checkpoint": {"id": "cp.m1", "requiredFacts": {}},
    }


def _assert_nothing_written(workdir: Path, root: str = "ontology") -> None:
    run_root = workdir / root
    if run_root.exists():
        assert not any(run_root.iterdir()), sorted(p.name for p in run_root.iterdir())
    for name in RUN_ARTIFACTS:
        assert not (run_root / name).exists(), name


class TestF3PreflightRefusal:
    def test_duplicate_ids_in_a_supplied_manifest_are_refused_before_anything_is_written(self, workdir, capsys):
        manifest = _manifest([
            {"id": "ev.reopen_receipt", "path": "a/reopen_receipt.json", "kind": "source_bytes", "source": True},
            {"id": "ev.reopen_receipt", "path": "a/reopen_receipt.py", "kind": "derivation_receipt"},
        ])
        (workdir / "task.json").write_text(json.dumps(manifest), encoding="utf-8")
        code, out = _run("task", "record", "--root", "ontology", "--task-id", "m1", "--manifest", "task.json",
                         cwd=workdir, capsys=capsys)
        assert code == ExitCode.ERROR == 4
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["status"] == "ERROR"
        assert payload["duplicateEvidenceIds"] == ["ev.reopen_receipt"]
        assert payload["reason"] == ("evidence id ev.reopen_receipt is bound to more than one path: "
                                     "a/reopen_receipt.json, a/reopen_receipt.py")
        _assert_nothing_written(workdir)

    def test_the_same_id_declared_twice_for_one_path_is_refused(self, workdir, capsys):
        manifest = _manifest([
            {"id": "ev.x", "path": "a/reopen_receipt.py", "kind": "derivation_receipt"},
            {"id": "ev.x", "path": "a/reopen_receipt.py", "kind": "derivation_receipt"},
        ])
        (workdir / "task.json").write_text(json.dumps(manifest), encoding="utf-8")
        code, out = _run("task", "record", "--root", "ontology", "--task-id", "m1", "--manifest", "task.json",
                         cwd=workdir, capsys=capsys)
        assert code == ExitCode.ERROR
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["duplicateEvidenceIds"] == ["ev.x"]
        assert payload["reason"] == "evidence id ev.x is declared 2 times"
        _assert_nothing_written(workdir)

    def test_the_same_evidence_flag_twice_is_refused(self, workdir, capsys):
        code, out = _record(workdir, capsys, "a/reopen_receipt.py", "a/reopen_receipt.py")
        assert code == ExitCode.ERROR
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["status"] == "ERROR"
        assert payload["duplicateEvidenceIds"] == ["ev.a/reopen_receipt.py"]
        assert payload["reason"] == "evidence id ev.a/reopen_receipt.py is declared 2 times"
        _assert_nothing_written(workdir)

    def test_the_same_file_under_two_spellings_is_refused(self, workdir, capsys):
        code, out = _record(workdir, capsys, "./a/reopen_receipt.py", "a//reopen_receipt.py")
        assert code == ExitCode.ERROR
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["duplicateEvidenceIds"] == ["ev.a/reopen_receipt.py"]
        _assert_nothing_written(workdir)

    def test_two_ids_for_one_path_in_a_manifest_are_refused(self, workdir, capsys):
        manifest = _manifest([
            {"id": "ev.one", "path": "a/reopen_receipt.py", "kind": "derivation_receipt"},
            {"id": "ev.two", "path": "./a/reopen_receipt.py", "kind": "derivation_receipt"},
        ])
        (workdir / "task.json").write_text(json.dumps(manifest), encoding="utf-8")
        code, out = _run("task", "init", "--root", "ontology", "--manifest", "task.json", cwd=workdir, capsys=capsys)
        assert code == ExitCode.ERROR
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["duplicateEvidenceIds"] == ["ev.one", "ev.two"]
        assert payload["reason"] == "evidence path a/reopen_receipt.py is declared more than once under ids ev.one, ev.two"
        _assert_nothing_written(workdir)

    def test_a_parent_segment_is_refused_with_nothing_written(self, workdir, capsys):
        (workdir / "outside.txt").write_bytes(b"x")
        (workdir / "base").mkdir()
        code, out = _run("task", "record", "--root", "ontology", "--task-id", "t1", "--base", "base",
                         "--evidence", "../outside.txt", cwd=workdir, capsys=capsys)
        assert code == ExitCode.ERROR
        assert "parent segment" in out
        _assert_nothing_written(workdir)

    def test_the_quiet_form_reports_the_refusal_not_stale_state(self, workdir, capsys):
        code, out = _record(workdir, capsys, "a/reopen_receipt.py", "a/reopen_receipt.py", extra=("--quiet",))
        assert code == ExitCode.ERROR
        assert out.startswith("ERROR evidence id ev.a/reopen_receipt.py is declared 2 times")

    def test_the_preflight_function_names_every_conflict(self, tmp_path):
        entries = [{"id": "ev.k", "path": "p1"}, {"id": "ev.k", "path": "p2"}, {"path": "p3"}, {"path": "./p3"}]
        with pytest.raises(EvidenceManifestError) as info:
            normalize_manifest_evidence(entries, tmp_path)
        assert info.value.duplicate_ids == ["ev.k", "ev.p3"]


# ---------------------------------------------------------------------------
# F4: full association at record time
# ---------------------------------------------------------------------------

class TestF4FullAssociation:
    def test_identical_bytes_under_two_paths_are_two_records_and_one_cas_object(self, workdir, capsys):
        (workdir / "a" / "copy.json").write_bytes((workdir / "a" / "reopen_receipt.json").read_bytes())
        code, out = _record(workdir, capsys, "a/reopen_receipt.json::source", "a/copy.json::source",
                            "a/reopen_receipt.py")
        assert code == 0, out
        digest = _sha256(workdir / "a" / "reopen_receipt.json")
        snapshot = _checkpoint(workdir)["snapshot"]
        assert snapshot["admittedSourceVersions"] == {"a/reopen_receipt.json": digest, "a/copy.json": digest}
        records = {r["logicalId"]: r for r in _evidence_records(workdir).values()}
        assert records["ev.a/reopen_receipt.json"]["subject"] == "a/reopen_receipt.json"
        assert records["ev.a/copy.json"]["subject"] == "a/copy.json"
        assert records["ev.a/reopen_receipt.json"]["contentDigest"] == digest
        assert records["ev.a/copy.json"]["contentDigest"] == digest
        assert len(ContentStore(workdir / "ontology" / "cas")) == 2   # shared bytes once, plus the .py

    def test_a_valid_blob_bound_to_the_wrong_path_is_refused(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        json_digest = _sha256(workdir / "a" / "reopen_receipt.json")
        py_digest = _sha256(workdir / "a" / "reopen_receipt.py")
        records = list(_evidence_records(workdir).values())
        cas = ContentStore(workdir / "ontology" / "cas")
        snapshot = _checkpoint(workdir)["snapshot"]
        # plant: path A now points at blob B, which is present and valid in the CAS
        snapshot["admittedSourceVersions"]["a/reopen_receipt.json"] = py_digest
        report = verify_evidence_bindings(
            snapshot, records, cas,
            expected={"a/reopen_receipt.json": json_digest, "a/reopen_receipt.py": py_digest})
        assert report["status"] == "FAIL"
        assert ("evidence mis-bound: a/reopen_receipt.json expected=" + json_digest + " snapshot=" + py_digest
                in report["blockers"])
        assert ("evidence mis-bound: a/reopen_receipt.json record=" + json_digest + " snapshot=" + py_digest
                in report["blockers"])

    def test_a_reference_outside_the_manifest_is_refused(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        records = list(_evidence_records(workdir).values())
        cas = ContentStore(workdir / "ontology" / "cas")
        snapshot = _checkpoint(workdir)["snapshot"]
        stray = "sha256:" + "0" * 64
        report = verify_evidence_bindings(snapshot, records, cas, referenced=[stray])
        assert report["blockers"] == ["evidence reference outside the manifest: " + stray]

    def test_a_clean_run_passes_the_same_check_after_the_fact(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        report = verify_evidence_bindings(_checkpoint(workdir)["snapshot"], _evidence_records(workdir),
                                          ContentStore(workdir / "ontology" / "cas"))
        assert report == {"status": "PASS", "checked": 2, "passed": 2, "findings": report["findings"], "blockers": [],
                          "recordNamesChecked": True, "claimChecked": False}
        assert all(f["status"] == "PASS" for f in report["findings"])


# ---------------------------------------------------------------------------
# F5: integrity on resume and `task verify`
# ---------------------------------------------------------------------------

class TestF5ResumeRejectsBadEvidence:
    def test_a_clean_run_resumes_with_an_integrity_block(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        code, report = _resume(workdir, capsys)
        assert code == 0 and report["resumable"] is True
        integrity = report["evidenceIntegrity"]
        assert integrity["status"] == "PASS"
        assert integrity["checked"] == 2 and integrity["passed"] == 2
        assert {f["path"] for f in integrity["findings"]} == {"a/reopen_receipt.json", "a/reopen_receipt.py"}
        code, out = _run("task", "verify", "--root", "ontology", cwd=workdir, capsys=capsys)
        assert code == 0
        assert json.loads(out)["checkpointId"] == "cp.t1"

    def test_a_tampered_cas_object_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        digest = _sha256(workdir / "a" / "reopen_receipt.py")
        blob = _cas_path(workdir, digest)
        payload = bytearray(blob.read_bytes())
        payload[0] ^= 0x01
        blob.write_bytes(bytes(payload))
        code, report = _resume(workdir, capsys)
        assert code == ExitCode.BLOCKED_BY_PRIOR_STATE == 6
        assert report["resumable"] is False
        assert "evidence corrupted: a/reopen_receipt.py " + digest in report["blockers"]
        assert report["restoredFacts"]   # every fact restored, still not resumable
        assert report["evidenceIntegrity"]["status"] == "FAIL"
        code, out = _run("task", "verify", "--root", "ontology", "--checkpoint-id", "cp.t1", cwd=workdir, capsys=capsys)
        assert code == ExitCode.FAIL
        assert "evidence corrupted: a/reopen_receipt.py " + digest in json.loads(out)["blockers"]

    def test_a_deleted_cas_object_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        digest = _sha256(workdir / "a" / "reopen_receipt.json")
        _cas_path(workdir, digest).unlink()
        code, report = _resume(workdir, capsys)
        assert code == 6 and report["resumable"] is False
        assert "evidence missing: a/reopen_receipt.json " + digest in report["blockers"]

    def test_a_snapshot_pointing_at_another_valid_blob_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        json_digest = _sha256(workdir / "a" / "reopen_receipt.json")
        py_digest = _sha256(workdir / "a" / "reopen_receipt.py")
        original = _checkpoint(workdir)
        snapshot = dict(original["snapshot"])
        snapshot["admittedSourceVersions"] = {"a/reopen_receipt.json": py_digest}   # the pre-fix binding
        # Mutation of committed bytes bypasses the new precommit gate deliberately.
        original["snapshot"] = snapshot
        original["logicalId"] = "cp.misbound"
        original["revisionId"] = digest_with("continuity.core.v2", original)
        (workdir / "ontology/checkpoints/cp.misbound.checkpoint.json").write_text(json.dumps(original))
        code, report = _resume(workdir, capsys, cp="cp.misbound")
        assert code == 6 and report["resumable"] is False
        assert ("evidence mis-bound: a/reopen_receipt.json record=" + json_digest + " snapshot=" + py_digest
                in report["blockers"])
        assert report["evidenceIntegrity"]["passed"] == 1 and report["evidenceIntegrity"]["checked"] == 2

    def test_verify_without_a_checkpoint_is_an_error(self, workdir, capsys):
        code, out = _run("task", "verify", "--root", "ontology", "--checkpoint-id", "cp.none", cwd=workdir, capsys=capsys)
        assert code == ExitCode.ERROR
        assert json.loads(out)["status"] == "ERROR"


# ---------------------------------------------------------------------------
# A1: the record's own seal, and ambiguity
# ---------------------------------------------------------------------------

class TestA1RecordSealAndAmbiguity:
    def test_an_edited_record_with_its_old_revision_id_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        name = evidence_record_name("ev.a/reopen_receipt.json") + ".json"
        path = workdir / "ontology" / "records" / name
        record = json.loads(path.read_text(encoding="utf-8"))
        py_digest = _sha256(workdir / "a" / "reopen_receipt.py")
        record["contentDigest"] = py_digest   # edited, revisionId untouched
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        code, report = _resume(workdir, capsys)
        assert code == 6 and report["resumable"] is False
        # `contentDigest` is a top-level self-field of continuity.core.v2 and is
        # therefore outside the record's own seal (the byte rule is frozen); the
        # edit is caught by the cross-check against the sealed snapshot instead.
        json_digest = _sha256(workdir / "a" / "reopen_receipt.json")
        assert report["evidenceIntegrity"]["blockers"] == [
            "evidence mis-bound: a/reopen_receipt.json record=" + py_digest + " snapshot=" + json_digest]

    def test_an_edited_subject_with_its_old_revision_id_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        name = evidence_record_name("ev.a/reopen_receipt.py") + ".json"
        path = workdir / "ontology" / "records" / name
        record = json.loads(path.read_text(encoding="utf-8"))
        record["subject"] = "a/other.py"
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        code, report = _resume(workdir, capsys)
        assert code == 6
        assert "evidence record unverified: a/other.py ev.a/reopen_receipt.py" in report["blockers"]

    def test_two_records_for_one_subject_with_different_digests_block_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        name = evidence_record_name("ev.a/reopen_receipt.json") + ".json"
        record = json.loads((workdir / "ontology" / "records" / name).read_text(encoding="utf-8"))
        rival = dict(record)
        rival["logicalId"] = "ev.rival"
        rival["contentDigest"] = _sha256(workdir / "a" / "reopen_receipt.py")
        rival = _reseal(rival)   # a correctly sealed second record naming the same subject
        (workdir / "ontology" / "records" / "evidence_rival.json").write_text(
            json.dumps(rival, indent=2, sort_keys=True), encoding="utf-8")
        code, report = _resume(workdir, capsys)
        assert code == 6 and report["resumable"] is False
        assert ("evidence ambiguous: a/reopen_receipt.json records=[ev.a/reopen_receipt.json, ev.rival]"
                in report["blockers"])


# ---------------------------------------------------------------------------
# A2: no CAS is NOT_RUN, and NOT_RUN is not PASS
# ---------------------------------------------------------------------------

class TestA2NoCasIsNotRun:
    def test_default_lookup_failure_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        shutil.copytree(workdir / "ontology" / "checkpoints", workdir / "elsewhere" / "checkpoints")
        code, report = _resume(workdir, capsys, root="elsewhere")
        assert code == 6 and report["resumable"] is False
        integrity = report["evidenceIntegrity"]
        assert integrity["status"] == "NOT_RUN"
        expected_cas = str(Path("elsewhere") / "cas")
        assert integrity["reason"] == "no CAS root found at " + expected_cas + "; pass --cas-root"
        assert report["evidenceIntegrity"]["blockers"] == ["evidence integrity not run: no CAS root found at " + expected_cas
                                      + "; pass --cas-root"]
        assert report["restoredFacts"]
        assert {f["status"] for f in integrity["findings"]} == {"NOT_RUN"}

    def test_an_invalid_explicit_cas_root_blocks_resume(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        code, report = _resume(workdir, capsys, "ontology", "cp.t1", "--cas-root", "no/such/cas")
        assert code == 6 and report["resumable"] is False
        assert report["evidenceIntegrity"]["status"] == "NOT_RUN"
        assert report["evidenceIntegrity"]["blockers"] == ["evidence integrity not run: explicit CAS root no" + os.sep + "such" + os.sep
                                      + "cas does not exist or is not a directory"]

    def test_an_explicit_valid_cas_root_lets_a_relocated_checkpoint_pass(self, workdir, capsys):
        assert _record(workdir, capsys, "a/reopen_receipt.json::source", "a/reopen_receipt.py")[0] == 0
        shutil.copytree(workdir / "ontology" / "checkpoints", workdir / "elsewhere" / "checkpoints")
        code, report = _resume(workdir, capsys, "elsewhere", "cp.t1",
                               "--cas-root", "ontology/cas", "--records-root", "ontology/records")
        assert code == 0 and report["evidenceIntegrity"]["status"] == "PASS"

    def test_only_a_checkpoint_with_no_evidence_references_is_resumable_unchecked(self, tmp_path):
        store = CheckpointStore(tmp_path / "checkpoints")
        store.commit("cp.empty", outcome_id="o", snapshot={
            "admittedSourceVersions": {}, "artifactRefs": {}, "planDigest": "sha256:" + "1" * 64,
            "contractDigests": {}, "implementationVersions": {}, "requiredFacts": [],
            "ephemeralBindings": [], "completeness": "AVAILABLE",
            "environmentBinding": {"hostId": "h", "interpreter": "cpython", "interpreterVersion": "3",
                                   "platform": "p", "unknownFields": []},
        }, last_sealed_event_seq=0, last_sealed_event_digest="sha256:" + "2" * 64,
            accepted_decisions=[], unresolved_claims=[], open_operations=[], next_legal_actions=["x"],
            recovery_policy_ref="rp.default.v1",
            closure_receipt={"closureKind": "STATE", "complete": True, "enumeratedMembers": [],
                             "expectedCount": 0, "observedCount": 0, "witnessRefs": [],
                             "scope": {"scopeKind": "required_facts", "selector": "cp.empty",
                                       "enumerationComplete": True}})
        report = store.resume("cp.empty")
        assert report.resumable is True
        assert report.as_dict()["evidenceIntegrity"] == {
            "status": "NOT_RUN", "reason": "the snapshot references no evidence",
            "checked": 0, "passed": 0, "findings": [], "blockers": []}


# ---------------------------------------------------------------------------
# F6: a checkpoint recorded under the old rule is read as it is
# ---------------------------------------------------------------------------

class TestF6PreFixCheckpointUnchanged:
    def test_the_fixture_loads_verifies_and_reports_the_collision_without_being_touched(self, capsys):
        before = {p.relative_to(FIXTURE).as_posix(): _sha256(p) for p in sorted(FIXTURE.rglob("*")) if p.is_file()}
        assert "records/evidence_ev_reopen_receipt.json" in before        # the stem-derived, overwritten record
        store = CheckpointStore(FIXTURE / "checkpoints")
        record = store.load("cp.prefix")                                  # verifies revisionId
        assert record["revisionId"] == "sha256:92fca6cb103a" + record["revisionId"][len("sha256:92fca6cb103a"):]
        py_digest = "sha256:150d529554ab3599e3e173d2b3f908f2f78f62b1c3936750a07b043bede561f2"
        json_digest = "sha256:ff4a2e9d4ba8fece6597cf53081902f18c6eaf961b02ae7082fe2d25c4fd158f"
        assert record["snapshot"]["admittedSourceVersions"] == {"a/reopen_receipt.json": py_digest}
        assert record["snapshot"]["artifactRefs"] == {"a/reopen_receipt.py": py_digest}
        assert ContentStore(FIXTURE_CAS).has(json_digest)                 # present in the CAS, unreferenced

        code, out = _run("resume", "--checkpoint-root", str(FIXTURE / "checkpoints"), "--checkpoint-id", "cp.prefix",
                         "--observed", '{"processId": 1}', "--cas-root", str(FIXTURE_CAS),
                         cwd=FIXTURE.parent, capsys=capsys)
        report = json.loads(out)
        assert code == 6 and report["resumable"] is False
        # Stem-derived IDs and record names legitimately fail the ID leg of
        # the chain; a pre-fix checkpoint is reported, never special-cased.
        assert report["evidenceIntegrity"]["blockers"] == [
            "evidence mis-bound: a/reopen_receipt.json record=none snapshot=" + py_digest,
            "evidence id mismatch: a/reopen_receipt.py record=ev.reopen_receipt expected=ev.a/reopen_receipt.py",
            "evidence record misplaced: a/reopen_receipt.py found=evidence_ev_reopen_receipt.json "
            "expected=evidence_ev.a+2freopen_receipt.py.json",
            "evidence record unexpected: evidence_ev_reopen_receipt.json subject=a/reopen_receipt.py",
            "evidence claim ids mismatch: extra=[ev.reopen_receipt] "
            "missing=[ev.a/reopen_receipt.json, ev.a/reopen_receipt.py]",
        ]
        assert report["evidenceIntegrity"]["checked"] == 2 and report["evidenceIntegrity"]["passed"] == 0
        assert report["evidenceIntegrity"]["claimChecked"] is True

        code, out = _run("task", "verify", "--root", str(FIXTURE), "--cas-root", str(FIXTURE_CAS),
                         cwd=FIXTURE.parent, capsys=capsys)
        assert code == ExitCode.FAIL
        assert json.loads(out)["blockers"] == report["blockers"]

        after = {p.relative_to(FIXTURE).as_posix(): _sha256(p) for p in sorted(FIXTURE.rglob("*")) if p.is_file()}
        assert after == before
