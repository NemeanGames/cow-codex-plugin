"""Evidence identity and evidence integrity.

Identity: an evidence entry's logical ID is a deterministic, *injective*
function of its path relative to the declared base. The whole normalized
relative path -- directories and extension included -- is carried in the ID
under a reversible escape, so two distinct relative paths never share an ID
and ``a/reopen_receipt.json`` and ``a/reopen_receipt.py`` are two records,
not one. The record file name is derived from the ID by the same escape over
a smaller safe set, so it stays injective on a case-folding filesystem.

Integrity: a checkpoint snapshot binds paths to content digests. Committing
or resuming over that snapshot is only sound when, for every path, the CAS
holds bytes that re-hash to the digest, a sealed Evidence record names that
path with the same digest, and the association is unambiguous. Nothing here
infers a binding from "some CAS blob matches"; a missing record is reported
as insufficient assurance, not repaired.

Every check here is producer-side tooling. A PASS from it is a consistency
result over the run's own records, not an independent audit.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, MutableSequence, Sequence

from ..canonical.profiles import digest_with
from ..claims.cas import CasError, ContentStore, DigestMismatch

__all__ = [
    "EvidencePathError",
    "EvidenceManifestError",
    "normalize_evidence_path",
    "evidence_id",
    "evidence_record_name",
    "unescape",
    "normalize_manifest_evidence",
    "missing_evidence_files",
    "seal_record",
    "verify_record_seal",
    "load_evidence_records",
    "snapshot_references",
    "evidence_record_name_for_path",
    "verify_evidence_bindings",
    "verify_run_root",
]

PROFILE = "continuity.core.v2"
SCHEMA_VERSION = "2.0.0"

ID_PREFIX = "ev."
RECORD_PREFIX = "evidence_"
RECORD_SUFFIX = ".json"
_ESCAPE = "+"
_HASH_SEPARATOR = "~"         # never produced by the escape, so the two name forms are disjoint
_ID_SAFE = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-")
_NAME_SAFE = frozenset("abcdefghijklmnopqrstuvwxyz0123456789._-")
_MAX_NAME_LENGTH = 120        # record file name bound (with suffix): far under every filesystem's
                              # 255-byte component limit, and short enough that a run root of
                              # ordinary depth stays inside Windows' 260-character default path limit
_NAME_PREFIX_KEEP = 40        # readable prefix kept in the hashed record-name form


class EvidencePathError(ValueError):
    """An evidence path cannot be expressed relative to the declared base."""


class EvidenceManifestError(ValueError):
    """Two evidence entries collide on ID or path; nothing has been written."""

    def __init__(self, reason: str, duplicate_ids: Sequence[str] = ()) -> None:
        super().__init__(reason)
        self.duplicate_ids = sorted(set(duplicate_ids))


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def _escape(text: str, safe: frozenset[str]) -> str:
    out: list[str] = []
    for byte in text.encode("utf-8"):
        char = chr(byte)
        if byte < 128 and char in safe and char != _ESCAPE:
            out.append(char)
        else:
            out.append("%s%02x" % (_ESCAPE, byte))
    return "".join(out)


def unescape(text: str) -> str:
    """Invert :func:`_escape`. ``+XX`` is one byte; anything else is itself."""
    raw = bytearray()
    i = 0
    while i < len(text):
        char = text[i]
        if char == _ESCAPE and i + 3 <= len(text) and _is_hex(text[i + 1:i + 3]):
            raw.append(int(text[i + 1:i + 3], 16))
            i += 3
        else:
            raw.extend(char.encode("utf-8"))
            i += 1
    return raw.decode("utf-8")


def _is_hex(pair: str) -> bool:
    return len(pair) == 2 and all(c in "0123456789abcdefABCDEF" for c in pair)


def normalize_evidence_path(path: str | os.PathLike[str], base: str | os.PathLike[str]) -> str:
    """The evidence path relative to ``base``: forward slashes, no ``.``/``..``, case kept.

    An absolute path is admitted only when it lies under ``base``. The result
    is lexical for relative inputs, so the ID does not depend on what the
    filesystem folds.
    """
    raw = str(path).strip()
    if not raw:
        raise EvidencePathError("evidence path is empty")
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            raw = candidate.resolve().relative_to(Path(base).resolve()).as_posix()
        except ValueError:
            raise EvidencePathError("evidence path " + repr(str(path)) + " lies outside the base "
                                    + repr(str(base))) from None
    parts = [seg for seg in raw.replace("\\", "/").split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise EvidencePathError("evidence path " + repr(str(path)) + " contains a parent segment; "
                                "evidence must lie under the base " + repr(str(base)))
    if not parts:
        raise EvidencePathError("evidence path " + repr(str(path)) + " names the base itself, not a file")
    return "/".join(parts)


def evidence_id(relpath: str) -> str:
    """``ev.`` + the reversibly escaped normalized relative path, always.

    Distinct relative paths give distinct IDs and :func:`unescape` recovers
    the path from every ID. There is no length cap and no hash fallback: the
    logical ID is a JSON string and must stay reversible for every valid
    relative path; only the record *file name* is bounded (see
    :func:`evidence_record_name`).
    """
    return ID_PREFIX + _escape(relpath, _ID_SAFE)


def evidence_record_name(ev_id: str) -> str:
    """``evidence_<...>``: a deterministic, collision-free file stem for an ID.

    The ID is escaped again over a case-folding-safe set, so two IDs that
    differ only in case or in a separator still name two files. When the
    full form would exceed the name bound, the name is a readable prefix plus
    ``~`` plus the full sha256 of the ID; ``~`` is never produced by the
    escape, so the two forms cannot collide with each other.
    The file name does not need to be reversible; the ID inside the record is.
    """
    encoded = _escape(ev_id, _NAME_SAFE)
    full = RECORD_PREFIX + encoded
    if len(full) + len(RECORD_SUFFIX) <= _MAX_NAME_LENGTH:
        return full
    return (RECORD_PREFIX + encoded[:_NAME_PREFIX_KEEP] + _HASH_SEPARATOR
            + hashlib.sha256(ev_id.encode("utf-8")).hexdigest())


def evidence_record_name_for_path(relpath: str) -> str:
    """The record file name (with suffix) the recorder writes for a path."""
    return evidence_record_name(evidence_id(relpath)) + RECORD_SUFFIX


def normalize_manifest_evidence(evidence: Sequence[MutableMapping[str, Any]],
                                base: str | os.PathLike[str], *, require_files: bool = False,
                                claim_evidence: MutableSequence[str] | None = None) -> None:
    """Preflight for a manifest's evidence list; mutates entries in place.

    Every ``path`` becomes its normalized relative form and every entry's
    ``id`` becomes :func:`evidence_id` of that path. An ``id`` a manifest
    supplies is an *alias*: it is checked for collisions, then every
    reference to it (``derivedFrom`` lists and ``claim_evidence``) is
    rewritten to the derived ID, so the sealed records carry derived IDs
    only. Raises :class:`EvidenceManifestError` when two entries share an
    alias or ID, share a normalized path, or bind one alias to two paths, or
    when ``claim_evidence`` does not list every evidence exactly once (an
    absent list defaults to every evidence, in manifest order); raises
    :class:`EvidencePathError` when, with ``require_files``, a listed file is
    absent or not a regular file under ``base``. Runs before anything is
    written, so a refusal leaves no partial run behind.
    """
    for entry in evidence:
        entry["path"] = normalize_evidence_path(entry["path"], base)
        entry["id"] = str(entry.get("id") or evidence_id(entry["path"]))

    paths_by_id: dict[str, list[str]] = {}
    ids_by_path: dict[str, list[str]] = {}
    for entry in evidence:
        paths_by_id.setdefault(entry["id"], []).append(entry["path"])
        ids_by_path.setdefault(entry["path"], []).append(entry["id"])

    reasons: list[str] = []
    duplicates: list[str] = []
    for ev_id, paths in paths_by_id.items():
        distinct = sorted(set(paths))
        if len(distinct) > 1:
            reasons.append("evidence id " + ev_id + " is bound to more than one path: " + ", ".join(distinct))
            duplicates.append(ev_id)
        elif len(paths) > 1:
            reasons.append("evidence id " + ev_id + " is declared " + str(len(paths)) + " times")
            duplicates.append(ev_id)
    for path, ids in ids_by_path.items():
        if len(ids) > 1 and len(set(ids)) > 1:
            reasons.append("evidence path " + path + " is declared more than once under ids " + ", ".join(sorted(set(ids))))
            duplicates.extend(ids)
    if reasons:
        raise EvidenceManifestError("; ".join(reasons), duplicates)

    # aliases -> derived ids; a derived id used directly maps to itself
    alias_to_id = {entry["id"]: evidence_id(entry["path"]) for entry in evidence}
    for entry in evidence:
        derived = alias_to_id[entry["id"]]
        if entry["id"] != derived:
            entry["alias"] = entry["id"]
        entry["id"] = derived
        if entry.get("derivedFrom"):
            entry["derivedFrom"] = [alias_to_id.get(str(d), str(d)) for d in entry["derivedFrom"]]
    derived_ids = [entry["id"] for entry in evidence]

    if claim_evidence is not None:
        listed = [alias_to_id.get(str(i), str(i)) for i in claim_evidence]
        if not listed:
            listed = list(derived_ids)
        extra = sorted(set(listed) - set(derived_ids))
        missing = sorted(set(derived_ids) - set(listed))
        repeated = sorted({i for i in listed if listed.count(i) > 1})
        if extra or missing or repeated:
            raise EvidenceManifestError(
                "claim.evidence must list every evidence id exactly once: extra=" + _fmt(extra)
                + " missing=" + _fmt(missing) + " repeated=" + _fmt(repeated),
                extra + missing + repeated)
        claim_evidence[:] = listed
    if require_files:
        missing_files = missing_evidence_files(evidence, base)
        if missing_files:
            raise EvidencePathError("evidence file(s) not found: " + ", ".join(missing_files))


def missing_evidence_files(evidence: Sequence[Mapping[str, Any]], base: str | os.PathLike[str]) -> list[str]:
    """Normalized paths that do not resolve to a regular file under ``base``."""
    root = Path(base)
    return [str(e["path"]) for e in evidence if not (root / str(e["path"])).is_file()]


# ---------------------------------------------------------------------------
# sealing and seal verification
# ---------------------------------------------------------------------------

def seal_record(record_type: str, logical_id: str, body: Mapping[str, Any],
                provenance: Mapping[str, Any], *, semantic_model_digest: str,
                created_at: str) -> dict[str, Any]:
    """A sealed record: envelope + body, ``revisionId`` = digest of everything else."""
    record: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "semanticModelDigest": semantic_model_digest,
        "recordType": record_type,
        "logicalId": logical_id,
        "hashProfile": PROFILE,
        "provenance": dict(provenance),
        "createdAt": created_at,
    }
    record.update(body)
    record["revisionId"] = digest_with(PROFILE, record)
    return record


def verify_record_seal(record: Mapping[str, Any]) -> bool:
    """Recompute a sealed record's ``revisionId`` the way ``CheckpointStore.load`` does.

    The ``continuity.core.v2`` byte rule strips a record's top-level self
    fields (``revisionId``, ``contentDigest``, ...) before hashing, so the
    seal covers ``subject``, ``logicalId``, provenance and the rest of the
    body but *not* the record's own ``contentDigest``. Binding of the digest
    to the path is therefore established by the cross-check against the
    sealed checkpoint snapshot and the CAS in
    :func:`verify_evidence_bindings`, never by this seal alone.
    """
    stored = record.get("revisionId")
    if not isinstance(stored, str):
        return False
    body = {k: v for k, v in record.items() if k != "revisionId"}
    try:
        return digest_with(str(record.get("hashProfile") or PROFILE), body) == stored
    except (KeyError, TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# integrity
# ---------------------------------------------------------------------------

def load_evidence_records(records_root: str | os.PathLike[str]) -> dict[str, dict[str, Any]]:
    """Every ``Evidence`` record under a run's ``records/`` directory, keyed by file name.

    Every ``*.json`` file is read, whatever its name: a record that was
    renamed away from its derived file name must still be seen so that the
    misplacement is reported rather than silently ignored.
    """
    root = Path(records_root)
    found: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return found
    for path in sorted(root.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and record.get("recordType") == "Evidence":
            found[path.name] = record
    return found


def snapshot_references(snapshot: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """``(section, path, digest)`` for every evidence reference in a snapshot."""
    refs: list[tuple[str, str, str]] = []
    for section in ("admittedSourceVersions", "artifactRefs"):
        entries = snapshot.get(section) or {}
        if isinstance(entries, Mapping):
            for path, digest in entries.items():
                refs.append((section, str(path), str(digest)))
    return refs


def _fmt(values: Iterable[str]) -> str:
    return "[" + ", ".join(sorted(str(v) for v in values)) + "]"


def verify_evidence_bindings(
    snapshot: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    cas: ContentStore,
    *,
    expected: Mapping[str, str] | None = None,
    referenced: Iterable[str] = (),
    witness_refs: Iterable[str] | None = None,
    claim: Mapping[str, Any] | None = None,
    claim_evidence: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Check the full association chain for every snapshot path.

    For each path ``P`` bound to digest ``D`` in the snapshot:

    1. exactly one sealed Evidence record has ``subject == P`` and it carries
       ``contentDigest == D`` (``evidence mis-bound`` / ``evidence ambiguous``);
    2. that record's ``logicalId`` is :func:`evidence_id` of ``P``
       (``evidence id mismatch``);
    3. no two records share a ``logicalId`` (``evidence duplicate id``);
    4. the record lives under the file name derived from its ID and no
       Evidence record lives under any other name (``evidence record
       misplaced`` / ``evidence record unexpected``);
    5. the CAS returns bytes that re-hash to ``D`` (``evidence missing`` /
       ``evidence corrupted``);
    6. the witness refs and the claim's evidence refs / evidence IDs equal
       the snapshot's digests / derived IDs, no extra and none missing
       (``evidence witness mismatch`` / ``evidence claim refs mismatch`` /
       ``evidence claim ids mismatch``).

    ``records`` maps file name -> record (a bare iterable is accepted for
    callers that have no file names; step 4 is then skipped and reported as
    ``recordNamesChecked: false``). ``expected`` (record time only) maps each
    manifest path to the digest just computed for that file; ``referenced``
    lists digests cited elsewhere that must all belong to a snapshot entry;
    ``claim`` is the sealed Claim record; ``claim_evidence`` the manifest's
    ID list. The result names every finding; ``blockers`` is the flat list a
    caller refuses on.
    """
    findings: list[dict[str, Any]] = []
    blockers: list[str] = []

    if isinstance(records, Mapping):
        named_records: list[tuple[str | None, Mapping[str, Any]]] = [(name, rec) for name, rec in records.items()]
        names_known = True
    else:
        named_records = [(None, rec) for rec in records]
        names_known = False

    by_subject: dict[str, list[tuple[str | None, Mapping[str, Any]]]] = {}
    by_id: dict[str, list[str]] = {}
    for name, record in named_records:
        subject = str(record.get("subject"))
        if not verify_record_seal(record):
            blockers.append("evidence record unverified: " + subject + " " + str(record.get("logicalId")))
            continue
        by_subject.setdefault(subject, []).append((name, record))
        by_id.setdefault(str(record.get("logicalId")), []).append(subject)
    for ev_id, subjects in sorted(by_id.items()):
        if len(subjects) > 1:
            blockers.append("evidence duplicate id: " + ev_id + " subjects=" + _fmt(subjects))

    refs = snapshot_references(snapshot)
    snapshot_paths = {path for _, path, _ in refs}
    expected_names = {evidence_record_name_for_path(path) for path in snapshot_paths}
    passed = 0
    for section, path, digest in refs:
        problems: list[str] = []
        if expected is not None:
            if path not in expected:
                problems.append("evidence mis-bound: " + path + " is in the snapshot but not in the manifest")
            elif expected[path] != digest:
                problems.append("evidence mis-bound: " + path + " expected=" + expected[path] + " snapshot=" + digest)
        if not cas.has(digest):
            problems.append("evidence missing: " + path + " " + digest)
        else:
            try:
                cas.get_bytes(digest)
            except DigestMismatch:
                problems.append("evidence corrupted: " + path + " " + digest)
            except CasError:
                problems.append("evidence missing: " + path + " " + digest)
        named = by_subject.get(path, [])
        if not named:
            problems.append("evidence mis-bound: " + path + " record=none snapshot=" + digest)
        elif len(named) > 1:
            problems.append("evidence ambiguous: " + path + " records="
                            + _fmt(str(r.get("logicalId")) for _, r in named))
        else:
            name, record = named[0]
            record_digest = str(record.get("contentDigest"))
            if record_digest != digest:
                problems.append("evidence mis-bound: " + path + " record=" + record_digest + " snapshot=" + digest)
            record_id = str(record.get("logicalId"))
            derived_id = evidence_id(path)
            if record_id != derived_id:
                problems.append("evidence id mismatch: " + path + " record=" + record_id + " expected=" + derived_id)
            if names_known:
                expected_name = evidence_record_name_for_path(path)
                if name != expected_name:
                    problems.append("evidence record misplaced: " + path + " found=" + str(name)
                                    + " expected=" + expected_name)
        finding = {"section": section, "path": path, "digest": digest,
                   "status": "PASS" if not problems else "FAIL", "problems": problems}
        findings.append(finding)
        if problems:
            blockers.extend(problems)
        else:
            passed += 1

    if names_known:
        for name, record in named_records:
            if name not in expected_names:
                blockers.append("evidence record unexpected: " + str(name) + " subject=" + str(record.get("subject")))

    known = {digest for _, _, digest in refs}
    if expected is not None:
        for path in sorted(set(expected) - snapshot_paths):
            blockers.append("evidence mis-bound: " + path + " expected=" + expected[path] + " snapshot=none")
    for ref in referenced:
        if ref not in known:
            blockers.append("evidence reference outside the manifest: " + str(ref))

    derived_ids = {evidence_id(path) for path in snapshot_paths}
    if witness_refs is not None:
        witnesses = {str(w) for w in witness_refs}
        if witnesses != known:
            blockers.append("evidence witness mismatch: extra=" + _fmt(witnesses - known)
                            + " missing=" + _fmt(known - witnesses))
    claim_checked = False
    if claim is not None:
        claim_checked = True
        assertion = claim.get("producerAssertion") or {}
        claim_refs = {str(d) for d in (assertion.get("evidenceRefs") or [])}
        if claim_refs != known:
            blockers.append("evidence claim refs mismatch: extra=" + _fmt(claim_refs - known)
                            + " missing=" + _fmt(known - claim_refs))
        # a requirementId is "r." + the evidence id without its "ev." prefix
        claim_ids = {ID_PREFIX + str(r.get("requirementId"))[2:] for r in (claim.get("requiredEvidence") or [])}
        if claim_ids != derived_ids:
            blockers.append("evidence claim ids mismatch: extra=" + _fmt(claim_ids - derived_ids)
                            + " missing=" + _fmt(derived_ids - claim_ids))
    if claim_evidence is not None:
        listed = [str(i) for i in claim_evidence]
        if set(listed) != derived_ids or len(listed) != len(set(listed)):
            blockers.append("evidence claim ids mismatch: extra=" + _fmt(set(listed) - derived_ids)
                            + " missing=" + _fmt(derived_ids - set(listed)))

    return {
        "status": "PASS" if not blockers else "FAIL",
        "checked": len(refs),
        "passed": passed,
        "recordNamesChecked": names_known,
        "claimChecked": claim_checked,
        "findings": findings,
        "blockers": blockers,
    }


