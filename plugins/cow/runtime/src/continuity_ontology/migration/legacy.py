"""Migration from the 0.1.0 ontology, CityQA and claim-bundle records.

Migration creates new semantic records. It never rewrites legacy bytes and it
never upgrades what a record established:

* a v1 ``PASS`` from a worker report migrates to a *producer-asserted* status
  with verification ``UNVERIFIED``, not to an independent v2 PASS;
* a synthetic example stays synthetic and stays inadmissible for live claims;
* a field that did not exist becomes ``UNKNOWN`` with a reason, never an
  invented default;
* a metric whose denominator changed becomes a new versioned metric id rather
  than a silent correction of the old one.

Legacy digests keep their own namespace. A migrated record cites the original
bytes and the profile that produced their digest, so an 0.1.0 identity still
verifies under ``ontology.core.v1`` after migration.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with, ontology_v1_bytes

__all__ = [
    "MigrationError",
    "MigrationBlocked",
    "migrate_status",
    "migrate_authority_label",
    "migrate_record",
    "migrate_metric_id",
    "MigrationReport",
]

#: v1 status -> (v2 producer status, verification status, note)
_STATUS_MAP: dict[str, tuple[str, str, str]] = {
    "PASS": ("PASS", "PRODUCER_ASSERTED", "a v1 worker PASS is a producer assertion in v2, not an independent verification"),
    "FAIL": ("FAIL", "PRODUCER_ASSERTED", "preserved as a contradiction reported by the producer"),
    "UNKNOWN": ("UNKNOWN", "UNVERIFIED", "preserved; missing evidence does not become a default"),
    "ERROR": ("ERROR", "UNVERIFIED", "preserved as a harness failure, not a product conclusion"),
    "NOT_RUN": ("NOT_RUN", "UNVERIFIED", "preserved as a dependency stop"),
}

#: Legacy trust states from the 0.1.0 projection vocabulary.
_TRUST_STATE_MAP: dict[str, str] = {
    "PRESENTATION_ONLY": "POLICY_OR_SYNTHETIC_AID",
    "DIRECT_EVIDENCE_PROJECTION": "DETERMINISTIC_DERIVATION",
    "INFERRED_EXPLANATION": "HEURISTIC_DECISION",
    "BLOCKED_MISSING_EVIDENCE": "CALLER_ASSERTION",
}

#: Metrics whose denominator changed between versions.
_METRIC_RENAMES: dict[str, tuple[str, str]] = {
    "rework_tax": (
        "rework_tax.vendor_tokens",
        "the v1 metric mixed unit domains; v2 publishes one metric per domain, so this is "
        "a different versioned metric rather than a correction of the old number",
    ),
    "concentration_ratio": (
        "UNMIGRATABLE",
        "the historical 227/508 ratio mixed skill uses with implementation runs; the two "
        "are separate counters in v2 and no single ratio reproduces it",
    ),
}


class MigrationError(ValueError):
    """Base class for migration failures."""


class MigrationBlocked(MigrationError):
    """Raised when migration cannot proceed without inventing information."""


def migrate_status(v1_status: str, *, producer_role: str = "legacy-worker") -> dict[str, Any]:
    """Migrate a v1 status without upgrading its authority."""
    if v1_status not in _STATUS_MAP:
        raise MigrationError(
            "unknown legacy status " + repr(v1_status) + "; an unrecognized status is not "
            "mapped to a default"
        )
    status, verification, note = _STATUS_MAP[v1_status]
    return {
        "producerStatus": status,
        "verificationStatus": verification,
        "producerRole": producer_role,
        "note": note,
        "independentlyVerified": False,
    }


def migrate_authority_label(legacy_label: str) -> str:
    """Map a legacy trust state onto an authority class without raising it."""
    if legacy_label in _TRUST_STATE_MAP:
        return _TRUST_STATE_MAP[legacy_label]
    raise MigrationError(
        "unknown legacy trust state " + repr(legacy_label)
        + "; unmapped labels are not silently promoted"
    )


def migrate_metric_id(v1_metric_id: str) -> dict[str, Any]:
    """Map a v1 metric id, flagging denominators that changed."""
    if v1_metric_id in _METRIC_RENAMES:
        new_id, reason = _METRIC_RENAMES[v1_metric_id]
        if new_id == "UNMIGRATABLE":
            return {"migrated": False, "v2MetricId": None, "reason": reason}
        return {"migrated": True, "v2MetricId": new_id, "reason": reason, "sameSeries": False}
    return {"migrated": True, "v2MetricId": v1_metric_id, "sameSeries": True}


def migrate_record(
    legacy: Mapping[str, Any],
    *,
    record_type: str,
    source_path: str,
    legacy_profile: str = "ontology.core.v1",
    synthetic: bool = False,
    absent_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Produce a v2 record that points back at the original bytes.

    The original digest is recomputed under the legacy profile and carried
    alongside the new one, so both identities remain checkable and the legacy
    namespace is untouched.
    """
    legacy_digest = digest_with(legacy_profile, legacy)
    unknowns = {
        field: {
            "value": None,
            "basis": "UNKNOWN",
            "reason": "the field does not exist in the legacy record; it is unknown, not defaulted",
        }
        for field in sorted(absent_fields)
    }

    migrated: dict[str, Any] = {
        "schemaVersion": "2.0.0",
        "recordType": record_type,
        "hashProfile": "continuity.core.v2",
        "provenance": {
            "origin": "SYNTHETIC_FIXTURE" if synthetic else "SOURCE_ARTIFACT",
            "productionMethod": "TRANSCRIBED",
            "observationChannel": "FILE_BYTES",
            "authorityClass": "POLICY_OR_SYNTHETIC_AID" if synthetic else "AUTHORITATIVE_SOURCE",
            "operationalOwnership": "NOT_APPLICABLE",
            "verificationStatus": "UNVERIFIED",
            "actor": "migration",
            "syntheticFixture": synthetic,
            "sourceRefs": [legacy_digest],
        },
        "migrationReceipt": {
            "recordType": "MigrationReceipt",
            "sourcePath": source_path,
            "legacyProfile": legacy_profile,
            "legacyDigest": legacy_digest,
            "legacyBytesPreserved": True,
            "deterministic": True,
            "unknownFields": unknowns,
            "note": (
                "The original record is unchanged and still verifies under "
                + legacy_profile + ". This is a new semantic record that cites it."
            ),
        },
        "legacyPayload": dict(legacy),
    }
    if synthetic:
        migrated["migrationReceipt"]["syntheticNote"] = (
            "This record originated as a synthetic fixture. It stays synthetic after "
            "migration and remains inadmissible for any live or measured-savings claim."
        )
    migrated["revisionId"] = digest_with("continuity.core.v2", migrated)
    return migrated


