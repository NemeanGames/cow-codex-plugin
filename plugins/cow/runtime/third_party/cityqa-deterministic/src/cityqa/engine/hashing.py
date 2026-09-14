"""SHA-256 digests over defined bytes.

Terminology is fixed by directive section 2. A digest establishes *content
identity*. It is not a signature and it authorizes nothing. Receipts produced by
this suite are therefore described as HASH-BOUND, never as signed, until an
asymmetric signing implementation exists.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .canonical import canonical_bytes, canonical_path

__all__ = [
    "DIGEST_PREFIX",
    "NULL_DIGEST",
    "digest_bytes",
    "digest_file",
    "digest_value",
    "digest_tree",
    "digest_mapping_of_files",
    "is_digest",
    "short_digest",
]

DIGEST_PREFIX = "sha256:"

# Digest of the empty byte string. Used where a digest slot must be present but
# the artifact is genuinely absent; it is never treated as a match.
NULL_DIGEST = DIGEST_PREFIX + hashlib.sha256(b"").hexdigest()

_CHUNK = 1 << 20


def digest_bytes(payload: bytes) -> str:
    """Return the prefixed SHA-256 digest of ``payload``."""
    return DIGEST_PREFIX + hashlib.sha256(payload).hexdigest()


def digest_file(path: str | os.PathLike[str]) -> str:
    """Return the prefixed SHA-256 digest of a file's raw bytes."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return DIGEST_PREFIX + hasher.hexdigest()


def digest_value(value: Any) -> str:
    """Return the semantic digest of a canonicalized value."""
    return digest_bytes(canonical_bytes(value))


def digest_tree(
    root: str | os.PathLike[str],
    exclude_names: Iterable[str] = (),
    exclude_suffixes: Iterable[str] = (),
) -> tuple[str, dict[str, str]]:
    """Digest a directory tree.

    Returns the tree digest and the per-file index that produced it. The index
    is keyed by logical (forward-slash, root-relative) path so the digest does
    not vary with the absolute location of the tree or the host separator.
    """
    root_path = Path(root)
    names = frozenset(exclude_names)
    suffixes = tuple(exclude_suffixes)
    index: dict[str, str] = {}
    for current, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(name for name in dirnames if name not in names)
        for filename in sorted(filenames):
            if filename in names or (suffixes and filename.endswith(suffixes)):
                continue
            absolute = Path(current) / filename
            relative = canonical_path(str(absolute.relative_to(root_path)))
            index[relative] = digest_file(absolute)
    return digest_value({"files": index}), index


def digest_mapping_of_files(paths: Mapping[str, str | os.PathLike[str]]) -> dict[str, str]:
    """Digest a named set of files, keyed by the caller's logical names."""
    return {name: digest_file(paths[name]) for name in sorted(paths)}


def is_digest(value: Any) -> bool:
    """True when ``value`` is a well-formed prefixed SHA-256 digest."""
    if not isinstance(value, str) or not value.startswith(DIGEST_PREFIX):
        return False
    hexpart = value[len(DIGEST_PREFIX):]
    if len(hexpart) != 64:
        return False
    return all(char in "0123456789abcdef" for char in hexpart)


def short_digest(value: str, width: int = 12) -> str:
    """Return a display-only abbreviation. Never used for comparison."""
    if not is_digest(value):
        return str(value)
    return value[len(DIGEST_PREFIX):][:width]