def verify_run_root(root: str | os.PathLike[str], checkpoint_id: str | None = None,
                    *, cas_root: str | os.PathLike[str] | None = None,
                    records_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """The integrity pass over an existing run root, after the fact.

    Loads the checkpoint (which verifies its own ``revisionId``), then runs
    :func:`verify_evidence_bindings` against ``<root>/cas`` and
    ``<root>/records``. Nothing is rewritten.
    """
    from .store import CheckpointStore

    run_root = Path(root)
    store = CheckpointStore(run_root / "checkpoints", cas_root=cas_root, records_root=records_root)
    if checkpoint_id is None:
        candidates = sorted(store.root.glob("*.checkpoint.json"))
        if len(candidates) != 1:
            raise ValueError("pass --checkpoint-id: found " + str(len(candidates))
                             + " checkpoint(s) under " + str(store.root))
        checkpoint_id = candidates[0].name[: -len(".checkpoint.json")]
    record = store.load(checkpoint_id)
    result = store.evidence_integrity(record)
    from .claim_integrity import combined_status
    claims = store.claim_integrity(record)
    evidence = dict(result)
    result["claimIntegrity"] = claims
    result["evidenceIntegrity"] = evidence
    result["status"] = combined_status(result["status"], claims["status"])
    if evidence["status"] == "NOT_RUN" and evidence["blockers"] and result["status"] == "PASS":
        result["status"] = "NOT_RUN"
    result["blockers"] = list(result["blockers"]) + claims["blockers"]
    result["checkpointId"] = checkpoint_id
    result["revisionId"] = record.get("revisionId")
    return result
