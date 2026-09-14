"""Content-addressed evidence store.

Evidence is stored once by content digest; roles, subjects and scopes live in
manifests that reference it. Storing the same bytes twice therefore produces
one object and two references, which is what keeps a delta bundle from
recopying unchanged evidence.

Writes go through the CityQA atomic-write primitives rather than a second file
engine. A failed write leaves no partially visible object: only a complete,
digest-verified commit becomes readable.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from cityqa.engine.atomic import write_bytes

from ..canonical.profiles import digest_with

__all__ = ["CasError", "DigestMismatch", "UnsafeObjectPath", "ContentStore"]

_MAX_OBJECT_BYTES = 64 * 1024 * 1024


class CasError(ValueError):
    """Base class for content-store failures."""


class DigestMismatch(CasError):
    """Stored bytes do not hash to the digest they are filed under."""


class UnsafeObjectPath(CasError):
    """A digest did not resolve to a path inside the store root."""


class ContentStore:
    """A two-level sharded store keyed by ``sha256:<hex>``."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        Path(root).mkdir(parents=True, exist_ok=True)
        self.root = Path(root).resolve()
        self._writes = 0
        self._deduplicated = 0

    # -- addressing --------------------------------------------------------

    def _path_for(self, digest: str) -> Path:
        """Resolve a content address to a path inside the store.

        Containment rests on the digest grammar, not on filesystem state: the
        address must be ``sha256:`` followed by exactly 64 lowercase hex
        characters, which cannot contain a separator, a drive letter or a
        parent reference. Deliberately no ``resolve()`` call here -- resolving
        a path whose parents another thread is concurrently creating returns
        different forms before and after creation, which made a correct address
        look like an escape under contention.
        """
        if not digest.startswith("sha256:"):
            raise UnsafeObjectPath("content addresses are prefixed digests, got " + repr(digest))
        hexpart = digest[len("sha256:"):]
        if len(hexpart) != 64 or any(c not in "0123456789abcdef" for c in hexpart):
            raise UnsafeObjectPath("malformed content address " + repr(digest))
        return self.root / hexpart[:2] / hexpart[2:4] / hexpart

    # -- writing -----------------------------------------------------------

    def put_bytes(self, payload: bytes) -> str:
        if len(payload) > _MAX_OBJECT_BYTES:
            raise CasError("object exceeds the " + str(_MAX_OBJECT_BYTES) + " byte bound")
        digest = digest_with("raw.file.sha256", payload)
        path = self._path_for(digest)
        if path.exists():
            if path.read_bytes() != payload:
                raise DigestMismatch(
                    "digest collision or corrupted object at " + digest
                )
            self._deduplicated += 1
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            write_bytes(path, payload)
        except OSError as exc:
            # Two writers can race on one content address. On Windows the loser
            # sees WinError 5 from the rename, and for a short window the target
            # is not yet readable either. Because the address *is* the content,
            # losing that race is not a failure -- the winner stored identical
            # bytes. Confirm that rather than assume it.
            settled = self._read_when_settled(path)
            if settled is None:
                raise
            if settled != payload:
                raise DigestMismatch(
                    "a concurrent write left different bytes at " + digest
                ) from exc
            self._deduplicated += 1
            return digest
        self._writes += 1
        return digest

    @staticmethod
    def _read_when_settled(path: Path, attempts: int = 40, delay: float = 0.005) -> bytes | None:
        """Read a path that a concurrent writer may still be renaming into place.

        This retries a *transport-class* failure only: a sharing violation on a
        file another thread is replacing. It never retries a content mismatch,
        which is a semantic result and is reported on the first read that
        succeeds. Bounded at roughly 200ms so a genuinely failed write surfaces
        as a failure rather than a hang.
        """
        for attempt in range(attempts):
            try:
                if path.exists():
                    return path.read_bytes()
            except OSError:
                pass
            if attempt < attempts - 1:
                time.sleep(delay)
        return None

    def put_value(self, value: Any) -> str:
        """Store a JSON value under its canonical v2 bytes."""
        from cityqa.engine.canonical import canonical_bytes

        return self.put_bytes(canonical_bytes(value))

    def put_file(self, path: str | os.PathLike[str]) -> str:
        return self.put_bytes(Path(path).read_bytes())

    # -- reading -----------------------------------------------------------

    def has(self, digest: str) -> bool:
        try:
            return self._path_for(digest).exists()
        except UnsafeObjectPath:
            return False

    def get_bytes(self, digest: str) -> bytes:
        path = self._path_for(digest)
        if not path.exists():
            raise CasError("no object for " + digest)
        payload = path.read_bytes()
        recomputed = digest_with("raw.file.sha256", payload)
        if recomputed != digest:
            raise DigestMismatch(
                "object at " + digest + " hashes to " + recomputed + "; the store is corrupt"
            )
        return payload

    def get_value(self, digest: str) -> Any:
        return json.loads(self.get_bytes(digest).decode("utf-8"))

    def verify_all(self) -> dict[str, Any]:
        """Rehash every object. Used by the audit-input freeze."""
        checked = 0
        corrupt: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            expected = "sha256:" + path.name
            payload = path.read_bytes()
            if digest_with("raw.file.sha256", payload) != expected:
                corrupt.append(expected)
            checked += 1
        return {"objectsChecked": checked, "corrupt": corrupt, "intact": not corrupt}

    def statistics(self) -> dict[str, int]:
        return {
            "objectsWritten": self._writes,
            "duplicateWritesAvoided": self._deduplicated,
        }

    def __iter__(self) -> Iterator[str]:
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                yield "sha256:" + path.name

    def __len__(self) -> int:
        return sum(1 for _ in self)
