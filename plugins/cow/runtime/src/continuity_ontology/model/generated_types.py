"""GENERATED FROM ontology/metamodel.json -- DO NOT EDIT

semanticModelDigest: sha256:0e07de0be6ddc33f77d15bf5d7144f2ba48edf23beb878b4257583718f1e706d
"""

from __future__ import annotations

from enum import Enum
from typing import Any

SEMANTIC_MODEL_DIGEST = 'sha256:0e07de0be6ddc33f77d15bf5d7144f2ba48edf23beb878b4257583718f1e706d'
METAMODEL_VERSION = '2.0.0'


class AcceptanceDimension(str, Enum):
    'The four release dimensions that must never collapse into one green status (R54).'
    SOFTWARE_ACCEPTED = 'SOFTWARE_ACCEPTED'
    EFFICIENCY_VERIFIED = 'EFFICIENCY_VERIFIED'
    DEPLOYMENT_VERIFIED = 'DEPLOYMENT_VERIFIED'
    LIVE_ADAPTER_QUALIFIED = 'LIVE_ADAPTER_QUALIFIED'


class AccountingRule(str, Enum):
    'How a subset field relates to its parent total for a given provider accounting version.'
    SUBSET_OF_INPUT = 'SUBSET_OF_INPUT'
    SUBSET_OF_OUTPUT = 'SUBSET_OF_OUTPUT'
    DISJOINT_ADDITIVE = 'DISJOINT_ADDITIVE'
    UNSPECIFIED = 'UNSPECIFIED'


class AuthorityClass(str, Enum):
    'The seven legacy authority classes preserved at each assertion boundary. Not a numeric trust ranking: each class establishes a different kind of claim and admissibility is decided per claim type.'
    AUTHORITATIVE_SOURCE = 'AUTHORITATIVE_SOURCE'
    DETERMINISTIC_DERIVATION = 'DETERMINISTIC_DERIVATION'
    PROVIDER_OBSERVATION = 'PROVIDER_OBSERVATION'
    OPERATION_OWNED_RESULT = 'OPERATION_OWNED_RESULT'
    HEURISTIC_DECISION = 'HEURISTIC_DECISION'
    POLICY_OR_SYNTHETIC_AID = 'POLICY_OR_SYNTHETIC_AID'
    CALLER_ASSERTION = 'CALLER_ASSERTION'


class BundleLifecycle(str, Enum):
    OPEN = 'OPEN'
    SEALED = 'SEALED'
    DELTA = 'DELTA'
    MATERIALIZED = 'MATERIALIZED'
    INVALIDATED = 'INVALIDATED'


class ClaimLifecycle(str, Enum):
    "Distinct dimension from Status. A claim's lifecycle never aliases a check result."
    DRAFT = 'DRAFT'
    SEALED = 'SEALED'
    AUDITED = 'AUDITED'
    SUPERSEDED = 'SUPERSEDED'
    REVOKED = 'REVOKED'


class ClosureKind(str, Enum):
    ENUMERATION = 'ENUMERATION'
    MUTATION_SET = 'MUTATION_SET'
    DEPENDENCY = 'DEPENDENCY'
    EVIDENCE = 'EVIDENCE'
    ROLLBACK = 'ROLLBACK'
    STATE = 'STATE'


class ConflictDisposition(str, Enum):
    UNRESOLVED = 'UNRESOLVED'
    ADJUDICATED_ACCEPT = 'ADJUDICATED_ACCEPT'
    ADJUDICATED_REJECT = 'ADJUDICATED_REJECT'
    ADJUDICATED_SPLIT_SCOPE = 'ADJUDICATED_SPLIT_SCOPE'


class EvidenceAdmissibility(str, Enum):
    ADMISSIBLE = 'ADMISSIBLE'
    INADMISSIBLE_SCOPE = 'INADMISSIBLE_SCOPE'
    INADMISSIBLE_AUTHORITY = 'INADMISSIBLE_AUTHORITY'
    INADMISSIBLE_FRESHNESS = 'INADMISSIBLE_FRESHNESS'
    INADMISSIBLE_INCOMPLETE = 'INADMISSIBLE_INCOMPLETE'
    INADMISSIBLE_SYNTHETIC_FOR_LIVE = 'INADMISSIBLE_SYNTHETIC_FOR_LIVE'


class ExecutionPurpose(str, Enum):
    'Timing PURPOSE. Verification and rework are labelled subsets, never additive siblings of active time.'
    PLANNING = 'PLANNING'
    RETRIEVAL = 'RETRIEVAL'
    GENERATION = 'GENERATION'
    VERIFICATION = 'VERIFICATION'
    AUDIT = 'AUDIT'
    PACKAGING = 'PACKAGING'
    RECOVERY_REWORK = 'RECOVERY_REWORK'


class ExecutionState(str, Enum):
    'Timing STATE. Orthogonal to purpose; a span has exactly one of each.'
    ACTIVE_EXECUTION = 'ACTIVE_EXECUTION'
    TOOL_WAIT = 'TOOL_WAIT'
    HUMAN_WAIT = 'HUMAN_WAIT'
    IDLE = 'IDLE'
    UNKNOWN = 'UNKNOWN'


class LifecycleState(str, Enum):
    CREATED = 'CREATED'
    VALIDATED = 'VALIDATED'
    READY = 'READY'
    RUNNING = 'RUNNING'
    CHECKPOINTED = 'CHECKPOINTED'
    COMPLETED = 'COMPLETED'
    BLOCKED = 'BLOCKED'
    FAILED = 'FAILED'
    ERRORED = 'ERRORED'
    CANCELED = 'CANCELED'


class MeasurementBasis(str, Enum):
    'Observed, estimated and unknown never share a field. Missing provider usage is UNKNOWN, never zero.'
    OBSERVED = 'OBSERVED'
    ESTIMATED = 'ESTIMATED'
    UNKNOWN = 'UNKNOWN'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class MetricAvailability(str, Enum):
    'Typed unavailable results replace NaN and infinity everywhere.'
    AVAILABLE = 'AVAILABLE'
    UNDEFINED_ZERO_DENOMINATOR = 'UNDEFINED_ZERO_DENOMINATOR'
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    INADMISSIBLE_INPUTS = 'INADMISSIBLE_INPUTS'
    INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'


class ObservationChannel(str, Enum):
    FILE_BYTES = 'FILE_BYTES'
    PROCESS_API = 'PROCESS_API'
    PROVIDER_API = 'PROVIDER_API'
    ENGINE_API = 'ENGINE_API'
    SCREEN_CAPTURE = 'SCREEN_CAPTURE'
    USER_REPORT = 'USER_REPORT'
    LOG_STREAM = 'LOG_STREAM'
    NOT_OBSERVED = 'NOT_OBSERVED'


class OperationalOwnership(str, Enum):
    'Whether the asserting actor owned the operation whose effect is claimed.'
    DIRECTLY_OWNED = 'DIRECTLY_OWNED'
    DELEGATED_WITH_RECEIPT = 'DELEGATED_WITH_RECEIPT'
    OBSERVED_THIRD_PARTY = 'OBSERVED_THIRD_PARTY'
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    UNKNOWN = 'UNKNOWN'


