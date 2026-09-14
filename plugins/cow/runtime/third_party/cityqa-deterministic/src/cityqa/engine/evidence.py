"""Evidence model (IMPLEMENTATION DIRECTIVE section 10).

Every machine claim requires an evidence record. Evidence *type* describes what
the artifact is; authority *class* describes what it is entitled to establish.
The two are separate, and keeping them separate is what stops a screenshot from
standing in for a measurement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .hashing import digest_file, digest_value, is_digest
from .statuses import AuthorityClass, SCHEMA_VERSION

__all__ = [
    "EvidenceError",
    "EvidenceRecord",
    "EvidenceLedger",
    "AuthorityMatrix",
    "AuthorityFinding",
]


class EvidenceError(ValueError):
    """Raised when an evidence record is malformed or unbacked."""


class EvidenceRecord:
    """One artifact offered in support of one or more claims."""

    __slots__ = (
        "evidence_id", "evidence_type", "authority_class", "producer",
        "artifact_path", "artifact_digest", "captured_at", "claim_ids",
        "run_id", "detail",
    )

    def __init__(
        self,
        evidence_id: str,
        evidence_type: str,
        authority_class: str,
        producer: str,
        artifact_path: str,
        artifact_digest: str,
        captured_at: str,
        claim_ids: Sequence[str] = (),
        run_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        if not evidence_id.startswith("EVIDENCE-"):
            raise EvidenceError("evidence id must begin with EVIDENCE-: " + evidence_id)
        if not is_digest(artifact_digest):
            raise EvidenceError(
                "evidence " + evidence_id + " has no well-formed artifact digest"
            )
        AuthorityClass(authority_class)
        self.evidence_id = evidence_id
        self.evidence_type = evidence_type
        self.authority_class = authority_class
        self.producer = producer
        self.artifact_path = artifact_path
        self.artifact_digest = artifact_digest
        self.captured_at = captured_at
        self.claim_ids = list(claim_ids)
        self.run_id = run_id
        self.detail = dict(detail or {})

    def as_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "evidenceId": self.evidence_id,
            "evidenceType": self.evidence_type,
            "authorityClass": self.authority_class,
            "producer": self.producer,
            "artifactPath": self.artifact_path,
            "artifactDigest": self.artifact_digest,
            "capturedAt": self.captured_at,
            "claimIds": sorted(self.claim_ids),
        }
        if self.run_id is not None:
            record["runId"] = self.run_id
        if self.detail:
            record["detail"] = self.detail
        return record

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "EvidenceRecord(" + self.evidence_id + ", " + self.authority_class + ")"


class EvidenceLedger:
    """The run's evidence records, keyed by evidence id."""

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}

    def add(self, record: EvidenceRecord) -> EvidenceRecord:
        existing = self._records.get(record.evidence_id)
        if existing is not None:
            if existing.artifact_digest != record.artifact_digest:
                raise EvidenceError(
                    "evidence id " + record.evidence_id + " was reused for a different "
                    "artifact digest"
                )
            for claim_id in record.claim_ids:
                if claim_id not in existing.claim_ids:
                    existing.claim_ids.append(claim_id)
            return existing
        self._records[record.evidence_id] = record
        return record

    def record_file(
        self,
        evidence_id: str,
        evidence_type: str,
        authority_class: str,
        producer: str,
        path: str | Path,
        captured_at: str,
        claim_ids: Sequence[str] = (),
        run_id: str | None = None,
        logical_path: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Digest a file and register it as evidence."""
        from .canonical import canonical_path

        target = Path(path)
        return self.add(
            EvidenceRecord(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                authority_class=authority_class,
                producer=producer,
                artifact_path=logical_path or canonical_path(str(target)),
                artifact_digest=digest_file(target),
                captured_at=captured_at,
                claim_ids=claim_ids,
                run_id=run_id,
                detail=detail,
            )
        )

    def record_value(
        self,
        evidence_id: str,
        evidence_type: str,
        authority_class: str,
        producer: str,
        logical_path: str,
        value: Any,
        captured_at: str,
        claim_ids: Sequence[str] = (),
        run_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Register an in-memory measurement as evidence, bound by its digest."""
        return self.add(
            EvidenceRecord(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                authority_class=authority_class,
                producer=producer,
                artifact_path=logical_path,
                artifact_digest=digest_value(value),
                captured_at=captured_at,
                claim_ids=claim_ids,
                run_id=run_id,
                detail=detail,
            )
        )

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def has(self, evidence_id: str) -> bool:
        return evidence_id in self._records

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def types_for(self, evidence_ids: Iterable[str]) -> set[str]:
        return {
            self._records[eid].evidence_type
            for eid in evidence_ids
            if eid in self._records
        }

    def authority_classes_for(self, evidence_ids: Iterable[str]) -> set[str]:
        return {
            self._records[eid].authority_class
            for eid in evidence_ids
            if eid in self._records
        }

    def unresolved(self, evidence_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted(eid for eid in evidence_ids if eid not in self._records))

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records[eid] for eid in sorted(self._records))

    def as_list(self) -> list[dict[str, Any]]:
        return [record.as_dict() for record in self.records()]

    def digest(self) -> str:
        return digest_value({"evidence": self.as_list()})

    def __len__(self) -> int:
        return len(self._records)


