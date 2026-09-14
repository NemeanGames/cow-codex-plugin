"""Hash-profile registry.

There is deliberately no universal serializer. Each digest domain has its own
byte rules, and mixing them changes identities that other systems already
depend on. In particular:

* ``cityqa.core.v1`` appends one terminal newline and collapses ``1.0`` to
  ``1``. ``ontology.core.v1`` does neither and emits a bare hex digest.
* ``sfd.checksum.world.v1`` is a *production* identity belonging to the
  Pershing SFD tooling. It uses plain ``json.dumps`` float repr, rounds
  translation to 4 places and quaternions to 6, and leaves scale unrounded.
  Substituting either canonical serializer here would silently change every
  checksum that tooling has ever produced.

Profiles declare their own self-field exclusions, collection ordering,
Unicode and numeric handling, time inclusion, signed-zero rule, nonfinite
policy and digest domain. ``describe()`` returns that declaration so a
receipt can record which rules produced a digest.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping, Sequence

from cityqa.engine.canonical import canonical_bytes as _cityqa_canonical_bytes

__all__ = [
    "HashProfileError",
    "HashProfile",
    "REGISTRY",
    "get_profile",
    "profile_names",
    "digest_with",
    "describe_all",
    "ontology_v1_bytes",
    "core_v2_bytes",
    "sfd_world_checksum_v1",
    "local_fingerprint_v2",
]


class HashProfileError(ValueError):
    """Raised when a value cannot be digested under the named profile."""


class HashProfile:
    """One digest domain and the exact byte rules that define it."""

    __slots__ = ("name", "version", "domain", "encoder", "digest_form", "rules", "doc")

    def __init__(
        self,
        name: str,
        version: str,
        domain: str,
        encoder: Callable[[Any], bytes],
        digest_form: str,
        rules: Mapping[str, Any],
        doc: str,
    ) -> None:
        self.name = name
        self.version = version
        self.domain = domain
        self.encoder = encoder
        self.digest_form = digest_form
        self.rules = dict(rules)
        self.doc = doc

    def encode(self, value: Any) -> bytes:
        return self.encoder(value)

    def digest(self, value: Any) -> str:
        raw = hashlib.sha256(self.encode(value)).hexdigest()
        if self.digest_form == "prefixed":
            return "sha256:" + raw
        if self.digest_form == "bare":
            return raw
        if self.digest_form == "bare_upper":
            return raw.upper()
        raise HashProfileError("unknown digest form: " + self.digest_form)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "digestDomain": self.domain,
            "domainSeparated": False,
            "domainSeparationCondition": (
                "continuity.core.v2 and cityqa.core.v1 encode identically when the value has no "
                "top-level revisionId, contentDigest, resolvedStateDigest or payloadDigest "
                "(in particular a value with no self-fields and no time); domain labels are not byte prefixes"
            ),
            "digestForm": self.digest_form,
            "rules": dict(self.rules),
            "doc": self.doc,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "HashProfile(" + self.name + ")"


# --------------------------------------------------------------------------
# ontology.core.v1 -- preserved byte-for-byte from continuity-ontology 0.1.0
# --------------------------------------------------------------------------

def ontology_v1_bytes(value: Any) -> bytes:
    """Exactly ``continuity_ontology.canonical.canonical_json_bytes`` of 0.1.0.

    No terminal newline, ``ensure_ascii=False``, compact separators. Changing
    any of these invalidates every 0.1.0 checkpoint and view identity.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


# --------------------------------------------------------------------------
# continuity.core.v2 -- the new core record profile
# --------------------------------------------------------------------------

_SELF_FIELDS = ("revisionId", "contentDigest", "resolvedStateDigest", "payloadDigest")


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise HashProfileError("non-finite float is not digestible")


def core_v2_bytes(value: Any, exclude_self_fields: Sequence[str] = _SELF_FIELDS) -> bytes:
    """Canonical bytes for a v2 core record.

    Delegates to the CityQA canonicalizer so the two systems agree on Unicode
    normalization, key ordering, escape rules and numeric text, then removes
    the record's own digest fields at the top level. A record never contains
    the digest of itself.
    """
    if isinstance(value, Mapping):
        stripped = {k: v for k, v in value.items() if k not in set(exclude_self_fields)}
    else:
        stripped = value
    _walk_reject(stripped)
    return _cityqa_canonical_bytes(stripped)


def _walk_reject(value: Any, depth: int = 0) -> None:
    if depth > 128:
        raise HashProfileError("value nesting exceeds digest depth limit")
    _reject_nonfinite(value)
    if isinstance(value, Mapping):
        for sub in value.values():
            _walk_reject(sub, depth + 1)
    elif isinstance(value, (list, tuple)):
        for sub in value:
            _walk_reject(sub, depth + 1)


# --------------------------------------------------------------------------
# sfd.checksum.world.v1 -- production identity, reported from source
# --------------------------------------------------------------------------