class Origin(str, Enum):
    'Orthogonal dimension: where the assertion came from.'
    SOURCE_ARTIFACT = 'SOURCE_ARTIFACT'
    LIVE_OBSERVATION = 'LIVE_OBSERVATION'
    DERIVATION = 'DERIVATION'
    POLICY = 'POLICY'
    HUMAN_INPUT = 'HUMAN_INPUT'
    SYNTHETIC_FIXTURE = 'SYNTHETIC_FIXTURE'


class ProductionMethod(str, Enum):
    MEASURED = 'MEASURED'
    RECOMPUTED = 'RECOMPUTED'
    REPLAYED = 'REPLAYED'
    TRANSCRIBED = 'TRANSCRIBED'
    ESTIMATED = 'ESTIMATED'
    ASSERTED = 'ASSERTED'
    GENERATED = 'GENERATED'


class PromotionState(str, Enum):
    NOT_EVALUATED = 'NOT_EVALUATED'
    ELIGIBLE = 'ELIGIBLE'
    INELIGIBLE = 'INELIGIBLE'
    PROMOTED = 'PROMOTED'
    WITHHELD = 'WITHHELD'


class Qualification(str, Enum):
    'Applies to a reused source, an implementation, or an adapter.'
    QUALIFIED = 'QUALIFIED'
    PROVISIONAL = 'PROVISIONAL'
    TENTATIVE = 'TENTATIVE'
    NEGATIVELY_QUALIFIED = 'NEGATIVELY_QUALIFIED'
    BLOCKED = 'BLOCKED'
    NOT_ASSESSED = 'NOT_ASSESSED'


class ResourceKind(str, Enum):
    'Provider cache accounting differs by provider and is pinned per providerAccountingVersion. VENDOR_CACHED_INPUT_TOKENS is a SUBSET_OF_INPUT (e.g. OpenAI prompt_tokens_details.cached_tokens lies inside prompt_tokens). VENDOR_CACHE_READ_INPUT_TOKENS and VENDOR_CACHE_CREATION_INPUT_TOKENS are DISJOINT_ADDITIVE with VENDOR_INPUT_TOKENS (observed on Anthropic messages usage: input_tokens=2 alongside cache_read_input_tokens=40399). A measurement names the layout it follows; the ledger never assumes one.'
    VENDOR_INPUT_TOKENS = 'VENDOR_INPUT_TOKENS'
    VENDOR_OUTPUT_TOKENS = 'VENDOR_OUTPUT_TOKENS'
    VENDOR_CACHED_INPUT_TOKENS = 'VENDOR_CACHED_INPUT_TOKENS'
    VENDOR_CACHE_READ_INPUT_TOKENS = 'VENDOR_CACHE_READ_INPUT_TOKENS'
    VENDOR_CACHE_CREATION_INPUT_TOKENS = 'VENDOR_CACHE_CREATION_INPUT_TOKENS'
    VENDOR_REASONING_OUTPUT_TOKENS = 'VENDOR_REASONING_OUTPUT_TOKENS'
    LOCAL_MODEL_INPUT_TOKENS = 'LOCAL_MODEL_INPUT_TOKENS'
    LOCAL_MODEL_OUTPUT_TOKENS = 'LOCAL_MODEL_OUTPUT_TOKENS'
    TOOL_RUNTIME_MS = 'TOOL_RUNTIME_MS'
    RETRY_COUNT = 'RETRY_COUNT'
    FAILED_ATTEMPT_COUNT = 'FAILED_ATTEMPT_COUNT'
    METERED_COMPUTE_MS = 'METERED_COMPUTE_MS'
    MONEY_MINOR_UNITS = 'MONEY_MINOR_UNITS'


class ReuseDisposition(str, Enum):
    REUSE_UNCHANGED = 'REUSE_UNCHANGED'
    WRAP = 'WRAP'
    EXTEND_WITH_MIGRATION = 'EXTEND_WITH_MIGRATION'
    REPLACE_WITH_PROVEN_EQUIVALENCE = 'REPLACE_WITH_PROVEN_EQUIVALENCE'
    REFERENCE_ONLY = 'REFERENCE_ONLY'
    NOT_AVAILABLE = 'NOT_AVAILABLE'


class Status(str, Enum):
    'Five-state per-check resolution contract. Reused verbatim from cityqa.engine.statuses.Status; the compatibility test asserts equality of the member sets.'
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNKNOWN = 'UNKNOWN'
    ERROR = 'ERROR'
    NOT_RUN = 'NOT_RUN'


class Verdict(str, Enum):
    'Program/auditor disposition. Distinct from Status and from lifecycle.'
    APPROVE = 'APPROVE'
    REJECT = 'REJECT'
    INDETERMINATE = 'INDETERMINATE'


class VerificationStatus(str, Enum):
    UNVERIFIED = 'UNVERIFIED'
    PRODUCER_ASSERTED = 'PRODUCER_ASSERTED'
    INDEPENDENTLY_VERIFIED = 'INDEPENDENTLY_VERIFIED'
    CONTRADICTED = 'CONTRADICTED'
    INADMISSIBLE = 'INADMISSIBLE'


class ViewLifecycle(str, Enum):
    WIP_DIAGNOSTIC = 'WIP_DIAGNOSTIC'
    COMMITTED_PROJECTION = 'COMMITTED_PROJECTION'
    STALE = 'STALE'
    UNAVAILABLE = 'UNAVAILABLE'