class AuthorityFinding:
    """The outcome of checking offered evidence against the authority matrix."""

    __slots__ = ("satisfied", "failure_code", "reason", "missing_types",
                 "offered_classes", "permitted_classes")

    def __init__(
        self,
        satisfied: bool,
        failure_code: str | None = None,
        reason: str = "",
        missing_types: Sequence[str] = (),
        offered_classes: Sequence[str] = (),
        permitted_classes: Sequence[str] = (),
    ) -> None:
        self.satisfied = satisfied
        self.failure_code = failure_code
        self.reason = reason
        self.missing_types = tuple(missing_types)
        self.offered_classes = tuple(offered_classes)
        self.permitted_classes = tuple(permitted_classes)

    def __bool__(self) -> bool:
        return self.satisfied

    def as_dict(self) -> dict[str, Any]:
        return {
            "satisfied": self.satisfied,
            "failureCode": self.failure_code,
            "reason": self.reason,
            "missingEvidenceTypes": list(self.missing_types),
            "offeredAuthorityClasses": list(self.offered_classes),
            "permittedAuthorityClasses": list(self.permitted_classes),
        }


class AuthorityMatrix:
    """Which authority classes may establish which claim types.

    Loaded from ``evidence_authority.v1.json``. The matrix holds the operational
    rule; this class only executes it.
    """

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._document = document
        self._rules = {rule["claimType"]: rule for rule in document.get("rules", [])}
        self._prohibited: list[Mapping[str, Any]] = list(document.get("prohibited", []))
        self._class_types: Mapping[str, Sequence[str]] = document.get(
            "authorityClassEvidenceTypes", {}
        )

    def permitted_classes(self, claim_type: str) -> tuple[str, ...]:
        rule = self._rules.get(claim_type)
        if rule is None:
            return ()
        return tuple(rule.get("permittedAuthorityClasses", ()))

    def required_types(self, claim_type: str) -> tuple[str, ...]:
        rule = self._rules.get(claim_type)
        if rule is None:
            return ()
        return tuple(rule.get("requiredEvidenceTypes", ()))

    def minimum_mode(self, claim_type: str) -> str | None:
        rule = self._rules.get(claim_type)
        if rule is None:
            return None
        return rule.get("minimumVerificationMode")

    def evidence_types_for_class(self, authority_class: str) -> tuple[str, ...]:
        return tuple(self._class_types.get(authority_class, ()))

    def check(
        self,
        claim_type: str,
        offered_classes: Iterable[str],
        offered_types: Iterable[str],
        required_types: Iterable[str] = (),
    ) -> AuthorityFinding:
        """Check offered evidence against the matrix for one claim type."""
        classes = sorted(set(offered_classes))
        types = set(offered_types)
        permitted = self.permitted_classes(claim_type)

        if not permitted:
            return AuthorityFinding(
                False,
                "EVIDENCE_AUTHORITY_INSUFFICIENT",
                "the authority matrix declares no rule for claim type " + claim_type,
                offered_classes=classes,
            )

        # An explicit prohibition is checked first: it is the rule that stops an
        # image digest from standing in for a measurement.
        for prohibition in self._prohibited:
            if claim_type not in prohibition.get("claimTypes", []):
                continue
            forbidden = prohibition["authorityClass"]
            if forbidden in classes and not (set(classes) - {forbidden}):
                return AuthorityFinding(
                    False,
                    prohibition["failureCode"],
                    prohibition["reason"],
                    offered_classes=classes,
                    permitted_classes=permitted,
                )

        if not set(classes) & set(permitted):
            return AuthorityFinding(
                False,
                "EVIDENCE_AUTHORITY_INSUFFICIENT",
                "claim type " + claim_type + " admits authority "
                + ", ".join(permitted) + "; the offered evidence carries "
                + (", ".join(classes) if classes else "none"),
                offered_classes=classes,
                permitted_classes=permitted,
            )

        needed = set(self.required_types(claim_type)) | set(required_types)
        missing = sorted(needed - types)
        if missing:
            return AuthorityFinding(
                False,
                "EVIDENCE_AUTHORITY_INSUFFICIENT",
                "required evidence type(s) absent: " + ", ".join(missing),
                missing_types=missing,
                offered_classes=classes,
                permitted_classes=permitted,
            )

        return AuthorityFinding(
            True,
            None,
            "offered authority satisfies claim type " + claim_type,
            offered_classes=classes,
            permitted_classes=permitted,
        )
