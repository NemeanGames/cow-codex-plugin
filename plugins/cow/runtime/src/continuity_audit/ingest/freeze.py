"""Audit-input freeze and read-only ingestion.

The auditor receives a sealed reading list, not the worker's writable scratch
tree. :func:`freeze_audit_input` produces that list; :class:`AuditInput` reads
only what the list names and refuses anything whose bytes have changed since
the freeze.

There is no write path in this module. The auditor cannot patch a candidate,
and the absence of a write function is the enforcement, not a comment asking
it not to.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from continuity_ontology.canonical.profiles import digest_with

__all__ = ["AuditInputError", "InputDrift", "freeze_audit_input", "AuditInput"]


class AuditInputError(ValueError):
    """Raised when the audit input cannot be read as frozen."""


class InputDrift(AuditInputError):
    """Raised when an input's bytes changed after the freeze."""


def freeze_audit_input(
    candidate_root: str | os.PathLike[str],
    reading_list: Sequence[str],
    *,
    candidate_digest: str,
    frozen_at: str,
) -> dict[str, Any]:
    """Seal the exact files the auditor is permitted to read."""
    root = Path(candidate_root).resolve()
    members: dict[str, str] = {}
    missing: list[str] = []
    for rel in sorted(set(reading_list)):
        target = (root / rel).resolve()
        if not str(target).startswith(str(root) + os.sep) and target != root:
            raise AuditInputError("reading list entry escapes the candidate root: " + rel)
        if not target.exists():
            missing.append(rel)
            continue
        members[rel.replace("\\", "/")] = digest_with("raw.file.sha256", target.read_bytes())
    manifest = {
        "schema": "ont20.audit-input-manifest/1",
        "candidateRoot": str(root),
        "candidateDigest": candidate_digest,
        "frozenAt": frozen_at,
        "members": members,
        "missing": missing,
        "note": (
            "This is the complete set of inputs the auditor may read. Anything not "
            "listed here is outside the audit's evidence base, and a missing entry is "
            "reported rather than substituted."
        ),
    }
    manifest["manifestDigest"] = digest_with("continuity.core.v2", manifest)
    return manifest


class AuditInput:
    """Read-only accessor bound to a frozen manifest."""

    def __init__(self, manifest: Mapping[str, Any]) -> None:
        self.manifest = dict(manifest)
        self.root = Path(str(manifest["candidateRoot"]))
        self.members: dict[str, str] = dict(manifest["members"])
        stored = self.manifest.pop("manifestDigest", None)
        recomputed = digest_with("continuity.core.v2", self.manifest)
        self.manifest["manifestDigest"] = stored
        if stored != recomputed:
            raise AuditInputError("the audit input manifest does not match its own digest")
        self.digest = stored

    def read_bytes(self, rel: str) -> bytes:
        key = rel.replace("\\", "/")
        if key not in self.members:
            raise AuditInputError(
                repr(rel) + " is not in the frozen reading list; the auditor reads only "
                "what was sealed for it"
            )
        target = self.root / key
        payload = target.read_bytes()
        actual = digest_with("raw.file.sha256", payload)
        if actual != self.members[key]:
            raise InputDrift(
                repr(rel) + " changed after the freeze: expected " + self.members[key]
                + ", read " + actual
            )
        return payload

    def read_json(self, rel: str) -> Any:
        return json.loads(self.read_bytes(rel).decode("utf-8"))

    def entries(self) -> tuple[str, ...]:
        return tuple(sorted(self.members))

    def missing(self) -> tuple[str, ...]:
        return tuple(self.manifest.get("missing", ()))