class MigrationReport:
    """Accumulates migration outcomes and blockers."""

    def __init__(self) -> None:
        self._migrated: list[dict[str, Any]] = []
        self._blocked: list[dict[str, Any]] = []

    def record(self, source_path: str, record_type: str, digest: str) -> None:
        self._migrated.append(
            {"sourcePath": source_path, "recordType": record_type, "revisionId": digest}
        )

    def block(self, source_path: str, reason: str) -> None:
        self._blocked.append({"sourcePath": source_path, "reason": reason})

    def summary(self) -> dict[str, Any]:
        return {
            "schema": "ont20.migration-report/1",
            "migratedCount": len(self._migrated),
            "blockedCount": len(self._blocked),
            "migrated": self._migrated,
            "blockers": self._blocked,
            "originalsModified": 0,
            "note": (
                "A failed migration leaves the original data intact and produces a named "
                "blocker. Nothing here rewrites legacy bytes."
            ),
        }


# ---------------------------------------------------------------------------
# R3.5 historical compatibility fixtures
# ---------------------------------------------------------------------------

#: The reported R3.5 terrain/operation closures. These are historical figures
#: bound to a particular frozen candidate; they are never copied into an
#: unrelated current dataset.
R35_FIXTURE_PROFILE: dict[str, Any] = {
    "profileId": "legacy_r35",
    "sourceOccurrences": 161,
    "uniqueTerrainControlUniverse": 131,
    "requiredSetCoverage": "FULL",
    "ownershipDerivation": "DIRECT_CURRENT_OPERATION",
    "journalReadbackRollbackSetEquality": True,
    "boundTo": "a particular historical frozen candidate",
    "replayQualification": "UNQUALIFIED_SOURCE_BYTES_NOT_ADMITTED",
    "note": (
        "The rejected R3.3 candidate is not the current executable baseline. These "
        "numbers apply only where the exact relevant source identities are admitted; "
        "generic validators and synthetic tests proceed without pretending to reproduce "
        "those bytes."
    ),
}


def check_r35_closure(observed: Mapping[str, Any]) -> dict[str, Any]:
    """Check an observation against the R3.5 historical closure requirements."""
    findings: list[dict[str, Any]] = []

    def check(check_id: str, ok: bool, detail: str) -> None:
        findings.append({"checkId": check_id, "status": "PASS" if ok else "FAIL", "detail": detail})

    check(
        "r35.universe",
        observed.get("uniqueTerrainControlUniverse") == 131,
        "unique terrain control universe is " + str(observed.get("uniqueTerrainControlUniverse"))
        + "; 130 is the known off-by-one failure mode",
    )
    check(
        "r35.occurrences",
        observed.get("sourceOccurrences") == 161,
        "source occurrences is " + str(observed.get("sourceOccurrences")),
    )
    check(
        "r35.coverage",
        observed.get("requiredSetCoverage") == "FULL",
        "required-set coverage is " + str(observed.get("requiredSetCoverage")),
    )
    check(
        "r35.ownership",
        observed.get("ownershipDerivation") == "DIRECT_CURRENT_OPERATION",
        "ownership derivation is " + str(observed.get("ownershipDerivation"))
        + "; a caller-owned transaction does not satisfy this",
    )
    check(
        "r35.setEquality",
        bool(observed.get("journalReadbackRollbackSetEquality")),
        "journal, readback and rollback sets are equal",
    )
    field_by_check = {"r35.universe": "uniqueTerrainControlUniverse",
                      "r35.occurrences": "sourceOccurrences", "r35.coverage": "requiredSetCoverage",
                      "r35.ownership": "ownershipDerivation", "r35.setEquality": "journalReadbackRollbackSetEquality"}
    for finding in findings:
        if observed.get(field_by_check[finding["checkId"]]) is None:
            finding["status"] = "UNKNOWN"
            finding["detail"] = "required observation is missing: " + field_by_check[finding["checkId"]]
    failed = [f for f in findings if f["status"] == "FAIL"]
    missing = [f for f in findings if f["status"] == "UNKNOWN"]
    return {
        "profileId": "legacy_r35",
        "status": "FAIL" if failed else "UNKNOWN" if missing else "PASS",
        "checks": findings,
        "failedChecks": [f["checkId"] for f in failed],
        "qualification": R35_FIXTURE_PROFILE["replayQualification"],
    }
