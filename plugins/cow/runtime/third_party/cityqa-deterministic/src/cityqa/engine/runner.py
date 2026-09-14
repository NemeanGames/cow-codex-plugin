"""The deterministic QA runner.

Phases execute in contract order; probes execute inside a phase in stable order
by probeId. Execution is serial. Concurrency is not offered, because the
directive's precondition for it -- proven deterministic ordering, isolated
outputs and race-free state -- is not yet demonstrated, and a nondeterministic
QA runner cannot support a hash-bound receipt.

A probe reports a measurement. This module decides nothing about limits; it
compares against the contract, applies the contract's stop rules, and records
what happened.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from .cache import CacheKey, ProbeCache, compute_input_digests
from .canonical import canonical_path
from .contracts import ContractSet, MissingContractValue, ProbeSpec
from .environment_identity import (
    environment_identity,
    execution_path_identity,
    implementation_digest,
    module_digest,
)
from .evidence import EvidenceLedger
from .hashing import digest_value
from .state_closure import utc_now
from .statuses import SCHEMA_VERSION, DefectDomain, Severity, Status
from .stop_rules import blocked_phases_after, should_stop

__all__ = ["ProbeContext", "ProbeOutcome", "ProbeRegistry", "Runner", "RunOutput"]


class ProbeOutcome:
    """What a probe reports.

    A probe never chooses its own severity, stop scope or required flag: those
    are contract properties. It reports what it measured and whether that
    satisfies the contract value it was given.
    """

    __slots__ = ("status", "observed", "expected", "evidence_ids", "failure_code",
                 "message_code", "detail", "unit")

    def __init__(
        self,
        status: str,
        observed: Any = None,
        expected: Any = None,
        evidence_ids: Sequence[str] = (),
        failure_code: str | None = None,
        message_code: str | None = None,
        detail: Mapping[str, Any] | None = None,
        unit: str | None = None,
    ) -> None:
        self.status = Status(status).value
        self.observed = observed
        self.expected = expected
        self.evidence_ids = list(evidence_ids)
        self.failure_code = failure_code
        self.message_code = message_code
        self.detail = dict(detail or {})
        self.unit = unit

    @classmethod
    def unknown(cls, reason_code: str, detail: Mapping[str, Any] | None = None,
                expected: Any = None) -> "ProbeOutcome":
        """A probe that could not obtain what it needed.

        UNKNOWN never becomes PASS anywhere downstream.
        """
        return cls(
            Status.UNKNOWN.value,
            observed=None,
            expected=expected,
            failure_code=reason_code,
            message_code=reason_code,
            detail=detail,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ProbeOutcome(" + self.status + ")"


class ProbeContext:
    """Everything a probe is permitted to see."""

    __slots__ = ("run_id", "contract", "candidate_root", "project_path", "payload_path",
                 "evidence", "adapters", "captured_at", "fixture_mode", "state",
                 "outputs_root", "baseline_path")

    def __init__(
        self,
        run_id: str,
        contract: ContractSet,
        candidate_root: Path,
        evidence: EvidenceLedger,
        adapters: Mapping[str, Any],
        outputs_root: Path,
        project_path: Path | None = None,
        payload_path: Path | None = None,
        baseline_path: Path | None = None,
        fixture_mode: bool = False,
    ) -> None:
        self.run_id = run_id
        self.contract = contract
        self.candidate_root = candidate_root
        self.project_path = project_path
        self.payload_path = payload_path
        self.baseline_path = baseline_path
        self.evidence = evidence
        self.adapters = dict(adapters)
        self.outputs_root = outputs_root
        self.fixture_mode = fixture_mode
        self.captured_at = utc_now()
        self.state: MutableMapping[str, Any] = {}

    def adapter(self, name: str) -> Any:
        return self.adapters.get(name)

    def logical(self, path: str | Path) -> str:
        """Path relative to the candidate root, in logical form."""
        target = Path(path)
        try:
            return canonical_path(str(target.relative_to(self.candidate_root)))
        except ValueError:
            return canonical_path(str(target))


ProbeFunction = Callable[[ProbeContext, ProbeSpec], ProbeOutcome]


class ProbeRegistry:
    """Maps probeId to implementation."""

    def __init__(self) -> None:
        self._functions: dict[str, ProbeFunction] = {}
        self._modules: dict[str, str] = {}

    def register(self, probe_id: str, function: ProbeFunction) -> None:
        self._functions[probe_id] = function
        self._modules[probe_id] = getattr(function, "__module__", "")

    def probe(self, probe_id: str) -> ProbeFunction | None:
        return self._functions.get(probe_id)

    def module_for(self, probe_id: str) -> str:
        return self._modules.get(probe_id, "")

    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(self._functions))

    def __contains__(self, probe_id: object) -> bool:
        return probe_id in self._functions


class RunOutput:
    """Everything one run produced."""

    __slots__ = ("run_id", "results", "evidence", "manifest", "terminal_status",
                 "stopped_by", "cache_statistics", "environment", "execution_path")

    def __init__(
        self,
        run_id: str,
        results: Sequence[Mapping[str, Any]],
        evidence: EvidenceLedger,
        manifest: Mapping[str, Any],
        terminal_status: str,
        stopped_by: str | None,
        cache_statistics: Mapping[str, Any],
        environment: Mapping[str, Any],
        execution_path: Mapping[str, Any],
    ) -> None:
        self.run_id = run_id
        self.results = list(results)
        self.evidence = evidence
        self.manifest = dict(manifest)
        self.terminal_status = terminal_status
        self.stopped_by = stopped_by
        self.cache_statistics = dict(cache_statistics)
        self.environment = dict(environment)
        self.execution_path = dict(execution_path)

    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in Status}
        for result in self.results:
            counts[str(result["status"])] += 1
        return counts

    def failures(self) -> list[Mapping[str, Any]]:
        return [r for r in self.results if r["status"] == Status.FAIL.value]

    def by_probe(self, probe_id: str) -> Mapping[str, Any] | None:
        for result in self.results:
            if result["probeId"] == probe_id:
                return result
        return None


class Runner:
    """Executes the QA contract against a candidate."""

    def __init__(
        self,
        contract: ContractSet,
        registry: ProbeRegistry,
        cache: ProbeCache | None = None,
        fixture_mode: bool = False,
        entry_point: str = "production",
    ) -> None:
        self.contract = contract
        self.registry = registry
        self.cache = cache
        self.fixture_mode = fixture_mode
        self.entry_point = entry_point
        self._implementation_digest = implementation_digest()

    # -- result construction --------------------------------------------

    def _result(
        self,
        run_id: str,
        spec: ProbeSpec,
        status: str,
        observed: Any = None,
        expected: Any = None,
        evidence_ids: Sequence[str] = (),
        failure_code: str | None = None,
        message_code: str | None = None,
        blocked_phases: Sequence[str] = (),
        cache_key: str | None = None,
        cached: bool = False,
        defect_domain: str | None = None,
        severity: str | None = None,
        duration_ms: int = 0,
        unit: str | None = None,
    ) -> dict[str, Any]:
        status_value = Status(status).value
        if status_value in (Status.PASS.value, Status.NOT_RUN.value):
            # A probe that passed has no failure, and one that never ran has not
            # earned the failure code its contract entry would assign it.
            code = None
        elif failure_code is not None:
            code = failure_code
        else:
            code = spec.failure_code
        return {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "probeId": spec.probe_id,
            "phase": spec.phase,
            "status": status_value,
            "severity": Severity(severity or spec.severity).value,
            "defectDomain": DefectDomain(defect_domain or spec.defect_domain).value,
            "failureCode": code,
            "stopScope": spec.stop_scope,
            "required": spec.required,
            "unknownPromotionRule": spec.unknown_promotion_rule,
            "metric": spec.metric,
            "operator": spec.operator,
            "unit": unit if unit is not None else spec.unit,
            "expected": expected,
            "observed": observed,
            "evidenceIds": sorted(set(evidence_ids)),
            "blockedPhases": list(blocked_phases),
            "contractRef": spec.contract_ref,
            "requiredAuthority": spec.required_authority,
            "requiredEvidenceTypes": list(spec.required_evidence_types),
            "cacheKey": cache_key,
            "cached": cached,
            "durationMs": duration_ms,
            "messageCode": message_code,
        }

    # -- cache ----------------------------------------------------------

    def _cache_key(
        self,
        spec: ProbeSpec,
        context: ProbeContext,
        environment_digest: str,
        provider_digest: str,
        execution_path_digest: str,
    ) -> CacheKey:
        return CacheKey(
            probe_id=spec.probe_id,
            implementation_digest=module_digest(self.registry.module_for(spec.probe_id)),
            contract_digest=self.contract.contract_digest,
            input_digests=compute_input_digests(context.candidate_root, spec.input_patterns),
            environment_digest=environment_digest,
            provider_digest=provider_digest,
            execution_path_digest=execution_path_digest,
        )

    # -- execution ------------------------------------------------------

    def run(
        self,
        run_id: str,
        context: ProbeContext,
        only_probes: Sequence[str] | None = None,
    ) -> RunOutput:
        """Execute the contract. Never raises for a probe defect.

        A probe that raises produces status ERROR in the harness defect domain
        and contributes zero product failures. The distinction matters: a
        broken probe is not evidence about the city.
        """
        import time

        provider_identity = {}
        unreal = context.adapter("unreal")
        if unreal is not None and hasattr(unreal, "identity"):
            try:
                provider_identity = unreal.identity()
            except Exception:
                provider_identity = {"identity": "UNAVAILABLE"}

        environment = environment_identity(provider_identity)
        execution_path = execution_path_identity(
            execution_path_id="producer.fixture" if self.fixture_mode else "producer.production",
            entry_point=self.entry_point,
            contract_digest=self.contract.contract_digest,
            fixture_mode=self.fixture_mode,
        )
        provider_digest = digest_value(provider_identity)
        execution_path_digest = execution_path["entryPointDigest"]

        selected = set(only_probes) if only_probes is not None else None
        results: list[dict[str, Any]] = []
        stopped_by: str | None = None
        stop_reason: str | None = None
        blocked_from_phase: str | None = None
        unrun_in_stopping_phase: list[ProbeSpec] = []

        for phase in self.contract.phase_order:
            if blocked_from_phase is not None:
                continue
            phase_specs = list(self.contract.probes_for_phase(phase))
            for position, spec in enumerate(phase_specs):
                if selected is not None and spec.probe_id not in selected:
                    continue

                started = time.monotonic()
                cache_key: CacheKey | None = None
                cached_result: dict[str, Any] | None = None

                if self.cache is not None and spec.cacheable:
                    try:
                        cache_key = self._cache_key(
                            spec, context, environment["digest"], provider_digest,
                            execution_path_digest,
                        )
                        cached_result = self.cache.lookup(cache_key)
                    except Exception:
                        # A cache failure is never allowed to change a verdict.
                        cache_key = None
                        cached_result = None

                if cached_result is not None:
                    cached_result["runId"] = run_id
                    results.append(cached_result)
                    result = cached_result
                else:
                    result = self._execute(run_id, spec, context, cache_key)
                    elapsed = int((time.monotonic() - started) * 1000)
                    result["durationMs"] = elapsed
                    results.append(result)
                    if (
                        self.cache is not None
                        and cache_key is not None
                        and spec.cacheable
                    ):
                        try:
                            self.cache.store(cache_key, result)
                        except Exception:
                            pass

                decision = should_stop(
                    status=result["status"],
                    required=result["required"],
                    severity=result["severity"],
                    stop_scope=result["stopScope"],
                    scope_expansion=self.contract.expand_stop_scope(result["stopScope"]),
                    pipeline="generation",
                )
                if decision.stop:
                    stopped_by = spec.probe_id
                    stop_reason = decision.reason
                    blocked = blocked_phases_after(phase, self.contract.phase_order)
                    result["blockedPhases"] = list(blocked)
                    result["stoppedPipeline"] = True
                    blocked_from_phase = phase
                    # Probes later in the stopping phase did not run either. They
                    # are recorded as NOT_RUN rather than omitted: a result set
                    # that silently lacks a probe reads as coverage it never had.
                    unrun_in_stopping_phase = phase_specs[position + 1:]
                    break

        if blocked_from_phase is not None:
            for spec in unrun_in_stopping_phase:
                if selected is not None and spec.probe_id not in selected:
                    continue
                results.append(
                    self._result(
                        run_id, spec, Status.NOT_RUN.value,
                        observed=None,
                        expected=None,
                        message_code="NOT_RUN_STOP_EARLIER_IN_PHASE",
                    )
                )
            for phase in blocked_phases_after(blocked_from_phase, self.contract.phase_order):
                for spec in self.contract.probes_for_phase(phase):
                    if selected is not None and spec.probe_id not in selected:
                        continue
                    results.append(
                        self._result(
                            run_id, spec, Status.NOT_RUN.value,
                            observed=None,
                            expected=None,
                            message_code="NOT_RUN_PRIOR_PHASE_STOP",
                        )
                    )

        counts = {status.value: 0 for status in Status}
        for result in results:
            counts[str(result["status"])] += 1

        terminal = self._terminal_status(counts)
        # A phase counts as executed when any probe in it produced a result. The
        # stopping phase is executed even though some of its probes are NOT_RUN,
        # so the two lists stay disjoint.
        executed = {r["phase"] for r in results if r["status"] != Status.NOT_RUN.value}
        executed_phases = sorted(executed, key=lambda p: self.contract.phase_order.index(p))
        blocked_phases = sorted(
            {r["phase"] for r in results if r["status"] == Status.NOT_RUN.value} - executed,
            key=lambda p: self.contract.phase_order.index(p),
        )

        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "startedAt": context.captured_at,
            "completedAt": utc_now(),
            "contractDigest": self.contract.contract_digest,
            "policySetDigest": self.contract.policy_set_digest,
            "schemaSetDigest": self.contract.schemas.set_digest(),
            "candidateDigest": str(context.state.get("candidateDigest", "")) or None,
            "baselineDigest": context.state.get("baselineDigest"),
            "environmentIdentityDigest": environment["digest"],
            "implementationDigest": self._implementation_digest,
            "executionPathId": execution_path["executionPathId"],
            "fixtureMode": self.fixture_mode,
            "phasesExecuted": executed_phases,
            "phasesBlocked": blocked_phases,
            "resultCounts": counts,
            "terminalStatus": terminal,
            "stateClosure": "UNKNOWN",
            "resultsDigest": digest_value({"results": results}),
            "evidenceDigest": context.evidence.digest(),
            "stoppedByProbeId": stopped_by,
            "stopReason": stop_reason,
            "outputs": [],
        }
        if manifest["candidateDigest"] is None:
            manifest.pop("candidateDigest")

        return RunOutput(
            run_id=run_id,
            results=results,
            evidence=context.evidence,
            manifest=manifest,
            terminal_status=terminal,
            stopped_by=stopped_by,
            cache_statistics=self.cache.statistics() if self.cache else {"enabled": False},
            environment=environment,
            execution_path=execution_path,
        )

    def _execute(
        self,
        run_id: str,
        spec: ProbeSpec,
        context: ProbeContext,
        cache_key: CacheKey | None,
    ) -> dict[str, Any]:
        """Run one probe, converting any defect into ERROR."""
        function = self.registry.probe(spec.probe_id)
        key_digest = cache_key.digest() if cache_key is not None else None

        if function is None:
            return self._result(
                run_id, spec, Status.UNKNOWN.value,
                failure_code="HARNESS_PROBE_NOT_IMPLEMENTED",
                message_code="HARNESS_PROBE_NOT_IMPLEMENTED",
                defect_domain=DefectDomain.HARNESS.value,
                cache_key=key_digest,
                expected={"probeImplementation": "registered"},
                observed={"probeImplementation": "absent"},
            )

        expected: Any = None
        if spec.contract_ref:
            try:
                expected = self.contract.resolve(spec.contract_ref)
            except MissingContractValue:
                # No fallback: an unresolvable contract value is UNKNOWN.
                return self._result(
                    run_id, spec, Status.UNKNOWN.value,
                    failure_code="CONTRACT_VALUE_UNRESOLVED",
                    message_code="CONTRACT_VALUE_UNRESOLVED",
                    defect_domain=DefectDomain.EVIDENCE.value,
                    expected={"contractRef": spec.contract_ref},
                    observed=None,
                    cache_key=key_digest,
                )

        try:
            outcome = function(context, spec)
        except Exception as exc:  # a probe defect is never a product failure
            return self._result(
                run_id, spec, Status.ERROR.value,
                failure_code="HARNESS_PROBE_EXCEPTION",
                message_code="HARNESS_PROBE_EXCEPTION",
                defect_domain=DefectDomain.HARNESS.value,
                severity=Severity.CRITICAL.value,
                expected=expected,
                observed={
                    "exceptionType": type(exc).__name__,
                    "traceDigest": digest_value(
                        {"trace": traceback.format_exception_only(type(exc), exc)}
                    ),
                },
                cache_key=key_digest,
            )

        if not isinstance(outcome, ProbeOutcome):
            return self._result(
                run_id, spec, Status.ERROR.value,
                failure_code="HARNESS_PROBE_CONTRACT_VIOLATION",
                message_code="HARNESS_PROBE_CONTRACT_VIOLATION",
                defect_domain=DefectDomain.HARNESS.value,
                severity=Severity.CRITICAL.value,
                expected=expected,
                observed={"returned": type(outcome).__name__},
                cache_key=key_digest,
            )

        unresolved = context.evidence.unresolved(outcome.evidence_ids)
        if unresolved and outcome.status == Status.PASS.value:
            # A PASS that names evidence which does not exist is not a PASS.
            return self._result(
                run_id, spec, Status.UNKNOWN.value,
                failure_code="EVIDENCE_REFERENCE_UNRESOLVED",
                message_code="EVIDENCE_REFERENCE_UNRESOLVED",
                defect_domain=DefectDomain.EVIDENCE.value,
                expected=outcome.expected if outcome.expected is not None else expected,
                observed={"unresolvedEvidenceIds": list(unresolved)},
                evidence_ids=outcome.evidence_ids,
                cache_key=key_digest,
            )

        return self._result(
            run_id, spec, outcome.status,
            observed=outcome.observed,
            expected=outcome.expected if outcome.expected is not None else expected,
            evidence_ids=outcome.evidence_ids,
            failure_code=outcome.failure_code,
            message_code=outcome.message_code,
            cache_key=key_digest,
            unit=outcome.unit,
        )

    @staticmethod
    def _terminal_status(counts: Mapping[str, int]) -> str:
        """The run's terminal status.

        Precedence follows severity of consequence, not count: one ERROR
        outranks any number of passes.
        """
        if counts.get(Status.ERROR.value, 0):
            return Status.ERROR.value
        if counts.get(Status.FAIL.value, 0):
            return Status.FAIL.value
        if counts.get(Status.UNKNOWN.value, 0) or counts.get(Status.NOT_RUN.value, 0):
            return Status.UNKNOWN.value
        if counts.get(Status.PASS.value, 0):
            return Status.PASS.value
        return Status.UNKNOWN.value