def _sfd_row(
    mesh_path: str,
    translation: Sequence[float],
    quaternion: Sequence[float],
    scale: Sequence[float],
) -> list[Any]:
    """Build one world-space row: [mesh, tx,ty,tz, qx,qy,qz,qw, sx,sy,sz].

    Translation rounds to 4 places and the quaternion to 6, matching the
    reported source. Scale is passed through unrounded: rounding it here would
    change checksums that already exist in saved maps.
    """
    if len(translation) != 3 or len(quaternion) != 4 or len(scale) != 3:
        raise HashProfileError("sfd row requires 3 translation, 4 quaternion, 3 scale values")
    row: list[Any] = [mesh_path]
    row.extend(round(float(v), 4) for v in translation)
    row.extend(round(float(v), 6) for v in quaternion)
    row.extend(float(v) for v in scale)
    return row


def sfd_world_checksum_v1(rows: Iterable[Sequence[Any]]) -> str:
    """Reproduce the reported v1 SFD world checksum.

    ``sha256(json.dumps(sorted(rows), sort_keys=True, separators=(',',':'),
    allow_nan=False).encode()).hexdigest()``

    Rows arrive already shaped by :func:`sfd_row`. Sorting is Python's
    lexicographic list ordering, which compares the mesh path first and then
    the numeric columns -- the same ordering the source applies.

    QUALIFICATION: these semantics are transcribed from a source review report,
    not from admitted source bytes. ``profiles.sfd_source_admitted()`` reports
    False until the exact SFD source files are admitted, and the compatibility
    claim stays UNKNOWN until then. The golden vectors in
    ``tests/golden/sfd_checksum_v1.json`` pin this implementation's behaviour so
    a later admission can confirm or contradict it.
    """
    materialized = [list(row) for row in rows]
    payload = json.dumps(
        sorted(materialized), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def sfd_row(
    mesh_path: str,
    translation: Sequence[float],
    quaternion: Sequence[float],
    scale: Sequence[float],
) -> list[Any]:
    """Public row builder for the v1 profile."""
    return _sfd_row(mesh_path, translation, quaternion, scale)


def sfd_source_admitted() -> bool:
    """True only when the exact SFD source bytes have been admitted.

    Nothing in this package sets it to True implicitly. Admission is recorded
    in ``source_snapshots/INTAKE_REPORT.json`` and asserted by the migration
    tooling, not inferred from a filename.
    """
    return False


# --------------------------------------------------------------------------
# sfd.fingerprint.local.v2 -- DIAGNOSTIC ONLY
# --------------------------------------------------------------------------

def local_fingerprint_v2(
    rows: Iterable[Sequence[Any]],
    scale_quantum: int = 3,
) -> str:
    """Local-frame diagnostic fingerprint.

    Non-authoritative by construction. A v2 match never overrides a v1
    mismatch, and no acceptance contract may cite this profile as its
    production identity. Scale is quantized here precisely because this
    profile is *not* the production one.
    """
    materialized: list[list[Any]] = []
    for row in rows:
        row = list(row)
        if len(row) != 11:
            raise HashProfileError("local fingerprint requires 11-column rows")
        mesh = row[0]
        nums = [float(v) for v in row[1:]]
        quantized = [round(v, 4) for v in nums[0:3]]
        quantized += [round(v, 6) for v in nums[3:7]]
        quantized += [round(v, scale_quantum) for v in nums[7:10]]
        materialized.append([mesh] + quantized)
    payload = json.dumps(
        sorted(materialized), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------
# raw file and dataset semantic identity
# --------------------------------------------------------------------------

def _raw_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    raise HashProfileError("raw.file.sha256 digests bytes, got " + type(value).__name__)


def _dataset_semantic_bytes(value: Any) -> bytes:
    """Semantic identity of a dataset: order-independent over member ids.

    Distinct from the dataset file's byte hash. The two are recorded
    separately because the verifier's runtime dependency and the disk import
    input play different roles.
    """
    if not isinstance(value, Mapping):
        raise HashProfileError("dataset semantic identity requires a mapping")
    members = value.get("members")
    if not isinstance(members, (list, tuple)):
        raise HashProfileError("dataset semantic identity requires a 'members' list")
    normalized = {
        "datasetId": str(value.get("datasetId", "")),
        "schema": str(value.get("schema", "")),
        "members": sorted(str(m) for m in members),
    }
    return _cityqa_canonical_bytes(normalized)


REGISTRY: dict[str, HashProfile] = {
    "ontology.core.v1": HashProfile(
        name="ontology.core.v1",
        version="1.0.0",
        domain="legacy-ontology-record",
        encoder=ontology_v1_bytes,
        digest_form="bare",
        rules={
            "terminalNewline": False,
            "keyOrder": "sorted",
            "separators": [",", ":"],
            "ensureAscii": False,
            "unicodeNormalization": "none",
            "numericText": "python-json-default",
            "signedZero": "preserved-as-json-emits",
            "nonfinite": "python-json-default-permits",
            "timeIncluded": True,
            "selfFieldExclusions": [],
        },
        doc="Preserved byte-for-byte from continuity-ontology 0.1.0. Never re-emit a 0.1.0 record under another profile and keep its old digest.",
    ),
    "cityqa.core.v1": HashProfile(
        name="cityqa.core.v1",
        version="1.0.0",
        domain="cityqa-receipt",
        encoder=_cityqa_canonical_bytes,
        digest_form="prefixed",
        rules={
            "terminalNewline": True,
            "keyOrder": "sorted-NFC",
            "separators": [",", ":"],
            "unicodeNormalization": "NFC",
            "numericText": "integer-collapsing float text, exact Decimal text",
            "signedZero": "negative zero normalizes to 0",
            "nonfinite": "rejected",
            "orderedCollections": "lists preserve order; sets rejected",
            "timeIncluded": "policy-declared exclusions only",
            "selfFieldExclusions": [],
        },
        doc="The CityQA suite's own canonical bytes, reused unchanged so a digest computed here matches one computed there.",
    ),
    "continuity.core.v2": HashProfile(
        name="continuity.core.v2",
        version="2.0.0",
        domain="ontology-2-record",
        encoder=core_v2_bytes,
        digest_form="prefixed",
        rules={
            "terminalNewline": True,
            "keyOrder": "sorted-NFC",
            "unicodeNormalization": "NFC",
            "numericText": "exact Decimal text; floats via CityQA float text",
            "signedZero": "negative zero normalizes to 0",
            "nonfinite": "rejected",
            "orderedCollections": "lists preserve order; sets rejected",
            "timeIncluded": False,
            "selfFieldExclusions": list(_SELF_FIELDS),
        },
        doc="New v2 core record profile. Shares CityQA byte rules deliberately and declares that as a common-mode dependency.",
    ),
    "raw.file.sha256": HashProfile(
        name="raw.file.sha256",
        version="1.0.0",
        domain="raw-bytes",
        encoder=_raw_bytes,
        digest_form="prefixed",
        rules={"transformation": "none", "note": "identity of the bytes on disk"},
        doc="Raw file identity. Never conflated with a semantic identity.",
    ),
    "dataset.semantic.v1": HashProfile(
        name="dataset.semantic.v1",
        version="1.0.0",
        domain="dataset-semantic",
        encoder=_dataset_semantic_bytes,
        digest_form="prefixed",
        rules={
            "memberOrder": "sorted (order-independent)",
            "note": "distinct from the dataset file's raw byte hash; both are recorded",
        },
        doc="Semantic dataset identity, recorded alongside and never instead of the import file's byte hash.",
    ),
    "sfd.checksum.world.v1": HashProfile(
        name="sfd.checksum.world.v1",
        version="1.0.0",
        domain="sfd-production-checksum",
        encoder=lambda rows: json.dumps(
            sorted([list(r) for r in rows]),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode(),
        digest_form="bare",
        rules={
            "coordinateSpace": "WORLD",
            "rowShape": ["mesh_path", "tx", "ty", "tz", "qx", "qy", "qz", "qw", "sx", "sy", "sz"],
            "ordering": "python sorted() lexicographic over row lists",
            "translationRounding": 4,
            "quaternionRounding": 6,
            "scaleRounding": None,
            "terminalNewline": False,
            "unicodeNormalization": "none",
            "numericText": "python json.dumps float repr",
            "nonfinite": "rejected (allow_nan=False)",
            "digestPrefix": "none (bare hexdigest)",
            "sourceAdmitted": False,
        },
        doc="Production SFD identity transcribed from a source review report. Compatibility remains UNKNOWN until the exact source bytes are admitted.",
    ),
    "sfd.fingerprint.local.v2": HashProfile(
        name="sfd.fingerprint.local.v2",
        version="2.0.0",
        domain="sfd-diagnostic-fingerprint",
        encoder=lambda rows: json.dumps(
            sorted([list(r) for r in rows]),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode(),
        digest_form="prefixed",
        rules={
            "coordinateSpace": "ACTOR_LOCAL_FITTED",
            "scaleQuantum": 3,
            "authoritative": False,
            "note": "diagnostic only; a v2 match never overrides a v1 mismatch",
        },
        doc="Diagnostic-only local-frame fingerprint. Not admissible as a production acceptance identity.",
    ),
}


def get_profile(name: str) -> HashProfile:
    try:
        return REGISTRY[name]
    except KeyError as exc:
        raise HashProfileError(
            "unknown hash profile " + repr(name) + "; known: " + ", ".join(sorted(REGISTRY))
        ) from exc


def profile_names() -> tuple[str, ...]:
    return tuple(sorted(REGISTRY))


def digest_with(profile_name: str, value: Any) -> str:
    return get_profile(profile_name).digest(value)


def describe_all() -> list[dict[str, Any]]:
    return [REGISTRY[name].describe() for name in sorted(REGISTRY)]


def decimal_str(value: Decimal | int | str) -> str:
    """Exact decimal text used wherever a decimal enters a v2 record."""
    return format(Decimal(str(value)), "f")
