"""Environment identity binding and claim-specific cache freshness.

Identity first. A listening port tells you something is listening, not what it
is. A PID can be reused within seconds of a process exiting. An editor
launcher stub's file hash pins the stub, not the engine build behind it. So
:func:`bind_environment_identity` requires process *creation* identity, project
and map, native module and build identity, and adapter endpoint configuration,
and it names every dimension it could not observe rather than defaulting it.

Freshness second. The CityQA cache is reused unchanged; what this module adds
is that reuse is decided per *claim*, not per filename. A pure comparison of
identical frozen bytes may be reused with a receipt. A process, map,
visibility, slot or dirty-state observation, and any prescribed cold-reopen
check, must be fresh. A timeout is never converted into a cache hit.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from cityqa.engine.cache import CacheKey, ProbeCache

from continuity_ontology.canonical.profiles import digest_with

__all__ = [
    "IdentityError",
    "InsufficientIdentity",
    "ALWAYS_FRESH_DOMAINS",
    "bind_environment_identity",
    "identity_sufficiency",
    "freshness_decision",
    "build_cache_key",
]


class IdentityError(ValueError):
    """Raised when an environment binding cannot be built as described."""


class InsufficientIdentity(IdentityError):
    """Raised when only weak identity signals are offered."""


#: Observation domains that are never served from cache.
ALWAYS_FRESH_DOMAINS: frozenset[str] = frozenset(
    {
        "process",
        "map",
        "visibility",
        "slot",
        "dirty_state",
        "cold_reopen",
        "generation_key",
        "authorization",
        "provider_session",
    }
)

#: Signals that cannot, alone, establish which environment is running.
_WEAK_SIGNALS = {
    "listeningPort": "a listening port is not editor identity",
    "pid": "a PID can be reused after the original process exits",
    "launcherStubDigest": "an executable stub hash does not pin the engine build",
}

_REQUIRED_DIMENSIONS = (
    "processCreation",
    "projectIdentity",
    "mapIdentity",
    "moduleClosureDigest",
    "adapterEndpointConfigDigest",
)


def bind_environment_identity(
    observations: Mapping[str, Any],
    *,
    host_id: str,
    interpreter: str,
    interpreter_version: str,
    platform: str,
) -> dict[str, Any]:
    """Build an EnvironmentIdentity, naming what could not be observed."""
    unknown: list[str] = []
    record: dict[str, Any] = {
        "recordType": "EnvironmentIdentity",
        "hostId": host_id,
        "interpreter": interpreter,
        "interpreterVersion": interpreter_version,
        "platform": platform,
    }

    process = observations.get("processCreation")
    if process:
        if not process.get("createTime"):
            unknown.append("processCreation.createTime")
        if not process.get("executableDigest"):
            unknown.append("processCreation.executableDigest")
        if not process.get("commandLineDigest"):
            unknown.append("processCreation.commandLineDigest")
        record["processCreation"] = dict(process)
    else:
        unknown.append("processCreation")

    for field in ("providerBuild", "moduleClosureDigest", "adapterEndpointConfigDigest"):
        value = observations.get(field)
        if value:
            record[field] = value
        else:
            unknown.append(field)

    for field in ("projectIdentity", "mapIdentity"):
        if not observations.get(field):
            unknown.append(field)
        else:
            record[field] = observations[field]

    record["unknownFields"] = sorted(unknown)
    return record


def identity_sufficiency(identity: Mapping[str, Any], offered: Mapping[str, Any]) -> dict[str, Any]:
    """Decide whether an environment is pinned well enough to bind a claim."""
    weak_only = [
        _WEAK_SIGNALS[k] for k in _WEAK_SIGNALS if offered.get(k) and k in offered
    ]
    expected = offered.get("expectedBindings", {})
    contradictions = [field for field, value in expected.items()
                      if identity.get(field) is not None and identity[field] != value]
    if contradictions:
        return {"status": "FAIL", "sufficient": False, "missingDimensions": [],
                "reason": "identity contradicts required bindings: " + ", ".join(contradictions)}
    unknown = set(identity.get("unknownFields", ()))
    unknown.update(field for field in _REQUIRED_DIMENSIONS if not identity.get(field))
    missing_required = [d for d in _REQUIRED_DIMENSIONS if d in unknown]

    if missing_required:
        return {
            "status": "UNKNOWN",
            "sufficient": False,
            "missingDimensions": missing_required,
            "weakSignalsOffered": weak_only,
            "reason": (
                "environment identity is incomplete: " + ", ".join(missing_required)
                + (". Offered instead: " + "; ".join(weak_only) if weak_only else "")
            ),
        }
    return {
        "status": "PASS",
        "sufficient": True,
        "missingDimensions": [],
        "weakSignalsOffered": weak_only,
        "reason": "process creation, project, map, module closure and adapter configuration are bound",
    }


def freshness_decision(
    claim_type: str,
    observation_domain: str,
    policy: Mapping[str, Any],
    *,
    bound_inputs: Mapping[str, str],
    cached_entry_age_seconds: int | None = None,
    dependency_changed: Sequence[str] = (),
    timed_out: bool = False,
) -> dict[str, Any]:
    """Decide whether a cached result may be reused for this claim."""
    receipt: dict[str, Any] = {
        "recordType": "CacheReuseReceipt",
        "receiptId": claim_type + ":" + observation_domain,
        "claimType": claim_type,
        "cacheKeyDigest": digest_with("continuity.core.v2", dict(sorted(bound_inputs.items()))),
        "boundInputs": dict(sorted(bound_inputs.items())),
        "freshnessPolicyId": str(policy.get("policyId", "")),
        "reused": False,
    }

    if timed_out:
        receipt["refusedReason"] = (
            "the observation timed out; a timeout is not a cache hit and does not convert "
            "a failed check into a reused result"
        )
        return receipt

    if observation_domain in ALWAYS_FRESH_DOMAINS:
        receipt["refusedReason"] = (
            observation_domain + " observations are always fresh; a historical observation "
            "cannot satisfy a freshness-required check"
        )
        return receipt

    if dependency_changed:
        receipt["refusedReason"] = (
            "dependency closure changed: " + ", ".join(sorted(dependency_changed))
        )
        return receipt

    max_age = policy.get("maxAgeSeconds")
    if max_age is not None and cached_entry_age_seconds is None:
        receipt["refusedReason"] = "cached entry age is unknown under maxAgeSeconds policy"
        return receipt
    if max_age is not None and cached_entry_age_seconds is not None:
        if cached_entry_age_seconds > int(max_age):
            receipt["refusedReason"] = (
                "cached entry is " + str(cached_entry_age_seconds) + "s old, beyond the "
                + str(max_age) + "s policy limit"
            )
            return receipt

    reusable = set(policy.get("reusableWhileUnchanged", ()))
    if reusable and not reusable.issuperset(set(bound_inputs)):
        unbound = sorted(set(bound_inputs) - reusable)
        receipt["refusedReason"] = (
            "inputs not covered by the reuse policy: " + ", ".join(unbound)
        )
        return receipt

    receipt["reused"] = True
    receipt["reason"] = (
        "pure comparison over unchanged frozen bytes; every relevant dependency is bound "
        "and stable"
    )
    return receipt


def build_cache_key(
    probe_id: str,
    *,
    implementation_digest: str,
    contract_digest: str,
    input_digests: Mapping[str, str],
    environment_digest: str,
    provider_digest: str,
    execution_path_digest: str,
) -> CacheKey:
    """Build a CityQA cache key. Reuses the existing six-part identity."""
    return CacheKey(
        probe_id=probe_id,
        implementation_digest=implementation_digest,
        contract_digest=contract_digest,
        input_digests=dict(input_digests),
        environment_digest=environment_digest,
        provider_digest=provider_digest,
        execution_path_digest=execution_path_digest,
    )
