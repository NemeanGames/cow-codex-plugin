"""Producer-side Claim consistency, independent of evidence-pass availability.

This is not independent acceptance. Missing required bodies remain UNKNOWN;
contradictions remain FAIL even when another component cannot be evaluated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ..canonical.profiles import digest_with
from ..claims.cas import CasError, ContentStore
from ..validate.records import validate_persisted
from ..validate.validator import validate_record
from .evidence_integrity import evidence_id, snapshot_references, verify_record_seal


def combined_status(*statuses: str) -> str:
    for state in ("FAIL", "ERROR", "UNKNOWN"):
        if state in statuses:
            return state
    return "PASS" if "PASS" in statuses else "NOT_RUN"


def check_claim_integrity(checkpoint: Mapping[str, Any], records_root: Path,
                          cas: ContentStore | None, *,
                          proposed: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Check pinned identities and bodies from disk or a proposed commit set.

    Proposed keys are relative to records_root; the bundle's public index is
    ../frozen/bundle.json. No required body may be silently ignored.
    """
    findings: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    expected: dict[str, Any] = {}
    observed: dict[str, Any] = {}

    def finding(status: str, code: str, detail: Any) -> None:
        findings.append({"status": status, "code": code, "detail": str(detail)})

    def read(name: str) -> Any:
        try:
            body = proposed[name] if proposed is not None and name in proposed else json.loads(
                (records_root / name).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
            if not isinstance(body, dict):
                raise ValueError("record must be an object")
            return body
        except FileNotFoundError:
            finding("UNKNOWN", "missing_body", name)
        except (ValueError, UnicodeError) as exc:
            finding("FAIL", "malformed_body", name + ": " + str(exc))
        except OSError as exc:
            finding("ERROR", "body_io", name + ": " + str(exc))
        except Exception as exc:
            finding("ERROR", "body_evaluation", name + ": " + str(exc))
        return None

    def pin(name: str) -> list[Any]:
        facts = [f for f in snapshot.get("requiredFacts", []) if f.get("factId") == name]
        if len(facts) > 1:
            finding("FAIL", "duplicate_binding", name)
        values = [f.get("value") for f in facts]
        for f in facts:
            if not f.get("present") or not valid_digest(f.get("value")):
                finding("FAIL", "invalid_binding", name)
        expected[name] = values
        return values

    def claim_body(body: dict[str, Any], standalone: bool) -> None:
        if standalone:
            validation = validate_record("Claim", body)
            if not validation.ok:
                raise ValueError("invalid Claim envelope/body: " + repr(validation.issues))
        validate_persisted(dict(body, recordType="Claim"))
        cid = body.get("claimId")
        if body.get("recordType") != "Claim" or not isinstance(cid, str) or not cid:
            raise ValueError("invalid Claim type or claimId")
        if standalone and (body.get("logicalId") != cid or body.get("hashProfile") != "continuity.core.v2"):
            raise ValueError("Claim logical identity/profile mismatch")
        proposition, assertion = body["proposition"], body["producerAssertion"]
        if not isinstance(proposition, dict) or not isinstance(proposition.get("scope"), dict) or not proposition.get("claimType"):
            raise ValueError("invalid proposition")
        if not isinstance(assertion, dict) or assertion.get("producerStatus") not in {"PASS", "FAIL", "UNKNOWN", "ERROR", "NOT_RUN"}:
            raise ValueError("invalid producer assertion")
        requirements = body["requiredEvidence"]
        if not isinstance(requirements, list) or any(not isinstance(r, dict) or not isinstance(r.get("requirementId"), str) or not r.get("requirementId") or not r.get("evidenceKind") for r in requirements):
            raise ValueError("invalid requiredEvidence")
        ids = [r["requirementId"] for r in requirements]
        if len(ids) != len(set(ids)):
            finding("FAIL", "duplicate_requirement", cid)
        refs = assertion.get("evidenceRefs", [])
        if not isinstance(refs, list) or any(not valid_digest(ref) for ref in refs):
            raise ValueError("invalid evidenceRefs")
        if standalone:
            bindings = {evidence_id(path): digest for _, path, digest in snapshot_references(snapshot)}
            required_ids = ["ev." + rid[2:] for rid in ids if rid.startswith("r.")]
            if len(required_ids) != len(ids) or set(required_ids) != set(bindings):
                finding("FAIL", "claim_evidence_ids", cid)
            if len(refs) != len(required_ids) or any(ref != bindings.get(eid) for eid, ref in zip(required_ids, refs)):
                finding("FAIL", "claim_evidence_associations", cid)
        for ref in refs:
            if cas is None:
                finding("NOT_RUN", "claim_cas_unavailable", ref)
                continue
            try:
                cas.get_bytes(ref)
            except CasError as exc:
                finding("FAIL", "claim_evidence_bytes", exc)
            except OSError as exc:
                finding("ERROR", "claim_evidence_io", exc)
        if not isinstance(body.get("sufficiency"), dict) or body.get("lifecycle") not in {"DRAFT", "SEALED"}:
            raise ValueError("invalid Claim structure")

    snapshot = checkpoint.get("snapshot") or {}
    claims = pin("claimDigest")
    bundles = pin("bundleDigest")
    citations = []
    for decision in checkpoint.get("acceptedDecisions", []):
        if decision.get("decisionKind") == "producer_self_check":
            values = decision.get("citedInputs")
            if not isinstance(values, list) or not values or any(not valid_digest(v) for v in values):
                finding("FAIL", "invalid_citation", values)
            else:
                citations.extend(values)
    if len(citations) != len(set(citations)):
        finding("FAIL", "duplicate_citation", citations)
    required = bool(claims or bundles or citations or findings)
    expected["citedInputs"] = citations
    if claims or citations:
        body = read("claim.json")
        if body is not None:
            observed["claimDigest"] = body.get("revisionId")
            checked.append({"claimId": body.get("claimId"), "path": "claim.json"})
            try:
                claim_body(body, True)
                if not verify_record_seal(body):
                    finding("FAIL", "claim_revision_seal", body.get("revisionId"))
                for value in claims + citations:
                    if value != body.get("revisionId"):
                        finding("FAIL", "claim_pin_mismatch", value)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                finding("FAIL", "invalid_claim", exc)
            except Exception as exc:
                finding("ERROR", "claim_evaluation", exc)
    if bundles:
        candidates = pin("candidateDigest")
        if len(candidates) != 1:
            finding("FAIL", "candidate_binding", candidates)
        bundle = read("../frozen/bundle.json")
        if bundle is not None:
            try:
                if bundle.get("recordType") != "ClaimBundle" or bundle.get("lifecycle") != "SEALED" or not bundle.get("bundleId"):
                    raise ValueError("invalid bundle type/identity/lifecycle")
                members = bundle["memberIndex"]
                if not isinstance(members, list) or not members:
                    raise ValueError("missing bundle members")
                ids = [m["claimId"] for m in members]
                if len(ids) != len(set(ids)):
                    finding("FAIL", "duplicate_member", ids)
                resolved = digest_with("continuity.core.v2", {"members": members, "candidateDigest": bundle["candidateDigest"]})
                observed["bundleDigest"] = resolved
                observed["candidateDigest"] = bundle["candidateDigest"]
                if any(value != resolved for value in bundles) or resolved != bundle.get("resolvedStateDigest"):
                    finding("FAIL", "bundle_pin_mismatch", resolved)
                if any(value != bundle["candidateDigest"] for value in candidates):
                    finding("FAIL", "candidate_pin_mismatch", bundle["candidateDigest"])
                for member in members:
                    ref = member["revisionDigest"]
                    if not valid_digest(ref):
                        finding("FAIL", "invalid_member_digest", ref)
                        continue
                    name = "claim-revisions/" + ref[7:] + ".json"
                    revision = read(name)
                    if revision is None:
                        continue
                    checked.append({"claimId": member["claimId"], "path": name, "expectedIdentity": ref})
                    try:
                        validate_persisted(revision)
                        actual = digest_with("continuity.core.v2", revision)
                        checked[-1]["observedIdentity"] = actual
                        if "_digest" in revision or revision.get("recordType") != "ClaimRevision" or actual != ref:
                            raise ValueError("ClaimRevision type/digest mismatch")
                        body = revision["claim"]
                        if revision.get("claimId") != member["claimId"] or body.get("claimId") != member["claimId"] or body.get("lifecycle") != "SEALED" or body.get("mandatory") != member.get("mandatory"):
                            raise ValueError("member identity/lifecycle/mandatory mismatch")
                        if type(revision.get("revisionNumber")) is not int or revision["revisionNumber"] < 1 or not revision.get("changeReason"):
                            raise ValueError("invalid revision structure")
                        claim_body(body, False)
                    except (KeyError, TypeError, ValueError, AttributeError) as exc:
                        finding("FAIL", "invalid_revision", exc)
                    except Exception as exc:
                        finding("ERROR", "revision_evaluation", exc)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                finding("FAIL", "invalid_bundle", exc)
            except Exception as exc:
                finding("ERROR", "bundle_evaluation", exc)
    status = combined_status(*(f["status"] for f in findings)) if findings else ("PASS" if required else "NOT_RUN")
    return {"required": required, "status": status, "checkedClaims": checked,
            "expectedIdentities": expected, "observedIdentities": observed,
            "findings": findings, "blockers": ["claim integrity " + f["status"] + ": " + f["code"] + ": " + f["detail"] for f in findings]}


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result
