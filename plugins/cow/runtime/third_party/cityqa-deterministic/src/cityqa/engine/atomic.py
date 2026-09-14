"""Atomic authoritative writes (IMPLEMENTATION DIRECTIVE section 17).

Every authoritative JSON or manifest write follows the same sequence:

    temporary file -> write -> flush -> fsync -> atomic rename

A partial write is a harness ERROR, never a product failure. Callers that catch
:class:`AtomicWriteError` must classify it in the ``harness`` defect domain.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .canonical import canonical_bytes, canonical_path
from .hashing import digest_bytes, digest_file

__all__ = [
    "AtomicWriteError",
    "write_bytes",
    "write_json",
    "write_jsonl",
    "write_text",
    "write_directory_manifest",
    "OutputRecord",
]


class AtomicWriteError(OSError):
    """Raised when an authoritative write could not be completed atomically."""


class OutputRecord:
    """A written artifact and the digest of the bytes that were written."""

    __slots__ = ("path", "digest", "size")

    def __init__(self, path: Path, digest: str, size: int) -> None:
        self.path = path
        self.digest = digest
        self.size = size

    def as_dict(self, root: Path | None = None) -> dict[str, Any]:
        location = self.path
        if root is not None:
            try:
                location = self.path.relative_to(root)
            except ValueError:
                location = self.path
        return {
            "path": canonical_path(str(location)),
            "digest": self.digest,
            "sizeBytes": self.size,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "OutputRecord(%s, %s)" % (self.path, self.digest)


def _fsync_directory(directory: Path) -> None:
    """Flush the directory entry so the rename survives a crash.

    Windows has no directory fsync; the failure is expected there and is not an
    error, so it is swallowed rather than reported as a partial write.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_bytes(path: str | os.PathLike[str], payload: bytes) -> OutputRecord:
    """Write ``payload`` to ``path`` atomically and return its record."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix="." + target.name + ".",
            suffix=".partial",
            dir=str(target.parent),
        )
        temporary = Path(temporary_name)
        handle = os.fdopen(fd, "wb")
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temporary, target)
        temporary = None
        _fsync_directory(target.parent)
    except OSError as exc:
        raise AtomicWriteError(
            "atomic write of " + str(target) + " did not complete: " + str(exc)
        ) from exc
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
    return OutputRecord(target, digest_bytes(payload), len(payload))


def write_json(path: str | os.PathLike[str], value: Any) -> OutputRecord:
    """Write a canonical JSON document atomically."""
    return write_bytes(path, canonical_bytes(value))


def write_jsonl(path: str | os.PathLike[str], rows: Iterable[Any]) -> OutputRecord:
    """Write canonical JSON Lines atomically, one canonical record per line."""
    from .canonical import canonical_text

    body = "".join(canonical_text(row) + "\n" for row in rows)
    return write_bytes(path, body.encode("utf-8"))


def write_text(path: str | os.PathLike[str], text: str) -> OutputRecord:
    """Write UTF-8 text atomically with exactly one terminal newline."""
    if not text.endswith("\n"):
        text = text + "\n"
    return write_bytes(path, text.encode("utf-8"))


def write_directory_manifest(directory: str | os.PathLike[str]) -> tuple[OutputRecord, OutputRecord]:
    """Emit ``MANIFEST.json`` and ``MANIFEST.sha256`` for an output directory.

    Every output directory receives both, per directive section 17. The manifest
    indexes every file in the directory except the two manifest files
    themselves, which cannot describe their own bytes.
    """
    root = Path(directory)
    skip = {"MANIFEST.json", "MANIFEST.sha256"}
    entries: list[dict[str, Any]] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            if filename in skip and Path(current) == root:
                continue
            absolute = Path(current) / filename
            relative = canonical_path(str(absolute.relative_to(root)))
            entries.append(
                {
                    "path": relative,
                    "digest": digest_file(absolute),
                    "sizeBytes": absolute.stat().st_size,
                }
            )
    entries.sort(key=lambda entry: entry["path"])
    manifest = {
        "schemaVersion": "1.0.0",
        "manifestType": "DirectoryManifest",
        "entryCount": len(entries),
        "entries": entries,
    }
    json_record = write_json(root / "MANIFEST.json", manifest)
    lines = "".join(
        entry["digest"].split(":", 1)[1] + "  " + entry["path"] + "\n" for entry in entries
    )
    sha_record = write_text(root / "MANIFEST.sha256", lines.rstrip("\n"))
    return json_record, sha_record