#: Field tables keyed by entity, then field name.
ENTITY_FIELDS: dict[str, dict[str, dict[str, Any]]] = {
    'AcceptanceReceipt': {
        'acceptedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'accountingId': {'type': 'id', 'required': True, 'python': 'str'},
        'correctsReceiptId': {'type': 'id', 'required': False, 'python': 'str'},
        'firstQualifyingAttempt': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'partition': {'type': 'string', 'required': True, 'python': 'str'},
        'receiptId': {'type': 'id', 'required': True, 'python': 'str'},
        'requiredGateResults': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'revocationReason': {'type': 'string', 'required': False, 'python': 'str'},
        'revoked': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'weight': {'type': 'decimal', 'required': True, 'python': 'str'},
        'workUnitPolicyVersion': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'AcceptedWorkLedgerEntry': {
        'accountingId': {'type': 'id', 'required': True, 'python': 'str'},
        'delta': {'type': 'string', 'required': True, 'python': 'str'},
        'measurementWindow': {'type': 'string', 'required': True, 'python': 'str'},
        'receiptId': {'type': 'id', 'required': True, 'python': 'str'},
        'sequence': {'type': 'integer', 'required': True, 'python': 'int'},
        'weight': {'type': 'decimal', 'required': True, 'python': 'str'},
    },
    'AdjudicationReceipt': {
        'authorizedByRole': {'type': 'string', 'required': True, 'python': 'str'},
        'citedEvidence': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'citedPolicy': {'type': 'string', 'required': True, 'python': 'str'},
        'conflictId': {'type': 'id', 'required': True, 'python': 'str'},
        'disposition': {'type': {'enum': 'ConflictDisposition'}, 'required': True, 'python': 'ConflictDisposition'},
        'rationale': {'type': 'text', 'required': True, 'python': 'str'},
    },
    'Artifact': {
        'artifactKind': {'type': 'string', 'required': True, 'python': 'str'},
        'name': {'type': 'string', 'required': True, 'python': 'str'},
        'versions': {'type': {'list': {'ref': 'ArtifactVersion'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
    },
    'ArtifactVersion': {
        'artifact': {'type': {'ref': 'Artifact'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'contentDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'derivationReceipt': {'type': 'digest', 'required': False, 'python': 'str'},
        'directlyDerivedFrom': {'type': {'list': 'digest'}, 'required': False, 'python': 'list[str]'},
        'mediaType': {'type': 'string', 'required': False, 'python': 'str'},
        'sizeBytes': {'type': 'integer', 'required': True, 'python': 'int'},
    },
    'AuditResult': {
        'auditId': {'type': 'id', 'required': True, 'python': 'str'},
        'auditInputManifestDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'auditorImplementationDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'auditorRole': {'type': 'string', 'required': True, 'python': 'str'},
        'commonModeDependencies': {'type': {'list': {'map': 'string'}}, 'required': True, 'python': 'list[dict[str, str]]'},
        'disagreedWithProducer': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
        'frozenBundleDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'mandatoryTotals': {'type': {'map': 'integer'}, 'required': True, 'python': 'dict[str, int]'},
        'resultDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'verdict': {'type': {'enum': 'Verdict'}, 'required': True, 'python': 'Verdict'},
        'verdictRationale': {'type': 'text', 'required': True, 'python': 'str'},
        'verifications': {'type': {'list': {'ref': 'Verification'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
    },
    'AuthorizedOperation': {
        'authorizedScope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'capability': {'type': {'ref': 'Capability'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'expiresAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'grantDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'grantedByRole': {'type': 'string', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'replayGuard': {'type': 'string', 'required': True, 'python': 'str'},
        'secretsExcluded': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'BenchmarkPair': {
        'assistedAccepted': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'assistedTraceRef': {'type': 'digest', 'required': True, 'python': 'str'},
        'baselineAccepted': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'baselineTraceRef': {'type': 'digest', 'required': True, 'python': 'str'},
        'cacheStratum': {'type': 'string', 'required': True, 'python': 'str'},
        'contaminationChecks': {'type': {'list': {'object': {'checkId': {'type': 'id', 'required': True}, 'status': {'type': {'enum': 'Status'}, 'required': True}, 'reason': {'type': 'string', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'equivalenceContractDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'exclusionReason': {'type': 'string', 'required': False, 'python': 'str'},
        'includedInCohort': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'pairId': {'type': 'id', 'required': True, 'python': 'str'},
        'receipts': {'type': 'json', 'required': False, 'python': 'Any'},
        'setupAmortized': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'verificationCosts': {'type': {'ref': 'VerificationCostSet'}, 'required': False, 'python': 'str | dict[str, Any]'},
    },
    'BenchmarkProtocol': {
        'equivalenceContractDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'frozen': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'minimumPairs': {'type': 'integer', 'required': True, 'python': 'int'},
        'preRegisteredAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'protocolId': {'type': 'id', 'required': True, 'python': 'str'},
        'protocolKind': {'type': 'string', 'required': True, 'python': 'str'},
        'setupTreatment': {'type': 'string', 'required': True, 'python': 'str'},
        'stoppingRule': {'type': 'string', 'required': True, 'python': 'str'},
        'strata': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'targetPairs': {'type': 'integer', 'required': True, 'python': 'int'},
        'uncertaintyMethod': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'CacheReuseReceipt': {
        'boundInputs': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'cacheKeyDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'claimType': {'type': 'string', 'required': True, 'python': 'str'},
        'freshnessPolicyId': {'type': 'id', 'required': True, 'python': 'str'},
        'receiptId': {'type': 'id', 'required': True, 'python': 'str'},
        'refusedReason': {'type': 'string', 'required': False, 'python': 'str'},
        'reused': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'Capability': {
        'inputContract': {'type': {'ref': 'Contract'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'intent': {'type': 'text', 'required': True, 'python': 'str'},
        'name': {'type': 'string', 'required': True, 'python': 'str'},
        'outputContract': {'type': {'ref': 'Contract'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'sideEffectClass': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'Checkpoint': {
        'acceptedDecisions': {'type': {'list': {'ref': 'Decision'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'closureReceipt': {'type': {'ref': 'ClosureReceipt'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'committed': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'lastSealedEventDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'lastSealedEventSeq': {'type': 'integer', 'required': True, 'python': 'int'},
        'nextLegalActions': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'openOperations': {'type': {'list': {'ref': 'OpenOperation'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'outcome': {'type': {'ref': 'Outcome'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'recoveryPolicyRef': {'type': 'string', 'required': True, 'python': 'str'},
        'snapshot': {'type': {'ref': 'StateSnapshot'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'unresolvedClaims': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
    },
    'ChunkAggregate': {
        'aggregateId': {'type': 'id', 'required': True, 'python': 'str'},
        'chunkRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'consistencyGuarantee': {'type': 'string', 'required': True, 'python': 'str'},
        'consistencyWitnesses': {'type': {'list': {'object': {'witnessKind': {'type': 'string', 'required': True}, 'expected': {'type': 'json', 'required': False}, 'observed': {'type': 'json', 'required': False}, 'agrees': {'type': 'boolean', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'rejectionReasons': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'requiredScope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'status': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
    },
    'ChunkEnvelope': {
        'attempt': {'type': 'integer', 'required': True, 'python': 'int'},
        'candidateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'chunkId': {'type': 'id', 'required': True, 'python': 'str'},
        'completed': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'deadlineMs': {'type': 'duration_ms', 'required': True, 'python': 'int'},
        'elapsedMs': {'type': 'duration_ms', 'required': True, 'python': 'int'},
        'engineCount': {'type': 'integer', 'required': False, 'python': 'int'},
        'mapIdentity': {'type': 'string', 'required': True, 'python': 'str'},
        'memberIds': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'policyDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'processCreationDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'rangeEnd': {'type': 'string', 'required': True, 'python': 'str'},
        'rangeStart': {'type': 'string', 'required': True, 'python': 'str'},
        'runId': {'type': 'id', 'required': True, 'python': 'str'},
        'serializedRowCount': {'type': 'integer', 'required': False, 'python': 'int'},
        'snapshotEpoch': {'type': 'string', 'required': True, 'python': 'str'},
        'sourceDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'timedOut': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'Claim': {
        'claimId': {'type': 'id', 'required': True, 'python': 'str'},
        'freshnessPolicyRef': {'type': {'ref': 'FreshnessPolicy'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'lifecycle': {'type': {'enum': 'ClaimLifecycle'}, 'required': True, 'python': 'ClaimLifecycle'},
        'mandatory': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'producerAssertion': {'type': {'ref': 'ProducerAssertion'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'proposition': {'type': {'ref': 'Proposition'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'recordType': {'type': 'string', 'required': False, 'python': 'str'},
        'requiredEvidence': {'type': {'list': {'ref': 'EvidenceRequirement'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'sufficiency': {'type': {'ref': 'EvidenceSufficiencyReceipt'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'ClaimBundle': {
        'bundleId': {'type': 'id', 'required': True, 'python': 'str'},
        'candidateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'lifecycle': {'type': {'enum': 'BundleLifecycle'}, 'required': True, 'python': 'BundleLifecycle'},
        'memberIndex': {'type': {'list': {'object': {'claimId': {'type': 'id', 'required': True}, 'revisionDigest': {'type': 'digest', 'required': True}, 'mandatory': {'type': 'boolean', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'resolvedStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'sealedAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
    },
    'ClaimBundleDelta': {
        'changedRevisions': {'type': {'list': {'object': {'claimId': {'type': 'id', 'required': True}, 'revisionDigest': {'type': 'digest', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'deltaId': {'type': 'id', 'required': True, 'python': 'str'},
        'depth': {'type': 'integer', 'required': True, 'python': 'int'},
        'newEvidenceRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'parentBundleDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'removedClaimIds': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
        'resolvedStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
    },
    'ClaimRevision': {
        'changeReason': {'type': 'string', 'required': True, 'python': 'str'},
        'claim': {'type': {'ref': 'Claim'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'claimId': {'type': 'id', 'required': True, 'python': 'str'},
        'parentRevisionDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'revisionNumber': {'type': 'integer', 'required': True, 'python': 'int'},
    },
    'ClosureReceipt': {
        'closureKind': {'type': {'enum': 'ClosureKind'}, 'required': True, 'python': 'ClosureKind'},
        'complete': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'enumeratedMembers': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'expectedCount': {'type': 'integer', 'required': False, 'python': 'int'},
        'incompleteReason': {'type': 'string', 'required': False, 'python': 'str'},
        'observedCount': {'type': 'integer', 'required': True, 'python': 'int'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'witnessRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
    },
    'ConflictSet': {
        'claimIds': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
        'conflictId': {'type': 'id', 'required': True, 'python': 'str'},
        'conflictingEvidence': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'description': {'type': 'text', 'required': True, 'python': 'str'},
        'disposition': {'type': {'enum': 'ConflictDisposition'}, 'required': True, 'python': 'ConflictDisposition'},
        'invalidatesDownstream': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
    },
    'Contract': {
        'contractVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'freshnessPolicyRef': {'type': {'ref': 'FreshnessPolicy'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'name': {'type': 'string', 'required': True, 'python': 'str'},
        'predicates': {'type': {'list': {'ref': 'Predicate'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'requiredAuthorityClasses': {'type': {'list': {'enum': 'AuthorityClass'}}, 'required': False, 'python': 'list[AuthorityClass]'},
        'requiredEvidence': {'type': {'list': {'ref': 'EvidenceRequirement'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'scope': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'tolerances': {'type': {'map': 'decimal'}, 'required': False, 'python': 'dict[str, str]'},
        'units': {'type': {'map': 'string'}, 'required': False, 'python': 'dict[str, str]'},
    },
    'Decision': {
        'citedInputs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'decisionKind': {'type': 'string', 'required': True, 'python': 'str'},
        'disposition': {'type': 'string', 'required': True, 'python': 'str'},
        'issuedByRole': {'type': 'string', 'required': True, 'python': 'str'},
        'policyRef': {'type': 'string', 'required': False, 'python': 'str'},
        'rationale': {'type': 'text', 'required': True, 'python': 'str'},
    },
    'EfficiencyClaim': {
        'cohort': {'type': {'list': {'ref': 'BenchmarkPair'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'equivalenceContract': {'type': {'ref': 'EquivalenceContract'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'evaluatorResultRef': {'type': 'digest', 'required': False, 'python': 'str'},
        'evaluatorVerdict': {'type': {'enum': 'Verdict'}, 'required': False, 'python': 'Verdict'},
        'expectedClaim': {'type': 'text', 'required': True, 'python': 'str'},
        'metricId': {'type': 'string', 'required': True, 'python': 'str'},
        'producerNotes': {'type': 'text', 'required': False, 'python': 'str'},
        'proposedValue': {'type': 'decimal', 'required': False, 'python': 'str'},
    },
    'EntailmentReceipt': {
        'authorityClasses': {'type': {'list': {'enum': 'AuthorityClass'}}, 'required': True, 'python': 'list[AuthorityClass]'},
        'depth': {'type': 'integer', 'required': True, 'python': 'int'},
        'implementationDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'intendedUse': {'type': 'string', 'required': True, 'python': 'str'},
        'metamodelDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'receiptId': {'type': 'id', 'required': True, 'python': 'str'},
        'relation': {'type': 'string', 'required': True, 'python': 'str'},
        'ruleDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'sourceGraphDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'witnessPath': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
    },
    'EnvironmentIdentity': {
        'adapterEndpointConfigDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'hostId': {'type': 'string', 'required': True, 'python': 'str'},
        'interpreter': {'type': 'string', 'required': True, 'python': 'str'},
        'interpreterVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'moduleClosureDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'platform': {'type': 'string', 'required': True, 'python': 'str'},
        'processCreation': {'type': {'object': {'pid': {'type': 'integer', 'required': False}, 'createTime': {'type': 'string', 'required': False}, 'executablePath': {'type': 'string', 'required': False}, 'executableDigest': {'type': 'digest', 'required': False}, 'commandLineDigest': {'type': 'digest', 'required': False}}}, 'required': False, 'python': 'dict[str, Any]'},
        'providerBuild': {'type': {'map': 'string'}, 'required': False, 'python': 'dict[str, str]'},
        'unknownFields': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
    },
    'EquivalenceContract': {
        'cacheStratum': {'type': 'string', 'required': True, 'python': 'str'},
        'escalationPermitted': {'type': 'boolean', 'required': False, 'python': 'bool'},
        'evidenceStandard': {'type': {'list': {'ref': 'EvidenceRequirement'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'failureRecoveryPolicy': {'type': 'string', 'required': True, 'python': 'str'},
        'frozen': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'heldConstant': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'invalidatingDifferences': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'minimumMatchedPairs': {'type': 'integer', 'required': True, 'python': 'int'},
        'name': {'type': 'string', 'required': True, 'python': 'str'},
        'normalizationContract': {'type': 'string', 'required': False, 'python': 'str'},
        'permittedDifferences': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'qualityThresholds': {'type': {'list': {'ref': 'Predicate'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'requiredArtifactKinds': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'tokenAccountingBasis': {'type': 'string', 'required': True, 'python': 'str'},
        'verificationCostFields': {'type': {'list': 'string'}, 'required': False, 'python': 'list[str]'},
        'weightingPolicyRef': {'type': {'ref': 'WorkUnitPolicy'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'Evidence': {
        'admissibility': {'type': {'enum': 'EvidenceAdmissibility'}, 'required': True, 'python': 'EvidenceAdmissibility'},
        'contentDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'evidenceKind': {'type': 'string', 'required': True, 'python': 'str'},
        'method': {'type': 'text', 'required': True, 'python': 'str'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'subject': {'type': 'string', 'required': True, 'python': 'str'},
        'supportsClaimTypes': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'validFrom': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'validUntil': {'type': 'timestamp', 'required': False, 'python': 'str'},
    },
    'EvidenceRequirement': {
        'evidenceKind': {'type': 'string', 'required': True, 'python': 'str'},
        'freshnessSeconds': {'type': 'integer', 'required': False, 'python': 'int'},
        'mandatory': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'minimumAuthorityClasses': {'type': {'list': {'enum': 'AuthorityClass'}}, 'required': True, 'python': 'list[AuthorityClass]'},
        'requiredObservationChannels': {'type': {'list': {'enum': 'ObservationChannel'}}, 'required': False, 'python': 'list[ObservationChannel]'},
        'requirementId': {'type': 'id', 'required': True, 'python': 'str'},
        'syntheticAcceptable': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'EvidenceSufficiencyReceipt': {
        'closed': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'mandatoryApplicable': {'type': 'integer', 'required': True, 'python': 'int'},
        'mandatorySatisfied': {'type': 'integer', 'required': True, 'python': 'int'},
        'requirementResults': {'type': {'list': {'object': {'requirementId': {'type': 'id', 'required': True}, 'satisfied': {'type': 'boolean', 'required': True}, 'mandatory': {'type': 'boolean', 'required': True}, 'applicable': {'type': 'boolean', 'required': True}, 'reason': {'type': 'string', 'required': True}, 'evidenceRefs': {'type': {'list': 'digest'}, 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
    },
    'ExecutionEvent': {
        'correctsEventId': {'type': 'id', 'required': False, 'python': 'str'},
        'eventId': {'type': 'id', 'required': True, 'python': 'str'},
        'eventType': {'type': 'string', 'required': True, 'python': 'str'},
        'eventTypeVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'idempotencyKey': {'type': 'string', 'required': True, 'python': 'str'},
        'logicalSubject': {'type': 'string', 'required': True, 'python': 'str'},
        'monotonicClockDomain': {'type': 'string', 'required': False, 'python': 'str'},
        'monotonicNs': {'type': 'integer', 'required': False, 'python': 'int'},
        'payload': {'type': 'json', 'required': False, 'python': 'Any'},
        'payloadDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'priorEventDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'replayPolicy': {'type': 'string', 'required': True, 'python': 'str'},
        'sequence': {'type': 'integer', 'required': True, 'python': 'int'},
        'wallClock': {'type': 'timestamp', 'required': True, 'python': 'str'},
    },
    'ExecutionPlan': {
        'frozen': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'limits': {'type': {'map': 'json'}, 'required': False, 'python': 'dict[str, Any]'},
        'nodes': {'type': {'list': {'object': {'nodeId': {'type': 'id', 'required': True}, 'workItem': {'type': {'ref': 'WorkItem'}, 'required': True}, 'mandatory': {'type': 'boolean', 'required': True}, 'dependsOn': {'type': {'list': 'id'}, 'required': False}, 'selectedImplementation': {'type': {'ref': 'Implementation'}, 'required': False}, 'blocked': {'type': 'boolean', 'required': True}, 'blockedReason': {'type': 'string', 'required': False}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'outcome': {'type': {'ref': 'Outcome'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'selectionReceipts': {'type': {'list': {'ref': 'SelectionReceipt'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
    },
    'ExecutionTrace': {
        'actualActor': {'type': 'string', 'required': True, 'python': 'str'},
        'attempt': {'type': 'integer', 'required': True, 'python': 'int'},
        'authorizationReceiptRef': {'type': 'digest', 'required': False, 'python': 'str'},
        'capability': {'type': {'ref': 'Capability'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'consumedArtifacts': {'type': {'list': {'ref': 'ArtifactVersion'}}, 'required': False, 'python': 'list[str | dict[str, Any]]'},
        'environmentBinding': {'type': {'ref': 'EnvironmentIdentity'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'events': {'type': {'list': {'ref': 'ExecutionEvent'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'implementation': {'type': {'ref': 'Implementation'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'issuer': {'type': 'string', 'required': True, 'python': 'str'},
        'mutationScopeDeclared': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'parentTrace': {'type': {'ref': 'ExecutionTrace'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'plan': {'type': {'ref': 'ExecutionPlan'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'producedArtifacts': {'type': {'list': {'ref': 'ArtifactVersion'}}, 'required': False, 'python': 'list[str | dict[str, Any]]'},
        'resourceUsage': {'type': {'list': {'ref': 'ResourceUsage'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'runId': {'type': 'id', 'required': True, 'python': 'str'},
        'spans': {'type': {'list': {'ref': 'Span'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'terminalStatus': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
        'workItem': {'type': {'ref': 'WorkItem'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'FailureMode': {
        'code': {'type': 'string', 'required': True, 'python': 'str'},
        'description': {'type': 'text', 'required': True, 'python': 'str'},
        'domain': {'type': 'string', 'required': True, 'python': 'str'},
        'mapsToStatus': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
        'severity': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'FreshnessPolicy': {
        'alwaysFreshDomains': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'claimTypeGlob': {'type': 'string', 'required': True, 'python': 'str'},
        'maxAgeSeconds': {'type': 'integer', 'required': False, 'python': 'int'},
        'policyId': {'type': 'id', 'required': True, 'python': 'str'},
        'reusableWhileUnchanged': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
    },
    'Gate': {
        'authority': {'type': 'string', 'required': True, 'python': 'str'},
        'evaluatesAgainst': {'type': {'list': {'ref': 'Contract'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'independenceRequired': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'name': {'type': 'string', 'required': True, 'python': 'str'},
        'requiredPredicateIds': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
    },
    'GateResult': {
        'candidateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'contractDigests': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'evidenceClosure': {'type': {'ref': 'ClosureReceipt'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'gate': {'type': {'ref': 'Gate'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'independentlyEvaluated': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'notRunDependency': {'type': 'string', 'required': False, 'python': 'str'},
        'predicateResults': {'type': {'list': {'object': {'predicateId': {'type': 'id', 'required': True}, 'status': {'type': {'enum': 'Status'}, 'required': True}, 'expected': {'type': 'json', 'required': False}, 'observed': {'type': 'json', 'required': False}, 'reason': {'type': 'string', 'required': True}, 'evidenceRefs': {'type': {'list': 'digest'}, 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'status': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
    },
    'Handoff': {
        'checkpoint': {'type': {'ref': 'Checkpoint'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'fromActor': {'type': 'string', 'required': True, 'python': 'str'},
        'referencedEvidence': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'toActor': {'type': 'string', 'required': True, 'python': 'str'},
        'transferredFacts': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
    },
    'Implementation': {
        'authorizedScope': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'failureModes': {'type': {'list': 'string'}, 'required': False, 'python': 'list[str]'},
        'inputSchemaDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'outputSchemaDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'providerName': {'type': 'string', 'required': True, 'python': 'str'},
        'providerVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'qualification': {'type': {'enum': 'Qualification'}, 'required': True, 'python': 'Qualification'},
        'qualificationReceipt': {'type': {'ref': 'QualificationReceipt'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'realizes': {'type': {'list': {'ref': 'Capability'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'resourceProfile': {'type': {'map': 'json'}, 'required': False, 'python': 'dict[str, Any]'},
    },
    'Measurement': {
        'admissibility': {'type': {'enum': 'EvidenceAdmissibility'}, 'required': True, 'python': 'EvidenceAdmissibility'},
        'availability': {'type': {'enum': 'MetricAvailability'}, 'required': True, 'python': 'MetricAvailability'},
        'denominator': {'type': 'decimal', 'required': False, 'python': 'str'},
        'formulaVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'inputRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'metricId': {'type': 'string', 'required': True, 'python': 'str'},
        'numerator': {'type': 'decimal', 'required': False, 'python': 'str'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'unavailableReason': {'type': 'string', 'required': False, 'python': 'str'},
        'uncertainty': {'type': 'decimal', 'required': False, 'python': 'str'},
        'unit': {'type': 'string', 'required': True, 'python': 'str'},
        'value': {'type': 'decimal', 'required': False, 'python': 'str'},
    },
    'MutationIntent': {
        'declaredEffects': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'intentId': {'type': 'id', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'preStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'targetScope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'MutationLedgerEntry': {
        'effectDescription': {'type': 'text', 'required': True, 'python': 'str'},
        'entryId': {'type': 'id', 'required': True, 'python': 'str'},
        'intentId': {'type': 'id', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'ownership': {'type': {'ref': 'OwnershipAssertion'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'postStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'preStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'priorEntryDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'readbackRef': {'type': 'digest', 'required': False, 'python': 'str'},
        'sequence': {'type': 'integer', 'required': True, 'python': 'int'},
        'transactionId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'MutationSetClosureReceipt': {
        'discrepancies': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'intendedEffects': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'ledgeredEffects': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'readbackConfirmedEffects': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'rollbackSet': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'setsEqual': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'Observation': {
        'channel': {'type': {'enum': 'ObservationChannel'}, 'required': True, 'python': 'ObservationChannel'},
        'epoch': {'type': 'string', 'required': False, 'python': 'str'},
        'errorClass': {'type': 'string', 'required': False, 'python': 'str'},
        'observationId': {'type': 'id', 'required': True, 'python': 'str'},
        'observedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'partial': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'rawDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'subject': {'type': 'string', 'required': True, 'python': 'str'},
        'value': {'type': 'json', 'required': False, 'python': 'Any'},
    },
    'OpenOperation': {
        'capability': {'type': {'ref': 'Capability'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'disposition': {'type': 'string', 'required': False, 'python': 'str'},
        'idempotencyKey': {'type': 'string', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'receiptObserved': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'reconciliationProbe': {'type': 'string', 'required': False, 'python': 'str'},
        'reconciliationRequired': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'sideEffectPossible': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'Outcome': {
        'acceptanceCriteria': {'type': {'list': {'ref': 'Contract'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'lifecycle': {'type': {'enum': 'LifecycleState'}, 'required': True, 'python': 'LifecycleState'},
        'requestedResult': {'type': 'text', 'required': True, 'python': 'str'},
        'requiredArtifactKinds': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'requiredEvidenceKinds': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'subjectUniverse': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'title': {'type': 'string', 'required': True, 'python': 'str'},
        'workUnitPolicyRef': {'type': {'ref': 'WorkUnitPolicy'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'OwnershipAssertion': {
        'directness': {'type': {'enum': 'OperationalOwnership'}, 'required': True, 'python': 'OperationalOwnership'},
        'ownerRole': {'type': 'string', 'required': True, 'python': 'str'},
        'subject': {'type': 'string', 'required': True, 'python': 'str'},
        'transactionId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'Predicate': {
        'expected': {'type': 'json', 'required': False, 'python': 'Any'},
        'mandatory': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'operator': {'type': 'string', 'required': True, 'python': 'str'},
        'predicateId': {'type': 'id', 'required': True, 'python': 'str'},
        'subjectPath': {'type': 'string', 'required': True, 'python': 'str'},
        'tolerance': {'type': 'decimal', 'required': False, 'python': 'str'},
        'unit': {'type': 'string', 'required': False, 'python': 'str'},
    },
    'ProducerAssertion': {
        'evidenceRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'note': {'type': 'text', 'required': False, 'python': 'str'},
        'observedValue': {'type': 'json', 'required': False, 'python': 'Any'},
        'producerRole': {'type': 'string', 'required': True, 'python': 'str'},
        'producerStatus': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
        'proposition': {'type': {'ref': 'Proposition'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'PromotionDecision': {
        'actuatorRole': {'type': 'string', 'required': False, 'python': 'str'},
        'auditResultDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'candidateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'humanApprovalRefs': {'type': {'list': 'digest'}, 'required': True, 'python': 'list[str]'},
        'issuerRole': {'type': 'string', 'required': True, 'python': 'str'},
        'policyDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'reasons': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'state': {'type': {'enum': 'PromotionState'}, 'required': True, 'python': 'PromotionState'},
    },
    'Proposition': {
        'claimType': {'type': 'string', 'required': True, 'python': 'str'},
        'expectedValue': {'type': 'json', 'required': False, 'python': 'Any'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'statement': {'type': 'text', 'required': True, 'python': 'str'},
        'subject': {'type': 'string', 'required': True, 'python': 'str'},
        'unit': {'type': 'string', 'required': False, 'python': 'str'},
    },
    'Provenance': {
        'actor': {'type': 'string', 'required': True, 'python': 'str'},
        'authorityClass': {'type': {'enum': 'AuthorityClass'}, 'required': True, 'python': 'AuthorityClass'},
        'observationChannel': {'type': {'enum': 'ObservationChannel'}, 'required': True, 'python': 'ObservationChannel'},
        'operationalOwnership': {'type': {'enum': 'OperationalOwnership'}, 'required': True, 'python': 'OperationalOwnership'},
        'origin': {'type': {'enum': 'Origin'}, 'required': True, 'python': 'Origin'},
        'productionMethod': {'type': {'enum': 'ProductionMethod'}, 'required': True, 'python': 'ProductionMethod'},
        'sourceRefs': {'type': {'list': 'digest'}, 'required': False, 'python': 'list[str]'},
        'syntheticFixture': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'validitySnapshot': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'verificationStatus': {'type': {'enum': 'VerificationStatus'}, 'required': True, 'python': 'VerificationStatus'},
    },
    'ProviderReadback': {
        'channel': {'type': {'enum': 'ObservationChannel'}, 'required': True, 'python': 'ObservationChannel'},
        'matchesExpectedPostState': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'observedStateDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'readbackId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'ProviderSession': {
        'accountingVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'expiresAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'openedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'providerName': {'type': 'string', 'required': True, 'python': 'str'},
        'revalidateOnResume': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'sessionId': {'type': 'id', 'required': True, 'python': 'str'},
        'tokenizerId': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'QualificationReceipt': {
        'buildIdentityDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'candidateDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'configurationDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'dependencies': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'limits': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'observedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'probeScope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'providerName': {'type': 'string', 'required': True, 'python': 'str'},
        'providerVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'receiptId': {'type': 'id', 'required': True, 'python': 'str'},
        'result': {'type': {'enum': 'Qualification'}, 'required': True, 'python': 'Qualification'},
        'subjectKind': {'type': 'string', 'required': True, 'python': 'str'},
        'syntheticFixture': {'type': 'boolean', 'required': True, 'python': 'bool'},
    },
    'ReleaseManifest': {
        'acceptanceByDimension': {'type': {'list': {'object': {'dimension': {'type': {'enum': 'AcceptanceDimension'}, 'required': True}, 'status': {'type': {'enum': 'Status'}, 'required': True}, 'evidenceRefs': {'type': {'list': 'digest'}, 'required': True}, 'reason': {'type': 'string', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'auditResultDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'blockers': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'dependencyLockDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'knownGaps': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'liveUrl': {'type': 'uri', 'required': False, 'python': 'str'},
        'memberDigests': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'payloadDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'product': {'type': 'string', 'required': True, 'python': 'str'},
        'releaseUrl': {'type': 'uri', 'required': False, 'python': 'str'},
        'repositoryUrl': {'type': 'uri', 'required': False, 'python': 'str'},
        'schemaManifestDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'version': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'ResourceUsage': {
        'accountingRule': {'type': {'enum': 'AccountingRule'}, 'required': True, 'python': 'AccountingRule'},
        'basis': {'type': {'enum': 'MeasurementBasis'}, 'required': True, 'python': 'MeasurementBasis'},
        'belowResolution': {'type': 'boolean', 'required': False, 'python': 'bool'},
        'clockResolutionNs': {'type': 'integer', 'required': False, 'python': 'int'},
        'dedupKey': {'type': 'string', 'required': True, 'python': 'str'},
        'kind': {'type': {'enum': 'ResourceKind'}, 'required': True, 'python': 'ResourceKind'},
        'parentKind': {'type': {'enum': 'ResourceKind'}, 'required': False, 'python': 'ResourceKind'},
        'providerAccountingVersion': {'type': 'string', 'required': False, 'python': 'str'},
        'providerName': {'type': 'string', 'required': False, 'python': 'str'},
        'providerResponseId': {'type': 'string', 'required': False, 'python': 'str'},
        'scope': {'type': {'ref': 'Scope'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'tokenizerId': {'type': 'string', 'required': False, 'python': 'str'},
        'uncertainty': {'type': 'decimal', 'required': False, 'python': 'str'},
        'unit': {'type': 'string', 'required': True, 'python': 'str'},
        'unknownReason': {'type': 'string', 'required': False, 'python': 'str'},
        'value': {'type': 'decimal', 'required': False, 'python': 'str'},
    },
    'ResourceUsageLedger': {
        'accountingDomains': {'type': 'json', 'required': True, 'python': 'Any'},
        'consumes': {'type': 'json', 'required': True, 'python': 'Any'},
        'measurements': {'type': {'list': {'ref': 'ResourceUsage'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'recordType': {'type': 'string', 'required': True, 'python': 'str'},
        'runId': {'type': 'id', 'required': True, 'python': 'str'},
        'schemaVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'subsetReconciliation': {'type': 'json', 'required': True, 'python': 'Any'},
        'synthetic': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'totals': {'type': 'json', 'required': True, 'python': 'Any'},
    },
    'Retry': {
        'attempt': {'type': 'integer', 'required': True, 'python': 'int'},
        'ofInvocationId': {'type': 'id', 'required': True, 'python': 'str'},
        'permitted': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'reasonClass': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'ReviewView': {
        'accessibilityResults': {'type': {'list': {'object': {'checkId': {'type': 'id', 'required': True}, 'status': {'type': {'enum': 'Status'}, 'required': True}, 'reason': {'type': 'string', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'lifecycle': {'type': {'enum': 'ViewLifecycle'}, 'required': True, 'python': 'ViewLifecycle'},
        'profileId': {'type': 'string', 'required': True, 'python': 'str'},
        'rasterProfileDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'rendererId': {'type': 'string', 'required': True, 'python': 'str'},
        'rendererVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'semanticInputDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'sourceAuditDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'sourceCheckpointDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'unavailableReason': {'type': 'string', 'required': False, 'python': 'str'},
        'viewId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'RollbackAction': {
        'actionId': {'type': 'id', 'required': True, 'python': 'str'},
        'authorizedByRole': {'type': 'string', 'required': True, 'python': 'str'},
        'performed': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'resultDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'targetEntryId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'Scope': {
        'enumerationComplete': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'epoch': {'type': 'string', 'required': False, 'python': 'str'},
        'expectedMemberCount': {'type': 'integer', 'required': False, 'python': 'int'},
        'scopeKind': {'type': 'string', 'required': True, 'python': 'str'},
        'selector': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'SelectionReceipt': {
        'blocked': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'candidateUniverse': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
        'committed': {'type': 'id', 'required': False, 'python': 'str'},
        'hardPredicates': {'type': {'list': {'ref': 'Predicate'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'nodeId': {'type': 'id', 'required': True, 'python': 'str'},
        'prngSeed': {'type': 'string', 'required': False, 'python': 'str'},
        'prunedCandidates': {'type': {'list': {'object': {'candidateId': {'type': 'id', 'required': True}, 'predicateId': {'type': 'id', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'quantization': {'type': 'integer', 'required': True, 'python': 'int'},
        'rankedCandidates': {'type': {'list': {'object': {'candidateId': {'type': 'id', 'required': True}, 'score': {'type': 'decimal', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'terminalDecisionByCandidate': {'type': {'map': 'string'}, 'required': True, 'python': 'dict[str, str]'},
        'tieBreak': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'Span': {
        'actorId': {'type': 'string', 'required': True, 'python': 'str'},
        'allocationUnknown': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'belowResolution': {'type': 'boolean', 'required': False, 'python': 'bool'},
        'clockDomain': {'type': 'string', 'required': True, 'python': 'str'},
        'clockResolutionNs': {'type': 'integer', 'required': False, 'python': 'int'},
        'endNs': {'type': 'integer', 'required': True, 'python': 'int'},
        'leaf': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'parentSpanId': {'type': 'id', 'required': False, 'python': 'str'},
        'purpose': {'type': {'enum': 'ExecutionPurpose'}, 'required': True, 'python': 'ExecutionPurpose'},
        'spanId': {'type': 'id', 'required': True, 'python': 'str'},
        'startNs': {'type': 'integer', 'required': True, 'python': 'int'},
        'state': {'type': {'enum': 'ExecutionState'}, 'required': True, 'python': 'ExecutionState'},
        'traceRunId': {'type': 'id', 'required': True, 'python': 'str'},
        'uncertainty': {'type': 'decimal', 'required': False, 'python': 'str'},
    },
    'StateSnapshot': {
        'admittedSourceVersions': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'artifactRefs': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'completeness': {'type': {'enum': 'MetricAvailability'}, 'required': True, 'python': 'MetricAvailability'},
        'contractDigests': {'type': {'map': 'digest'}, 'required': True, 'python': 'dict[str, str]'},
        'environmentBinding': {'type': {'ref': 'EnvironmentIdentity'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'ephemeralBindings': {'type': {'list': {'object': {'bindingKind': {'type': 'string', 'required': True}, 'recordedValue': {'type': 'json', 'required': True}, 'carriesAuthority': {'type': 'boolean', 'required': True, 'doc': 'Always false when persisted: a saved PID, editor connection, expired authorization or prior visibility observation is a historical note, not continuing authority.'}, 'refreshRequiredOnResume': {'type': 'boolean', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'implementationVersions': {'type': {'map': 'string'}, 'required': True, 'python': 'dict[str, str]'},
        'planDigest': {'type': 'digest', 'required': True, 'python': 'str'},
        'requiredFacts': {'type': {'list': {'object': {'factId': {'type': 'id', 'required': True}, 'present': {'type': 'boolean', 'required': True}, 'value': {'type': 'json', 'required': False}, 'provenance': {'type': {'ref': 'Provenance'}, 'required': False}, 'missingReason': {'type': 'string', 'required': False}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
    },
    'ToolInvocation': {
        'completedAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'errorClass': {'type': 'string', 'required': False, 'python': 'str'},
        'idempotencyKey': {'type': 'string', 'required': True, 'python': 'str'},
        'implementation': {'type': {'ref': 'Implementation'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'invocationId': {'type': 'id', 'required': True, 'python': 'str'},
        'resultDigest': {'type': 'digest', 'required': False, 'python': 'str'},
        'startedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'terminalStatus': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
    },
    'Transaction': {
        'closedAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'committed': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'openedAt': {'type': 'timestamp', 'required': True, 'python': 'str'},
        'operationId': {'type': 'id', 'required': True, 'python': 'str'},
        'transactionId': {'type': 'id', 'required': True, 'python': 'str'},
    },
    'Verification': {
        'claimId': {'type': 'id', 'required': False, 'python': 'str'},
        'commonModeDependencies': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'independenceLevel': {'type': 'string', 'required': True, 'python': 'str'},
        'mode': {'type': 'string', 'required': True, 'python': 'str'},
        'producerStatus': {'type': 'json', 'required': False, 'python': 'Any'},
        'proposition': {'type': {'ref': 'Proposition'}, 'required': False, 'python': 'str | dict[str, Any]'},
        'reason': {'type': 'string', 'required': True, 'python': 'str'},
        'recomputedValue': {'type': 'json', 'required': False, 'python': 'Any'},
        'recordType': {'type': 'string', 'required': False, 'python': 'str'},
        'status': {'type': {'enum': 'Status'}, 'required': True, 'python': 'Status'},
    },
    'VerificationCostSet': {
        'auditorTokens': {'type': {'ref': 'ResourceUsage'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'managerTokens': {'type': {'ref': 'ResourceUsage'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'recoveryTokens': {'type': {'ref': 'ResourceUsage'}, 'required': True, 'python': 'str | dict[str, Any]'},
    },
    'WorkItem': {
        'accountingId': {'type': 'id', 'required': True, 'python': 'str'},
        'accountingPartition': {'type': 'string', 'required': True, 'python': 'str'},
        'contracts': {'type': {'list': {'ref': 'Contract'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'lifecycle': {'type': {'enum': 'LifecycleState'}, 'required': True, 'python': 'LifecycleState'},
        'limits': {'type': {'map': 'json'}, 'required': False, 'python': 'dict[str, Any]'},
        'parentOutcome': {'type': {'ref': 'Outcome'}, 'required': True, 'python': 'str | dict[str, Any]'},
        'permittedSideEffects': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'prerequisites': {'type': {'list': {'ref': 'WorkItem'}}, 'required': False, 'python': 'list[str | dict[str, Any]]'},
        'requiredCapabilities': {'type': {'list': {'ref': 'Capability'}}, 'required': True, 'python': 'list[str | dict[str, Any]]'},
        'title': {'type': 'string', 'required': True, 'python': 'str'},
    },
    'WorkPacket': {
        'finalAuditAuthority': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'frozenInterfaceVersion': {'type': 'string', 'required': True, 'python': 'str'},
        'ownedPaths': {'type': {'list': 'string'}, 'required': True, 'python': 'list[str]'},
        'ownerRole': {'type': 'string', 'required': True, 'python': 'str'},
        'packetId': {'type': 'id', 'required': True, 'python': 'str'},
        'requirementIds': {'type': {'list': 'id'}, 'required': True, 'python': 'list[str]'},
    },
    'WorkUnitPolicy': {
        'acceptanceUniverse': {'type': {'list': {'object': {'accountingId': {'type': 'id', 'required': True}, 'weight': {'type': 'decimal', 'required': True}, 'requiredGateIds': {'type': {'list': 'id'}, 'required': True}, 'partition': {'type': 'string', 'required': True}, 'partialCreditDefined': {'type': 'boolean', 'required': True}}}}, 'required': True, 'python': 'list[dict[str, Any]]'},
        'frozen': {'type': 'boolean', 'required': True, 'python': 'bool'},
        'frozenAt': {'type': 'timestamp', 'required': False, 'python': 'str'},
        'policyVersion': {'type': 'string', 'required': True, 'python': 'str'},
    },
}

KERNEL_CONCEPTS: tuple[str, ...] = (
    'Artifact',
    'Capability',
    'Checkpoint',
    'Contract',
    'Decision',
    'EfficiencyClaim',
    'EquivalenceContract',
    'Evidence',
    'ExecutionPlan',
    'ExecutionTrace',
    'Gate',
    'Implementation',
    'Outcome',
    'ResourceUsage',
    'StateSnapshot',
    'WorkItem',
)

IDENTITY_ENTITIES: tuple[str, ...] = (
    'AcceptanceReceipt',
    'AcceptedWorkLedgerEntry',
    'AdjudicationReceipt',
    'Artifact',
    'ArtifactVersion',
    'AuditResult',
    'AuthorizedOperation',
    'BenchmarkPair',
    'BenchmarkProtocol',
    'CacheReuseReceipt',
    'Capability',
    'Checkpoint',
    'ChunkAggregate',
    'ChunkEnvelope',
    'Claim',
    'ClaimBundle',
    'ClaimBundleDelta',
    'ClaimRevision',
    'ClosureReceipt',
    'ConflictSet',
    'Contract',
    'Decision',
    'EfficiencyClaim',
    'EntailmentReceipt',
    'EnvironmentIdentity',
    'EquivalenceContract',
    'Evidence',
    'EvidenceSufficiencyReceipt',
    'ExecutionEvent',
    'ExecutionPlan',
    'ExecutionTrace',
    'FailureMode',
    'FreshnessPolicy',
    'Gate',
    'GateResult',
    'Handoff',
    'Implementation',
    'Measurement',
    'MutationIntent',
    'MutationLedgerEntry',
    'MutationSetClosureReceipt',
    'Observation',
    'OpenOperation',
    'Outcome',
    'OwnershipAssertion',
    'ProducerAssertion',
    'PromotionDecision',
    'Proposition',
    'ProviderReadback',
    'ProviderSession',
    'QualificationReceipt',
    'ReleaseManifest',
    'ResourceUsage',
    'Retry',
    'ReviewView',
    'RollbackAction',
    'SelectionReceipt',
    'Span',
    'StateSnapshot',
    'ToolInvocation',
    'Transaction',
    'Verification',
    'WorkItem',
    'WorkPacket',
    'WorkUnitPolicy',
)

ALLOWED_CLOSURES: tuple[tuple[str, str], ...] = (
    ('directPrerequisite', 'dependsOn'),
    ('directlyDerivedFrom', 'derivedFrom'),
    ('directlyPrecedes', 'precedes'),
)
