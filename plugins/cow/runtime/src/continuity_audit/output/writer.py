"""Audit output, written to a separate root the producer does not own."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from cityqa.engine.atomic import write_bytes

from continuity_ontology.canonical.profiles import digest_with

__all__ = ["AuditOutputError", "AuditWriter"]


class AuditOutputError(ValueError):
    """Raised when the audit output root is unusable."""


class AuditWriter:
    """Writes audit results into an output root outside the candidate."""

    def __init__(self, output_root: str | os.PathLike[str], candidate_root: str | os.PathLike[str]) -> None:
        self.output_root = Path(output_root).resolve()
        candidate = Path(candidate_root).resolve()
        if self.output_root == candidate or str(self.output_root).startswith(str(candidate) + os.sep):
            raise AuditOutputError(
                "the audit output root lies inside the candidate root; an auditor writes "
                "to its own root so it cannot patch what it is auditing"
            )
        self.output_root.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, value: Mapping[str, Any]) -> dict[str, str]:
        safe = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        target = self.output_root / safe
        write_bytes(target, payload)
        return {
            "path": str(target),
            "digest": digest_with("raw.file.sha256", payload),
            "bytes": str(len(payload)),
        }
