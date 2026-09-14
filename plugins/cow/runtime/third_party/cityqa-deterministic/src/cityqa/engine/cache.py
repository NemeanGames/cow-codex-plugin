"""Probe cache (IMPLEMENTATION DIRECTIVE section 12).

The cache exists to keep a model out of the loop for work already done
deterministically. It is only safe if a cached PASS cannot outlive the
conditions that produced it, so the key covers every one of them:

    probe implementation digest
    contract digest
    input artifact digests
    environment identity digest
    provider identity digest
    execution-path identity

If any element changes, the key changes and the probe re-runs. Nothing is
evicted by age, because age is not what makes a result wrong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .atomic import write_json
from .canonical import canonical_path
from .hashing import digest_file, digest_value
from .statuses import Status

__all__ = ["CacheKey", "ProbeCache", "compute_input_digests"]


class CacheKey:
    """The six-part identity of one cacheable probe execution."""

    __slots__ = (
        "probe_id", "implementation_digest", "contract_digest", "input_digests",
        "environment_digest", "provider_digest", "execution_path_digest",
    )

    def __init__(
        self,
        probe_id: str,
        implementation_digest: str,
        contract_digest: str,
        input_digests: Mapping[str, str],
        environment_digest: str,
        provider_digest: str,
        execution_path_digest: str,
    ) -> None:
        self.probe_id = probe_id
        self.implementation_digest = implementation_digest
        self.contract_digest = contract_digest
        self.input_digests = dict(sorted(input_digests.items()))
        self.environment_digest = environment_digest
        self.provider_digest = provider_digest
        self.execution_path_digest = execution_path_digest

    def as_dict(self) -> dict[str, Any]:
        return {
            "probeId": self.probe_id,
            "probeImplementationDigest": self.implementation_digest,
            "contractDigest": self.contract_digest,
            "inputArtifactDigests": self.input_digests,
            "environmentIdentityDigest": self.environment_digest,
            "providerIdentityDigest": self.provider_digest,
            "executionPathIdentity": self.execution_path_digest,
        }

    def digest(self) -> str:
        return digest_value(self.as_dict())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "CacheKey(" + self.probe_id + ", " + self.digest()[:19] + ")"


def compute_input_digests(
    root: str | Path,
    patterns: Iterable[str],
) -> dict[str, str]:
    """Digest every file matching the probe's declared input patterns.

    A pattern that matches nothing contributes an explicit ``null`` marker
    rather than being skipped: the absence of an input is itself part of the
    identity of the result, so a file appearing later must invalidate the cache.
    """
    base = Path(root)
    digests: dict[str, str] = {}
    for pattern in sorted(set(patterns)):
        matched = sorted(base.glob(pattern))
        if not matched:
            digests["!absent:" + pattern] = digest_value({"pattern": pattern, "matches": []})
            continue
        for path in matched:
            if path.is_file():
                digests[canonical_path(str(path.relative_to(base)))] = digest_file(path)
    return digests


class ProbeCache:
    """A content-addressed store of prior probe results."""

    def __init__(self, directory: str | Path, enabled: bool = True) -> None:
        self.directory = Path(directory)
        self.enabled = enabled
        self.hits = 0
        self.misses = 0
        self._invalidated: set[str] = set()
        if self.enabled:
            self.directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: CacheKey) -> Path:
        digest = key.digest().split(":", 1)[1]
        return self.directory / digest[:2] / (digest + ".json")

    def invalidate_probe(self, probe_id: str) -> None:
        """Mark a probe so its cached entries are not consulted this run."""
        self._invalidated.add(probe_id)

    def invalidate_probes(self, probe_ids: Iterable[str]) -> None:
        for probe_id in probe_ids:
            self.invalidate_probe(probe_id)

    def lookup(self, key: CacheKey) -> dict[str, Any] | None:
        """Return a cached result, or ``None``.

        A cached ERROR or NOT_RUN is never served: those describe the harness or
        the run's control flow, not the product, and replaying them would hide a
        condition that may since have cleared.
        """
        if not self.enabled or key.probe_id in self._invalidated:
            self.misses += 1
            return None
        path = self._path_for(key)
        if not path.is_file():
            self.misses += 1
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            self.misses += 1
            return None
        if entry.get("cacheKey") != key.digest():
            self.misses += 1
            return None
        result = entry.get("result")
        if not isinstance(result, dict):
            self.misses += 1
            return None
        if result.get("status") in {Status.ERROR.value, Status.NOT_RUN.value}:
            self.misses += 1
            return None
        self.hits += 1
        stored = dict(result)
        stored["cached"] = True
        stored["cacheKey"] = key.digest()
        return stored

    def store(self, key: CacheKey, result: Mapping[str, Any]) -> None:
        """Record a result under its key.

        ERROR and NOT_RUN are not stored, for the same reason they are not
        served.
        """
        if not self.enabled:
            return
        if result.get("status") in {Status.ERROR.value, Status.NOT_RUN.value}:
            return
        payload = dict(result)
        payload["cached"] = False
        write_json(
            self._path_for(key),
            {
                "schemaVersion": "1.0.0",
                "cacheKey": key.digest(),
                "keyComponents": key.as_dict(),
                "result": payload,
            },
        )

    def statistics(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "enabled": self.enabled,
            "hits": self.hits,
            "misses": self.misses,
            "lookups": total,
            "invalidatedProbes": sorted(self._invalidated),
        }
