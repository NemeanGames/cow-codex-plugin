"""Environment and implementation identity.

Two digests bind a run to the machinery that produced it:

    environmentIdentityDigest   interpreter, platform and provider identity
    implementationDigest        the source bytes of the suite itself

Both enter the probe cache key. A probe result cached under one implementation
is never reused under another, which is what stops a fixed probe from silently
serving a stale PASS.

Nothing here is wall-clock dependent: a timestamp in an identity digest would
make every run a cache miss and every comparison meaningless.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

from .hashing import digest_value

__all__ = [
    "environment_identity",
    "implementation_digest",
    "dependency_lock_digest",
    "execution_path_identity",
    "PRODUCTION_EXECUTION_PATH",
    "FIXTURE_EXECUTION_PATH",
]

PRODUCTION_EXECUTION_PATH = "producer.production"
FIXTURE_EXECUTION_PATH = "producer.fixture"


def environment_identity(provider: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Describe the execution environment in stable, comparable terms.

    Username, hostname, process id and wall-clock time are deliberately absent.
    They vary between two runs that ought to be identical.
    """
    record = {
        "pythonImplementation": platform.python_implementation(),
        "pythonVersion": platform.python_version(),
        "pythonApiVersion": "%d.%d" % sys.version_info[:2],
        "platformSystem": platform.system(),
        "platformRelease": platform.release(),
        "platformMachine": platform.machine(),
        "byteOrder": sys.byteorder,
        "maxUnicode": sys.maxunicode,
        "filesystemEncoding": sys.getfilesystemencoding(),
        "provider": dict(provider) if provider else {},
    }
    record["digest"] = digest_value(record)
    return record


def _source_index(root: Path) -> dict[str, str]:
    from .canonical import canonical_path
    from .hashing import digest_file

    index: dict[str, str] = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if name not in {"__pycache__", ".pytest_cache"}
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            absolute = Path(current) / filename
            relative = canonical_path(str(absolute.relative_to(root)))
            index[relative] = digest_file(absolute)
    return index


def implementation_digest(package_root: str | Path | None = None) -> str:
    """Digest the suite's own source bytes.

    A change to a probe implementation must invalidate every cached result that
    probe produced. Hashing the source is the only way to notice that without
    trusting a version string somebody forgot to bump.
    """
    if package_root is None:
        package_root = Path(__file__).resolve().parents[2]
    root = Path(package_root)
    return digest_value({"source": _source_index(root)})


def module_digest(module_name: str) -> str:
    """Digest one module's source bytes, for a per-probe cache key."""
    from .hashing import digest_bytes

    module = sys.modules.get(module_name)
    if module is None or not getattr(module, "__file__", None):
        return digest_value({"module": module_name, "source": None})
    try:
        return digest_bytes(Path(module.__file__).read_bytes())
    except OSError:
        return digest_value({"module": module_name, "source": None})


def dependency_lock_digest(lock_path: str | Path | None = None) -> str:
    """Digest the dependency lock file.

    The runtime path of this suite has no third-party dependencies; the lock
    still enters the audit receipt so that a future dependency cannot be added
    without the receipt changing.
    """
    from .hashing import digest_bytes, digest_file

    if lock_path is None:
        candidate = Path(__file__).resolve().parents[3] / "requirements.lock"
    else:
        candidate = Path(lock_path)
    if candidate.is_file():
        return digest_file(candidate)
    return digest_bytes(b"")


def execution_path_identity(
    execution_path_id: str,
    entry_point: str,
    contract_digest: str,
    fixture_mode: bool,
) -> dict[str, Any]:
    """Identity of the code path that produced a run.

    A fixture run and a production run must never share this identity, or a
    fixture PASS could satisfy a production promotion.
    """
    record = {
        "executionPathId": execution_path_id,
        "producerEntryPoint": entry_point,
        "contractDigest": contract_digest,
        "fixtureMode": bool(fixture_mode),
    }
    record["entryPointDigest"] = digest_value(
        {
            "executionPathId": execution_path_id,
            "producerEntryPoint": entry_point,
            "fixtureMode": bool(fixture_mode),
        }
    )
    return record
