"""Result vocabulary for the CityQA deterministic suite.

The five-state resolution contract and its companion enumerations are fixed by
IMPLEMENTATION DIRECTIVE section 5.  Nothing in this module carries operational
values: thresholds, tolerances and required evidence live in versioned policy
instances, never in Python.
"""

from __future__ import annotations

from enum import Enum

SCHEMA_VERSION = "1.0.0"


class _Vocab(str, Enum):
    """Base for the fixed string vocabularies."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)

    @classmethod
    def parse(cls, raw: str) -> "_Vocab":
        try:
            return cls(raw)
        except ValueError as exc:
            raise VocabularyError(
                f"{cls.__name__} does not admit {raw!r}; allowed: {cls.values()}"
            ) from exc


class VocabularyError(ValueError):
    """Raised when a value falls outside a fixed vocabulary."""


class Status(_Vocab):
    """The five-state resolution contract.

    PASS      required evidence present, assertion satisfied
    FAIL      required evidence present, assertion not satisfied
    UNKNOWN   required probe or evidence unavailable; no success conclusion
    ERROR     harness or probe implementation failure; no product conclusion
    NOT_RUN   a prior phase stop prevented execution
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


class Severity(_Vocab):
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATION = "information"


class DefectDomain(_Vocab):
    ENVIRONMENT = "environment"
    PRODUCT = "product"
    HARNESS = "harness"
    ORCHESTRATION = "orchestration"
    EVIDENCE = "evidence"
    PRESENTATION = "presentation"


class StopScope(_Vocab):
    """Scope halted by a stopping result.

    ``both`` is retained from the directive vocabulary.  It is deliberately not
    self-describing against three named scopes, so its expansion is resolved
    from the ``stopScopeExpansion`` table in ``contracts/failure_codes.v1.json``
    rather than assumed here.  See docs/SOURCE_AUTHORITY.md.
    """

    GENERATION = "generation"
    AUDIT = "audit"
    PROMOTION = "promotion"
    BOTH = "both"
    NONE = "none"


class AuthorityClass(_Vocab):
    """Who or what is entitled to establish a claim."""

    MACHINE = "machine"
    RECEIPT = "receipt"
    MEASUREMENT = "measurement"
    REGISTRY = "registry"
    GRAPH = "graph"
    PACKAGE = "package"
    PROCESS = "process"
    OBSERVATION = "observation"


class Verdict(_Vocab):
    """Audit verdict and promotion decision vocabulary."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    INDETERMINATE = "INDETERMINATE"


class ClaimType(_Vocab):
    IDENTITY = "IDENTITY"
    PRESENCE = "PRESENCE"
    EXACT_COUNT = "EXACT_COUNT"
    BOUNDED_VALUE = "BOUNDED_VALUE"
    ORDER = "ORDER"
    SET_EQUALITY = "SET_EQUALITY"
    HASH_EQUALITY = "HASH_EQUALITY"
    REFERENCE_CLOSURE = "REFERENCE_CLOSURE"
    PROVENANCE = "PROVENANCE"
    AUTHORITY = "AUTHORITY"
    GEOMETRY_RELATION = "GEOMETRY_RELATION"
    PERSISTENCE_EQUIVALENCE = "PERSISTENCE_EQUIVALENCE"
    EXECUTION_PATH = "EXECUTION_PATH"
    ROLE_SEPARATION = "ROLE_SEPARATION"
    VISUAL_CAPTURE = "VISUAL_CAPTURE"
    STATE_CLOSURE = "STATE_CLOSURE"


class VerificationMode(_Vocab):
    RECOMPUTE = "RECOMPUTE"
    REPLAY = "REPLAY"
    COMPARE = "COMPARE"
    VERIFY_DIGEST = "VERIFY_DIGEST"
    VERIFY_SIGNATURE = "VERIFY_SIGNATURE"
    VERIFY_REFERENCE = "VERIFY_REFERENCE"
    INDEPENDENT_ALGORITHM = "INDEPENDENT_ALGORITHM"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"


class Operator(_Vocab):
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    SET_EQUAL = "SET_EQUAL"
    SUBSET_OF = "SUBSET_OF"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    SEQUENCE_EQUAL = "SEQUENCE_EQUAL"


class ExitCode:
    """Stable process exit codes (directive section 16)."""

    PASS = 0
    FAIL = 2
    UNKNOWN = 3
    ERROR = 4
    INVALID_CONTRACT = 5
    BLOCKED_BY_PRIOR_STATE = 6
    UNAUTHORIZED = 7


#: Statuses that never permit a success conclusion downstream.
NON_CONCLUSIVE = frozenset({Status.UNKNOWN, Status.ERROR, Status.NOT_RUN})

#: Severities that stop a pipeline when paired with a FAIL and a stopping scope.
STOPPING_SEVERITIES = frozenset({Severity.BLOCKER, Severity.CRITICAL})

#: Ordering used whenever severities must be sorted deterministically.
SEVERITY_ORDER: dict[str, int] = {
    Severity.BLOCKER.value: 0,
    Severity.CRITICAL.value: 1,
    Severity.MAJOR.value: 2,
    Severity.MINOR.value: 3,
    Severity.INFORMATION.value: 4,
}

#: Ordering used whenever statuses must be sorted deterministically.
STATUS_ORDER: dict[str, int] = {
    Status.ERROR.value: 0,
    Status.FAIL.value: 1,
    Status.UNKNOWN.value: 2,
    Status.NOT_RUN.value: 3,
    Status.PASS.value: 4,
}


def status_exit_code(status: Status | str) -> int:
    """Map a terminal status onto the stable process exit code."""
    value = Status(status).value
    return {
        Status.PASS.value: ExitCode.PASS,
        Status.FAIL.value: ExitCode.FAIL,
        Status.UNKNOWN.value: ExitCode.UNKNOWN,
        Status.ERROR.value: ExitCode.ERROR,
        Status.NOT_RUN.value: ExitCode.BLOCKED_BY_PRIOR_STATE,
    }[value]


def verdict_exit_code(verdict: Verdict | str) -> int:
    """Map an audit verdict or promotion decision onto its exit code."""
    value = Verdict(verdict).value
    return {
        Verdict.APPROVE.value: ExitCode.PASS,
        Verdict.REJECT.value: ExitCode.FAIL,
        Verdict.INDETERMINATE.value: ExitCode.UNKNOWN,
    }[value]
