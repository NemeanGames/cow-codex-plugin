"""Deterministic local artifact packaging and verification.

This is a real, executable capability, not a stand-in. It is what the
end-to-end acceptance run actually performs, so the trace it produces is an
observed trace rather than a synthesized one.

It has no vendor usage. That is stated rather than hidden: a real local trace
supports timing, replay and correctness claims and supports no measured
token-reduction claim at all.

Packaging is reproducible. Archive member order is sorted, timestamps are
fixed, and permissions are normalized, so the same inputs produce byte
identical output on two clean runs.
"""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from continuity_ontology.canonical.profiles import digest_with
from continuity_ontology.trace.precision import duration_precision, monotonic_resolution_ns

__all__ = [
    "PackagingError",
    "PathEscape",
    "MemberDigestMismatch",
    "package",
    "verify",
    "FIXED_TIMESTAMP",
]

#: A fixed DOS timestamp so archives do not vary with wall-clock time.
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

_MAX_MEMBER_BYTES = 64 * 1024 * 1024
_MAX_MEMBERS = 10_000


class PackagingError(ValueError):
    """Base class for packaging failures."""


class PathEscape(PackagingError):
    """A member resolved outside the declared root."""


class MemberDigestMismatch(PackagingError):
    """A member's bytes do not match the manifest."""


def _safe_relative(root: Path, target: Path) -> str:
    resolved = target.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and not str(resolved).startswith(str(root_resolved) + os.sep):
        raise PathEscape(str(target) + " resolves outside the declared root")
    return str(resolved.relative_to(root_resolved)).replace("\\", "/")


def package(
    root: str | os.PathLike[str],
    members: Sequence[str],
    output_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Package declared members into a reproducible archive."""
    root_path = Path(root)
    if len(members) > _MAX_MEMBERS:
        raise PackagingError("member count exceeds the bound of " + str(_MAX_MEMBERS))

    entries: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for member in members:
        target = root_path / member
        rel = _safe_relative(root_path, target)
        if rel in seen:
            raise PackagingError("duplicate member " + rel)
        seen.add(rel)
        if not target.exists():
            raise PackagingError("declared member does not exist: " + rel)
        payload = target.read_bytes()
        if len(payload) > _MAX_MEMBER_BYTES:
            raise PackagingError("member " + rel + " exceeds the size bound")
        entries.append((rel, payload))

    entries.sort(key=lambda e: e[0])
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic_ns()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel, payload in entries:
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIMESTAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    finished = time.monotonic_ns()

    manifest = {
        "schema": "ont20.payload-manifest/1",
        "memberDigests": {rel: digest_with("raw.file.sha256", payload) for rel, payload in entries},
        "memberCount": len(entries),
        "archiveDigest": digest_with("raw.file.sha256", output.read_bytes()),
        "reproducibility": {
            "memberOrder": "sorted",
            "timestamps": "fixed 1980-01-01",
            "permissions": "normalized 0644",
        },
    }
    return {
        "manifest": manifest,
        "archivePath": str(output),
        "startedNs": started,
        "finishedNs": finished,
        "durationMs": (finished - started) / 1_000_000.0,
        **duration_precision(finished - started, monotonic_resolution_ns()),
        "vendorUsage": {
            "basis": "NOT_APPLICABLE",
            "note": (
                "this operation makes no provider call; it is token-free for this measured "
                "scope, which is not a claim about surrounding model work"
            ),
        },
    }


def verify(
    archive_path: str | os.PathLike[str],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify an archive against its manifest without extracting it."""
    path = Path(archive_path)
    if not path.exists():
        return {"status": "UNKNOWN", "reason": "archive not found at " + str(path), "checked": 0}

    archive_digest = digest_with("raw.file.sha256", path.read_bytes())
    expected_members = dict(manifest.get("memberDigests", {}))
    findings: list[dict[str, str]] = []
    checked = 0

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            normalized = name.replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                findings.append({"member": name, "issue": "unsafe archive path"})
                continue
            if normalized not in expected_members:
                findings.append({"member": name, "issue": "member is not in the manifest"})
                continue
            actual = digest_with("raw.file.sha256", archive.read(name))
            checked += 1
            if actual != expected_members[normalized]:
                findings.append({"member": name, "issue": "digest mismatch"})
        missing = sorted(set(expected_members) - {n.replace("\\", "/") for n in names})
        for name in missing:
            findings.append({"member": name, "issue": "manifest member absent from the archive"})

    archive_matches = archive_digest == manifest.get("archiveDigest")
    if findings:
        return {
            "status": "FAIL",
            "reason": "; ".join(f["member"] + ": " + f["issue"] for f in findings),
            "findings": findings,
            "memberStatus": "FAIL",
            "archiveDigestMatches": archive_matches,
            "checked": checked,
            "archiveDigest": archive_digest,
        }
    return {
        "status": "PASS" if archive_matches else "FAIL",
        "memberStatus": "PASS",
        "reason": "every manifest member is present and its digest matches" if archive_matches else "archive digest mismatch; member digests match",
        "checked": checked,
        "archiveDigest": archive_digest,
        "archiveDigestMatches": archive_digest == manifest.get("archiveDigest"),
    }
