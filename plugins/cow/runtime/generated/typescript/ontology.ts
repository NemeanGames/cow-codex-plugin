// GENERATED FROM ontology/metamodel.json -- DO NOT EDIT
// semanticModelDigest: sha256:356d05c8e459888cd22779f81e74d9e856a749105e115cca66391806a95aca4a

export const SEMANTIC_MODEL_DIGEST = "sha256:356d05c8e459888cd22779f81e74d9e856a749105e115cca66391806a95aca4a";
export const METAMODEL_VERSION = "2.0.0";

export type AcceptanceDimension =
  | "SOFTWARE_ACCEPTED"
  | "EFFICIENCY_VERIFIED"
  | "DEPLOYMENT_VERIFIED"
  | "LIVE_ADAPTER_QUALIFIED";
export const AcceptanceDimension_VALUES: readonly AcceptanceDimension[] = [
  "SOFTWARE_ACCEPTED",
  "EFFICIENCY_VERIFIED",
  "DEPLOYMENT_VERIFIED",
  "LIVE_ADAPTER_QUALIFIED",
] as const;

export type AccountingRule =
  | "SUBSET_OF_INPUT"
  | "SUBSET_OF_OUTPUT"
  | "DISJOINT_ADDITIVE"
  | "UNSPECIFIED";
export const AccountingRule_VALUES: readonly AccountingRule[] = [
  "SUBSET_OF_INPUT",
  "SUBSET_OF_OUTPUT",
  "DISJOINT_ADDITIVE",
  "UNSPECIFIED",
] as const;

export type AuthorityClass =
  | "AUTHORITATIVE_SOURCE"
  | "DETERMINISTIC_DERIVATION"
  | "PROVIDER_OBSERVATION"
  | "OPERATION_OWNED_RESULT"
  | "HEURISTIC_DECISION"
  | "POLICY_OR_SYNTHETIC_AID"
  | "CALLER_ASSERTION";
export const AuthorityClass_VALUES: readonly AuthorityClass[] = [
  "AUTHORITATIVE_SOURCE",
  "DETERMINISTIC_DERIVATION",
  "PROVIDER_OBSERVATION",
  "OPERATION_OWNED_RESULT",
  "HEURISTIC_DECISION",
  "POLICY_OR_SYNTHETIC_AID",
  "CALLER_ASSERTION",
] as const;

export type BundleLifecycle =
  | "OPEN"
  | "SEALED"
  | "DELTA"
  | "MATERIALIZED"
  | "INVALIDATED";
export const BundleLifecycle_VALUES: readonly BundleLifecycle[] = [
  "OPEN",
  "SEALED",
  "DELTA",
  "MATERIALIZED",
  "INVALIDATED",
] as const;

export type ClaimLifecycle =
  | "DRAFT"
  | "SEALED"
  | "AUDITED"
  | "SUPERSEDED"
  | "REVOKED";
export const ClaimLifecycle_VALUES: readonly ClaimLifecycle[] = [
  "DRAFT",
  "SEALED",
  "AUDITED",
  "SUPERSEDED",
  "REVOKED",
] as const;

export type ClosureKind =
  | "ENUMERATION"
  | "MUTATION_SET"
  | "DEPENDENCY"
  | "EVIDENCE"
  | "ROLLBACK"
  | "STATE";
export const ClosureKind_VALUES: readonly ClosureKind[] = [
  "ENUMERATION",
  "MUTATION_SET",
  "DEPENDENCY",
  "EVIDENCE",
  "ROLLBACK",
  "STATE",
] as const;

export type ConflictDisposition =
  | "UNRESOLVED"
  | "ADJUDICATED_ACCEPT"
  | "ADJUDICATED_REJECT"
  | "ADJUDICATED_SPLIT_SCOPE";
export const ConflictDisposition_VALUES: readonly ConflictDisposition[] = [
  "UNRESOLVED",
  "ADJUDICATED_ACCEPT",
  "ADJUDICATED_REJECT",
  "ADJUDICATED_SPLIT_SCOPE",
] as const;

export type EvidenceAdmissibility =
  | "ADMISSIBLE"
  | "INADMISSIBLE_SCOPE"
  | "INADMISSIBLE_AUTHORITY"
  | "INADMISSIBLE_FRESHNESS"
  | "INADMISSIBLE_INCOMPLETE"
  | "INADMISSIBLE_SYNTHETIC_FOR_LIVE";
export const EvidenceAdmissibility_VALUES: readonly EvidenceAdmissibility[] = [
  "ADMISSIBLE",
  "INADMISSIBLE_SCOPE",
  "INADMISSIBLE_AUTHORITY",
  "INADMISSIBLE_FRESHNESS",
  "INADMISSIBLE_INCOMPLETE",
  "INADMISSIBLE_SYNTHETIC_FOR_LIVE",
] as const;

export type ExecutionPurpose =
  | "PLANNING"
  | "RETRIEVAL"
  | "GENERATION"
  | "VERIFICATION"
  | "AUDIT"
  | "PACKAGING"
  | "RECOVERY_REWORK";
export const ExecutionPurpose_VALUES: readonly ExecutionPurpose[] = [
  "PLANNING",
  "RETRIEVAL",
  "GENERATION",
  "VERIFICATION",
  "AUDIT",
  "PACKAGING",
  "RECOVERY_REWORK",
] as const;

export type ExecutionState =
  | "ACTIVE_EXECUTION"
  | "TOOL_WAIT"
  | "HUMAN_WAIT"
  | "IDLE"
  | "UNKNOWN";
export const ExecutionState_VALUES: readonly ExecutionState[] = [
  "ACTIVE_EXECUTION",
  "TOOL_WAIT",
  "HUMAN_WAIT",
  "IDLE",
  "UNKNOWN",
] as const;

export type LifecycleState =
  | "CREATED"
  | "VALIDATED"
  | "READY"
  | "RUNNING"
  | "CHECKPOINTED"
  | "COMPLETED"
  | "BLOCKED"
  | "FAILED"
  | "ERRORED"
  | "CANCELED";
export const LifecycleState_VALUES: readonly LifecycleState[] = [
  "CREATED",
  "VALIDATED",
  "READY",
  "RUNNING",
  "CHECKPOINTED",
  "COMPLETED",
  "BLOCKED",
  "FAILED",
  "ERRORED",
  "CANCELED",
] as const;

export type MeasurementBasis =
  | "OBSERVED"
  | "ESTIMATED"
  | "UNKNOWN"
  | "NOT_APPLICABLE";
export const MeasurementBasis_VALUES: readonly MeasurementBasis[] = [
  "OBSERVED",
  "ESTIMATED",
  "UNKNOWN",
  "NOT_APPLICABLE",
] as const;

export type MetricAvailability =
  | "AVAILABLE"
  | "UNDEFINED_ZERO_DENOMINATOR"
  | "NOT_APPLICABLE"
  | "INADMISSIBLE_INPUTS"
  | "INSUFFICIENT_EVIDENCE";
export const MetricAvailability_VALUES: readonly MetricAvailability[] = [
  "AVAILABLE",
  "UNDEFINED_ZERO_DENOMINATOR",
  "NOT_APPLICABLE",
  "INADMISSIBLE_INPUTS",
  "INSUFFICIENT_EVIDENCE",
] as const;

export type ObservationChannel =
  | "FILE_BYTES"
  | "PROCESS_API"
  | "PROVIDER_API"
  | "ENGINE_API"
  | "SCREEN_CAPTURE"
  | "USER_REPORT"
  | "LOG_STREAM"
  | "NOT_OBSERVED";
export const ObservationChannel_VALUES: readonly ObservationChannel[] = [
  "FILE_BYTES",
  "PROCESS_API",
  "PROVIDER_API",
  "ENGINE_API",
  "SCREEN_CAPTURE",
  "USER_REPORT",
  "LOG_STREAM",
  "NOT_OBSERVED",
] as const;

export type OperationalOwnership =
  | "DIRECTLY_OWNED"
  | "DELEGATED_WITH_RECEIPT"
  | "OBSERVED_THIRD_PARTY"
  | "NOT_APPLICABLE"
  | "UNKNOWN";
export const OperationalOwnership_VALUES: readonly OperationalOwnership[] = [
  "DIRECTLY_OWNED",
  "DELEGATED_WITH_RECEIPT",
  "OBSERVED_THIRD_PARTY",
  "NOT_APPLICABLE",
  "UNKNOWN",
] as const;

export type Origin =
  | "SOURCE_ARTIFACT"
  | "LIVE_OBSERVATION"
  | "DERIVATION"
  | "POLICY"
  | "HUMAN_INPUT"
  | "SYNTHETIC_FIXTURE";
export const Origin_VALUES: readonly Origin[] = [
  "SOURCE_ARTIFACT",
  "LIVE_OBSERVATION",
  "DERIVATION",
  "POLICY",
  "HUMAN_INPUT",
  "SYNTHETIC_FIXTURE",
] as const;

export type ProductionMethod =
  | "MEASURED"
  | "RECOMPUTED"
  | "REPLAYED"
  | "TRANSCRIBED"
  | "ESTIMATED"
  | "ASSERTED"
  | "GENERATED";
export const ProductionMethod_VALUES: readonly ProductionMethod[] = [
  "MEASURED",
  "RECOMPUTED",
  "REPLAYED",
  "TRANSCRIBED",
  "ESTIMATED",
  "ASSERTED",
  "GENERATED",
] as const;

export type PromotionState =
  | "NOT_EVALUATED"
  | "ELIGIBLE"
  | "INELIGIBLE"
  | "PROMOTED"
  | "WITHHELD";
export const PromotionState_VALUES: readonly PromotionState[] = [
  "NOT_EVALUATED",
  "ELIGIBLE",
  "INELIGIBLE",
  "PROMOTED",
  "WITHHELD",
] as const;

export type Qualification =
  | "QUALIFIED"
  | "PROVISIONAL"
  | "TENTATIVE"
  | "NEGATIVELY_QUALIFIED"
  | "BLOCKED"
  | "NOT_ASSESSED";
export const Qualification_VALUES: readonly Qualification[] = [
  "QUALIFIED",
  "PROVISIONAL",
  "TENTATIVE",
  "NEGATIVELY_QUALIFIED",
  "BLOCKED",
  "NOT_ASSESSED",
] as const;

export type ResourceKind =
  | "VENDOR_INPUT_TOKENS"
  | "VENDOR_OUTPUT_TOKENS"
  | "VENDOR_CACHED_INPUT_TOKENS"
  | "VENDOR_CACHE_READ_INPUT_TOKENS"
  | "VENDOR_CACHE_CREATION_INPUT_TOKENS"
  | "VENDOR_REASONING_OUTPUT_TOKENS"
  | "LOCAL_MODEL_INPUT_TOKENS"
  | "LOCAL_MODEL_OUTPUT_TOKENS"
  | "TOOL_RUNTIME_MS"
  | "RETRY_COUNT"
  | "FAILED_ATTEMPT_COUNT"
  | "METERED_COMPUTE_MS"
  | "MONEY_MINOR_UNITS";
export const ResourceKind_VALUES: readonly ResourceKind[] = [
  "VENDOR_INPUT_TOKENS",
  "VENDOR_OUTPUT_TOKENS",
  "VENDOR_CACHED_INPUT_TOKENS",
  "VENDOR_CACHE_READ_INPUT_TOKENS",
  "VENDOR_CACHE_CREATION_INPUT_TOKENS",
  "VENDOR_REASONING_OUTPUT_TOKENS",
  "LOCAL_MODEL_INPUT_TOKENS",
  "LOCAL_MODEL_OUTPUT_TOKENS",
  "TOOL_RUNTIME_MS",
  "RETRY_COUNT",
  "FAILED_ATTEMPT_COUNT",
  "METERED_COMPUTE_MS",
  "MONEY_MINOR_UNITS",
] as const;

export type ReuseDisposition =
  | "REUSE_UNCHANGED"
  | "WRAP"
  | "EXTEND_WITH_MIGRATION"
  | "REPLACE_WITH_PROVEN_EQUIVALENCE"
  | "REFERENCE_ONLY"
  | "NOT_AVAILABLE";
export const ReuseDisposition_VALUES: readonly ReuseDisposition[] = [
  "REUSE_UNCHANGED",
  "WRAP",
  "EXTEND_WITH_MIGRATION",
  "REPLACE_WITH_PROVEN_EQUIVALENCE",
  "REFERENCE_ONLY",
  "NOT_AVAILABLE",
] as const;

export type Status =
  | "PASS"
  | "FAIL"
  | "UNKNOWN"
  | "ERROR"
  | "NOT_RUN";
export const Status_VALUES: readonly Status[] = [
  "PASS",
  "FAIL",
  "UNKNOWN",
  "ERROR",
  "NOT_RUN",
] as const;

export type Verdict =
  | "APPROVE"
  | "REJECT"
  | "INDETERMINATE";
export const Verdict_VALUES: readonly Verdict[] = [
  "APPROVE",
  "REJECT",
  "INDETERMINATE",
] as const;

export type VerificationStatus =
  | "UNVERIFIED"
  | "PRODUCER_ASSERTED"
  | "INDEPENDENTLY_VERIFIED"
  | "CONTRADICTED"
  | "INADMISSIBLE";
export const VerificationStatus_VALUES: readonly VerificationStatus[] = [
  "UNVERIFIED",
  "PRODUCER_ASSERTED",
  "INDEPENDENTLY_VERIFIED",
  "CONTRADICTED",
  "INADMISSIBLE",
] as const;

export type ViewLifecycle =
  | "WIP_DIAGNOSTIC"
  | "COMMITTED_PROJECTION"
  | "STALE"
  | "UNAVAILABLE";
export const ViewLifecycle_VALUES: readonly ViewLifecycle[] = [
  "WIP_DIAGNOSTIC",
  "COMMITTED_PROJECTION",
  "STALE",
  "UNAVAILABLE",
] as const;

export interface RecordEnvelope {
  createdAt?: string;
  hashProfile: string;
  logicalId: string;
  provenance: string | Provenance;
  recordType: string;
  revisionId: string;
  schemaVersion: string;
  semanticModelDigest: string;
}

/** Credits exactly one accounting identity once. Revocation appends a correction; it never rewrites history. */
export interface AcceptanceReceipt extends RecordEnvelope {
  acceptedAt: string;
  accountingId: string;
  correctsReceiptId?: string;
  firstQualifyingAttempt: boolean;
  partition: string;
  receiptId: string;
  requiredGateResults: Array<string>;
  revocationReason?: string;
  revoked: boolean;
  weight: string;
  workUnitPolicyVersion: string;
  "x-extension"?: Record<string, unknown>;
}

export interface AcceptedWorkLedgerEntry extends RecordEnvelope {
  accountingId: string;
  delta: string;
  measurementWindow: string;
  receiptId: string;
  sequence: number;
  weight: string;
  "x-extension"?: Record<string, unknown>;
}

export interface AdjudicationReceipt extends RecordEnvelope {
  authorizedByRole: string;
  citedEvidence: Array<string>;
  citedPolicy: string;
  conflictId: string;
  disposition: ConflictDisposition;
  rationale: string;
  "x-extension"?: Record<string, unknown>;
}

/** Logical identity. Byte identity lives in ArtifactVersion. */
export interface Artifact extends RecordEnvelope {
  artifactKind: string;
  name: string;
  versions: Array<string | ArtifactVersion>;
  "x-extension"?: Record<string, unknown>;
}

/** Immutable byte-addressed version of an artifact. */
export interface ArtifactVersion extends RecordEnvelope {
  artifact: string | Artifact;
  contentDigest: string;
  derivationReceipt?: string;
  directlyDerivedFrom?: Array<string>;
  mediaType?: string;
  sizeBytes: number;
  "x-extension"?: Record<string, unknown>;
}

/** Produced by the independent auditor package only. Never written by a producer. */
export interface AuditResult extends RecordEnvelope {
  auditId: string;
  auditInputManifestDigest: string;
  auditorImplementationDigest: string;
  auditorRole: string;
  commonModeDependencies: Array<Record<string, string>>;
  disagreedWithProducer: Array<string>;
  frozenBundleDigest: string;
  mandatoryTotals: Record<string, number>;
  resultDigest: string;
  verdict: Verdict;
  verdictRationale: string;
  verifications: Array<string | Verification>;
  "x-extension"?: Record<string, unknown>;
}

export interface AuthorizedOperation extends RecordEnvelope {
  authorizedScope: string | Scope;
  capability: string | Capability;
  expiresAt?: string;
  grantDigest: string;
  grantedByRole: string;
  operationId: string;
  replayGuard: string;
  secretsExcluded: boolean;
  "x-extension"?: Record<string, unknown>;
}

/** One matched baseline/assisted execution pair under a frozen equivalence contract. */
export interface BenchmarkPair extends RecordEnvelope {
  assistedAccepted: boolean;
  assistedTraceRef: string;
  baselineAccepted: boolean;
  baselineTraceRef: string;
  cacheStratum: string;
  contaminationChecks: Array<{ checkId: string; reason: string; status: Status }>;
  equivalenceContractDigest: string;
  exclusionReason?: string;
  includedInCohort: boolean;
  pairId: string;
  receipts?: unknown;
  setupAmortized: boolean;
  verificationCosts?: string | VerificationCostSet;
  "x-extension"?: Record<string, unknown>;
}

/** Pre-registered before a cohort is measured. A pilot is a debugging cohort, never an advertised result. */
export interface BenchmarkProtocol extends RecordEnvelope {
  equivalenceContractDigest: string;
  frozen: boolean;
  minimumPairs: number;
  preRegisteredAt: string;
  protocolId: string;
  protocolKind: string;
  setupTreatment: string;
  stoppingRule: string;
  strata: Array<string>;
  targetPairs: number;
  uncertaintyMethod: string;
  "x-extension"?: Record<string, unknown>;
}

export interface CacheReuseReceipt extends RecordEnvelope {
  boundInputs: Record<string, string>;
  cacheKeyDigest: string;
  claimType: string;
  freshnessPolicyId: string;
  receiptId: string;
  refusedReason?: string;
  reused: boolean;
  "x-extension"?: Record<string, unknown>;
}

/** Stable functional contract independent of vendor or tool names. */
export interface Capability extends RecordEnvelope {
  inputContract: string | Contract;
  intent: string;
  name: string;
  outputContract: string | Contract;
  sideEffectClass: string;
  "x-extension"?: Record<string, unknown>;
}

/** Committed semantic state with closure, recovery policy and exact snapshot references. Never preserves live handles as continuing authority. */
export interface Checkpoint extends RecordEnvelope {
  acceptedDecisions: Array<string | Decision>;
  closureReceipt: string | ClosureReceipt;
  committed: boolean;
  lastSealedEventDigest: string;
  lastSealedEventSeq: number;
  nextLegalActions: Array<string>;
  openOperations: Array<string | OpenOperation>;
  outcome: string | Outcome;
  recoveryPolicyRef: string;
  snapshot: string | StateSnapshot;
  unresolvedClaims: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Rejects gaps, overlap, duplicate ranges, stale or mixed epochs, process changes, candidate changes and partial writes. */
export interface ChunkAggregate extends RecordEnvelope {
  aggregateId: string;
  chunkRefs: Array<string>;
  consistencyGuarantee: string;
  consistencyWitnesses: Array<{ agrees: boolean; expected?: unknown; observed?: unknown; witnessKind: string }>;
  rejectionReasons: Array<string>;
  requiredScope: string | Scope;
  status: Status;
  "x-extension"?: Record<string, unknown>;
}

/** One stable-ID-ordered collection chunk in a single authorized session. */
export interface ChunkEnvelope extends RecordEnvelope {
  attempt: number;
  candidateDigest: string;
  chunkId: string;
  completed: boolean;
  deadlineMs: number;
  elapsedMs: number;
  engineCount?: number;
  mapIdentity: string;
  memberIds: Array<string>;
  policyDigest: string;
  processCreationDigest: string;
  rangeEnd: string;
  rangeStart: string;
  runId: string;
  serializedRowCount?: number;
  snapshotEpoch: string;
  sourceDigest: string;
  timedOut: boolean;
  "x-extension"?: Record<string, unknown>;
}

/** Binds a proposition, bounded scope, expected/observed values, required evidence, authority/freshness and policy. */
export interface Claim extends RecordEnvelope {
  claimId: string;
  freshnessPolicyRef?: string | FreshnessPolicy;
  lifecycle: ClaimLifecycle;
  mandatory: boolean;
  producerAssertion: string | ProducerAssertion;
  proposition: string | Proposition;
  requiredEvidence: Array<string | EvidenceRequirement>;
  sufficiency: string | EvidenceSufficiencyReceipt;
  "x-extension"?: Record<string, unknown>;
}

/** Sealed producer bundle. Immutable member index with a resolved-state digest. */
export interface ClaimBundle extends RecordEnvelope {
  bundleId: string;
  candidateDigest: string;
  lifecycle: BundleLifecycle;
  memberIndex: Array<{ claimId: string; mandatory: boolean; revisionDigest: string }>;
  resolvedStateDigest: string;
  sealedAt?: string;
  "x-extension"?: Record<string, unknown>;
}

/** Changed revisions plus new evidence references. Unchanged evidence is referenced, never recopied. */
export interface ClaimBundleDelta extends RecordEnvelope {
  changedRevisions: Array<{ claimId: string; revisionDigest: string }>;
  deltaId: string;
  depth: number;
  newEvidenceRefs: Array<string>;
  parentBundleDigest: string;
  removedClaimIds: Array<string>;
  resolvedStateDigest: string;
  "x-extension"?: Record<string, unknown>;
}

export interface ClaimRevision extends RecordEnvelope {
  changeReason: string;
  claim: string | Claim;
  claimId: string;
  parentRevisionDigest?: string;
  revisionNumber: number;
  "x-extension"?: Record<string, unknown>;
}

/** Bounded complete enumeration over a declared scope. Empty or failed retrieval never proves absence. */
export interface ClosureReceipt extends RecordEnvelope {
  closureKind: ClosureKind;
  complete: boolean;
  enumeratedMembers: Array<string>;
  expectedCount?: number;
  incompleteReason?: string;
  observedCount: number;
  scope: string | Scope;
  witnessRefs: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Conflicts remain visible until an authorized adjudication cites the conflicting evidence and policy. */
export interface ConflictSet extends RecordEnvelope {
  claimIds: Array<string>;
  conflictId: string;
  conflictingEvidence: Array<string>;
  description: string;
  disposition: ConflictDisposition;
  invalidatesDownstream: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Versioned requirements with units, tolerances and evidence/freshness/authority requirements. */
export interface Contract extends RecordEnvelope {
  contractVersion: string;
  freshnessPolicyRef?: string | FreshnessPolicy;
  name: string;
  predicates: Array<string | Predicate>;
  requiredAuthorityClasses?: Array<AuthorityClass>;
  requiredEvidence: Array<string | EvidenceRequirement>;
  scope: Array<string>;
  tolerances?: Record<string, string>;
  units?: Record<string, string>;
  "x-extension"?: Record<string, unknown>;
}

/** An authorized or computed disposition with cited inputs. Never inferred from labels or colours. */
export interface Decision extends RecordEnvelope {
  citedInputs: Array<string>;
  decisionKind: string;
  disposition: string;
  issuedByRole: string;
  policyRef?: string;
  rationale: string;
  "x-extension"?: Record<string, unknown>;
}

/** Proposed comparison of accepted equivalent work. A verdict is produced only by an evaluator, never by the producer. */
export interface EfficiencyClaim extends RecordEnvelope {
  cohort: Array<string | BenchmarkPair>;
  equivalenceContract: string | EquivalenceContract;
  evaluatorResultRef?: string;
  evaluatorVerdict?: Verdict;
  expectedClaim: string;
  metricId: string;
  producerNotes?: string;
  proposedValue?: string;
  "x-extension"?: Record<string, unknown>;
}

/** Emitted for any inference used to prune, rank, authorize or accept. */
export interface EntailmentReceipt extends RecordEnvelope {
  authorityClasses: Array<AuthorityClass>;
  depth: number;
  implementationDigest: string;
  intendedUse: string;
  metamodelDigest: string;
  receiptId: string;
  relation: string;
  ruleDigest: string;
  sourceGraphDigest: string;
  witnessPath: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** A listening port is not editor identity; an executable stub hash does not pin an engine build. */
export interface EnvironmentIdentity extends RecordEnvelope {
  adapterEndpointConfigDigest?: string;
  hostId: string;
  interpreter: string;
  interpreterVersion: string;
  moduleClosureDigest?: string;
  platform: string;
  processCreation?: { commandLineDigest?: string; createTime?: string; executableDigest?: string; executablePath?: string; pid?: number };
  providerBuild?: Record<string, string>;
  unknownFields: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Frozen comparison conditions, required quality/evidence, normalization, baseline rules and admissibility. */
export interface EquivalenceContract extends RecordEnvelope {
  cacheStratum: string;
  escalationPermitted?: boolean;
  evidenceStandard: Array<string | EvidenceRequirement>;
  failureRecoveryPolicy: string;
  frozen: boolean;
  heldConstant: Array<string>;
  invalidatingDifferences: Array<string>;
  minimumMatchedPairs: number;
  name: string;
  normalizationContract?: string;
  permittedDifferences: Array<string>;
  qualityThresholds: Array<string | Predicate>;
  requiredArtifactKinds: Array<string>;
  tokenAccountingBasis: string;
  verificationCostFields?: Array<string>;
  weightingPolicyRef: string | WorkUnitPolicy;
  "x-extension"?: Record<string, unknown>;
}

/** Bounded observation or source artifact with provenance, method, validity and admissibility. */
export interface Evidence extends RecordEnvelope {
  admissibility: EvidenceAdmissibility;
  contentDigest: string;
  evidenceKind: string;
  method: string;
  scope: string | Scope;
  subject: string;
  supportsClaimTypes: Array<string>;
  validFrom?: string;
  validUntil?: string;
  "x-extension"?: Record<string, unknown>;
}

export interface EvidenceRequirement {
  evidenceKind: string;
  freshnessSeconds?: number;
  mandatory: boolean;
  minimumAuthorityClasses: Array<AuthorityClass>;
  requiredObservationChannels?: Array<ObservationChannel>;
  requirementId: string;
  syntheticAcceptable: boolean;
  "x-extension"?: Record<string, unknown>;
}

export interface EvidenceSufficiencyReceipt extends RecordEnvelope {
  closed: boolean;
  mandatoryApplicable: number;
  mandatorySatisfied: number;
  requirementResults: Array<{ applicable: boolean; evidenceRefs: Array<string>; mandatory: boolean; reason: string; requirementId: string; satisfied: boolean }>;
  "x-extension"?: Record<string, unknown>;
}

/** Append-only envelope. Corrections are linked events, never silent edits. */
export interface ExecutionEvent extends RecordEnvelope {
  correctsEventId?: string;
  eventId: string;
  eventType: string;
  eventTypeVersion: string;
  idempotencyKey: string;
  logicalSubject: string;
  monotonicClockDomain?: string;
  monotonicNs?: number;
  payload?: unknown;
  payloadDigest: string;
  priorEventDigest: string;
  replayPolicy: string;
  sequence: number;
  wallClock: string;
  "x-extension"?: Record<string, unknown>;
}

/** Frozen work DAG with selection receipts and mandatory blocked nodes. */
export interface ExecutionPlan extends RecordEnvelope {
  frozen: boolean;
  limits?: Record<string, unknown>;
  nodes: Array<{ blocked: boolean; blockedReason?: string; dependsOn?: Array<string>; mandatory: boolean; nodeId: string; selectedImplementation?: string | Implementation; workItem: string | WorkItem }>;
  outcome: string | Outcome;
  selectionReceipts: Array<string | SelectionReceipt>;
  "x-extension"?: Record<string, unknown>;
}

/** Observed execution. Never stores model reasoning transcripts; captures externally observable work. */
export interface ExecutionTrace extends RecordEnvelope {
  actualActor: string;
  attempt: number;
  authorizationReceiptRef?: string;
  capability?: string | Capability;
  consumedArtifacts?: Array<string | ArtifactVersion>;
  environmentBinding: string | EnvironmentIdentity;
  events: Array<string | ExecutionEvent>;
  implementation?: string | Implementation;
  issuer: string;
  mutationScopeDeclared: boolean;
  parentTrace?: string | ExecutionTrace;
  plan: string | ExecutionPlan;
  producedArtifacts?: Array<string | ArtifactVersion>;
  resourceUsage: Array<string | ResourceUsage>;
  runId: string;
  spans: Array<string | Span>;
  terminalStatus: Status;
  workItem: string | WorkItem;
  "x-extension"?: Record<string, unknown>;
}

export interface FailureMode extends RecordEnvelope {
  code: string;
  description: string;
  domain: string;
  mapsToStatus: Status;
  severity: string;
  "x-extension"?: Record<string, unknown>;
}

/** Cache keys are decided by the claim, not by a shared filename. */
export interface FreshnessPolicy extends RecordEnvelope {
  alwaysFreshDomains: Array<string>;
  claimTypeGlob: string;
  maxAgeSeconds?: number;
  policyId: string;
  reusableWhileUnchanged: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Contract-bound evaluation definition. A definition link is never a PASS. */
export interface Gate extends RecordEnvelope {
  authority: string;
  evaluatesAgainst: Array<string | Contract>;
  independenceRequired: boolean;
  name: string;
  requiredPredicateIds: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** One execution of a Gate. Separate immutable record from the Gate definition. */
export interface GateResult extends RecordEnvelope {
  candidateDigest: string;
  contractDigests: Record<string, string>;
  evidenceClosure?: string | ClosureReceipt;
  gate: string | Gate;
  independentlyEvaluated: boolean;
  notRunDependency?: string;
  predicateResults: Array<{ evidenceRefs: Array<string>; expected?: unknown; observed?: unknown; predicateId: string; reason: string; status: Status }>;
  status: Status;
  "x-extension"?: Record<string, unknown>;
}

export interface Handoff extends RecordEnvelope {
  checkpoint: string | Checkpoint;
  fromActor: string;
  referencedEvidence: Array<string>;
  toActor: string;
  transferredFacts: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Versioned capability provider. Replaceable under the same capability contract. */
export interface Implementation extends RecordEnvelope {
  authorizedScope: Array<string>;
  failureModes?: Array<string>;
  inputSchemaDigest?: string;
  outputSchemaDigest?: string;
  providerName: string;
  providerVersion: string;
  qualification: Qualification;
  qualificationReceipt?: string | QualificationReceipt;
  realizes: Array<string | Capability>;
  resourceProfile?: Record<string, unknown>;
  "x-extension"?: Record<string, unknown>;
}

/** A typed metric result. Carries value, unit, scope, authority, validity, formula version, input references and a reason when unavailable. */
export interface Measurement extends RecordEnvelope {
  admissibility: EvidenceAdmissibility;
  availability: MetricAvailability;
  denominator?: string;
  formulaVersion: string;
  inputRefs: Array<string>;
  metricId: string;
  numerator?: string;
  scope: string | Scope;
  unavailableReason?: string;
  uncertainty?: string;
  unit: string;
  value?: string;
  "x-extension"?: Record<string, unknown>;
}

export interface MutationIntent extends RecordEnvelope {
  declaredEffects: Array<string>;
  intentId: string;
  operationId: string;
  preStateDigest: string;
  targetScope: string | Scope;
  "x-extension"?: Record<string, unknown>;
}

/** Append-only. A mutation-effect claim requires the authorized operation, intent, pre-state, ledger range, post-state, provider readback, direct ownership binding and rollback-set closure. */
export interface MutationLedgerEntry extends RecordEnvelope {
  effectDescription: string;
  entryId: string;
  intentId: string;
  operationId: string;
  ownership: string | OwnershipAssertion;
  postStateDigest: string;
  preStateDigest: string;
  priorEntryDigest: string;
  readbackRef?: string;
  sequence: number;
  transactionId: string;
  "x-extension"?: Record<string, unknown>;
}

/** Set equality between intended effects, ledger entries, readbacks and the rollback set. */
export interface MutationSetClosureReceipt extends RecordEnvelope {
  discrepancies: Array<string>;
  intendedEffects: Array<string>;
  ledgeredEffects: Array<string>;
  operationId: string;
  readbackConfirmedEffects: Array<string>;
  rollbackSet: Array<string>;
  setsEqual: boolean;
  "x-extension"?: Record<string, unknown>;
}

export interface Observation extends RecordEnvelope {
  channel: ObservationChannel;
  epoch?: string;
  errorClass?: string;
  observationId: string;
  observedAt: string;
  partial: boolean;
  rawDigest: string;
  scope: string | Scope;
  subject: string;
  value?: unknown;
  "x-extension"?: Record<string, unknown>;
}

/** An interruption after a possible side effect but before its receipt. Requires reconciliation, never an automatic retry. */
export interface OpenOperation extends RecordEnvelope {
  capability: string | Capability;
  disposition?: string;
  idempotencyKey: string;
  operationId: string;
  receiptObserved: boolean;
  reconciliationProbe?: string;
  reconciliationRequired: boolean;
  sideEffectPossible: boolean;
  "x-extension"?: Record<string, unknown>;
}

/** Requested end state, bounded scope, acceptance criteria, required artifacts/evidence, governing work-unit policy. */
export interface Outcome extends RecordEnvelope {
  acceptanceCriteria: Array<string | Contract>;
  lifecycle: LifecycleState;
  requestedResult: string;
  requiredArtifactKinds: Array<string>;
  requiredEvidenceKinds: Array<string>;
  subjectUniverse: Array<string>;
  title: string;
  workUnitPolicyRef: string | WorkUnitPolicy;
  "x-extension"?: Record<string, unknown>;
}

/** Direct ownership only. Ownership is not transitive and cannot be smuggled through containment. */
export interface OwnershipAssertion extends RecordEnvelope {
  directness: OperationalOwnership;
  ownerRole: string;
  subject: string;
  transactionId: string;
  "x-extension"?: Record<string, unknown>;
}

/** One allowlisted typed comparison. No expression evaluation, no policy eval. */
export interface Predicate {
  expected?: unknown;
  mandatory: boolean;
  operator: string;
  predicateId: string;
  subjectPath: string;
  tolerance?: string;
  unit?: string;
  "x-extension"?: Record<string, unknown>;
}

/** A producer's structural readiness statement. Carries no verification authority. */
export interface ProducerAssertion extends RecordEnvelope {
  evidenceRefs: Array<string>;
  note?: string;
  observedValue?: unknown;
  producerRole: string;
  producerStatus: Status;
  proposition: string | Proposition;
  "x-extension"?: Record<string, unknown>;
}

/** Pure policy evaluation over frozen audit inputs, followed only by a separately authorized actuator. */
export interface PromotionDecision extends RecordEnvelope {
  actuatorRole?: string;
  auditResultDigest: string;
  candidateDigest: string;
  humanApprovalRefs: Array<string>;
  issuerRole: string;
  policyDigest: string;
  reasons: Array<string>;
  state: PromotionState;
  "x-extension"?: Record<string, unknown>;
}

/** What is asserted, independent of who asserts it. */
export interface Proposition extends RecordEnvelope {
  claimType: string;
  expectedValue?: unknown;
  scope: string | Scope;
  statement: string;
  subject: string;
  unit?: string;
  "x-extension"?: Record<string, unknown>;
}

/** Orthogonal provenance dimensions attached at every assertion boundary. Legacy authority labels are derived from these through a tested mapping and are never raised silently. */
export interface Provenance {
  actor: string;
  authorityClass: AuthorityClass;
  observationChannel: ObservationChannel;
  operationalOwnership: OperationalOwnership;
  origin: Origin;
  productionMethod: ProductionMethod;
  sourceRefs?: Array<string>;
  syntheticFixture: boolean;
  validitySnapshot?: string;
  verificationStatus: VerificationStatus;
  "x-extension"?: Record<string, unknown>;
}

/** An independent re-read of the mutated subject from the provider. A provider success field is not a readback. */
export interface ProviderReadback extends RecordEnvelope {
  channel: ObservationChannel;
  matchesExpectedPostState: boolean;
  observedStateDigest: string;
  operationId: string;
  readbackId: string;
  "x-extension"?: Record<string, unknown>;
}

export interface ProviderSession extends RecordEnvelope {
  accountingVersion: string;
  expiresAt?: string;
  openedAt: string;
  providerName: string;
  revalidateOnResume: boolean;
  sessionId: string;
  tokenizerId: string;
  "x-extension"?: Record<string, unknown>;
}

/** Qualification never floats to another version, build, configuration or candidate. */
export interface QualificationReceipt extends RecordEnvelope {
  buildIdentityDigest?: string;
  candidateDigest?: string;
  configurationDigest: string;
  dependencies: Array<string>;
  limits: Array<string>;
  observedAt: string;
  probeScope: string | Scope;
  providerName: string;
  providerVersion: string;
  receiptId: string;
  result: Qualification;
  subjectKind: string;
  syntheticFixture: boolean;
  "x-extension"?: Record<string, unknown>;
}

export interface ReleaseManifest extends RecordEnvelope {
  acceptanceByDimension: Array<{ dimension: AcceptanceDimension; evidenceRefs: Array<string>; reason: string; status: Status }>;
  auditResultDigest?: string;
  blockers: Array<string>;
  dependencyLockDigest: string;
  knownGaps: Array<string>;
  liveUrl?: string;
  memberDigests: Record<string, string>;
  payloadDigest: string;
  product: string;
  releaseUrl?: string;
  repositoryUrl?: string;
  schemaManifestDigest: string;
  version: string;
  "x-extension"?: Record<string, unknown>;
}

/** Typed measured resource vector with observation authority, scope, accounting basis and uncertainty. */
export interface ResourceUsage extends RecordEnvelope {
  accountingRule: AccountingRule;
  basis: MeasurementBasis;
  belowResolution?: boolean;
  clockResolutionNs?: number;
  dedupKey: string;
  kind: ResourceKind;
  parentKind?: ResourceKind;
  providerAccountingVersion?: string;
  providerName?: string;
  providerResponseId?: string;
  scope: string | Scope;
  tokenizerId?: string;
  uncertainty?: string;
  unit: string;
  unknownReason?: string;
  value?: string;
  "x-extension"?: Record<string, unknown>;
}

export interface ResourceUsageLedger {
  accountingDomains: unknown;
  consumes: unknown;
  measurements: Array<string | ResourceUsage>;
  recordType: string;
  runId: string;
  schemaVersion: string;
  subsetReconciliation: unknown;
  synthetic: boolean;
  totals: unknown;
  "x-extension"?: Record<string, unknown>;
}

export interface Retry extends RecordEnvelope {
  attempt: number;
  ofInvocationId: string;
  permitted: boolean;
  reasonClass: string;
  "x-extension"?: Record<string, unknown>;
}

/** A view projects state. It never establishes it. */
export interface ReviewView extends RecordEnvelope {
  accessibilityResults: Array<{ checkId: string; reason: string; status: Status }>;
  lifecycle: ViewLifecycle;
  profileId: string;
  rasterProfileDigest?: string;
  rendererId: string;
  rendererVersion: string;
  semanticInputDigest: string;
  sourceAuditDigest?: string;
  sourceCheckpointDigest?: string;
  unavailableReason?: string;
  viewId: string;
  "x-extension"?: Record<string, unknown>;
}

export interface RollbackAction extends RecordEnvelope {
  actionId: string;
  authorizedByRole: string;
  performed: boolean;
  resultDigest?: string;
  targetEntryId: string;
  "x-extension"?: Record<string, unknown>;
}

/** A bounded scope. Absence claims require ENUMERATION closure over exactly this scope. */
export interface Scope {
  enumerationComplete: boolean;
  epoch?: string;
  expectedMemberCount?: number;
  scopeKind: string;
  selector: string;
  "x-extension"?: Record<string, unknown>;
}

/** Deterministic candidate selection: generate, hard-prune, feature, rank, budget-select, commit. Hard predicates are never overridden by ranking. */
export interface SelectionReceipt extends RecordEnvelope {
  blocked: boolean;
  candidateUniverse: Array<string>;
  committed?: string;
  hardPredicates: Array<string | Predicate>;
  nodeId: string;
  prngSeed?: string;
  prunedCandidates: Array<{ candidateId: string; predicateId: string }>;
  quantization: number;
  rankedCandidates: Array<{ candidateId: string; score: string }>;
  terminalDecisionByCandidate: Record<string, string>;
  tieBreak: string;
  "x-extension"?: Record<string, unknown>;
}

/** State and purpose are orthogonal. Verification and rework spans inside active execution are labelled subsets, not additive siblings. */
export interface Span extends RecordEnvelope {
  actorId: string;
  allocationUnknown: boolean;
  belowResolution?: boolean;
  clockDomain: string;
  clockResolutionNs?: number;
  endNs: number;
  leaf: boolean;
  parentSpanId?: string;
  purpose: ExecutionPurpose;
  spanId: string;
  startNs: number;
  state: ExecutionState;
  traceRunId: string;
  uncertainty?: string;
  "x-extension"?: Record<string, unknown>;
}

/** Bounded state inventory with completeness indicators, environment binding, freshness and unresolved facts. */
export interface StateSnapshot extends RecordEnvelope {
  admittedSourceVersions: Record<string, string>;
  artifactRefs: Record<string, string>;
  completeness: MetricAvailability;
  contractDigests: Record<string, string>;
  environmentBinding: string | EnvironmentIdentity;
  ephemeralBindings: Array<{ bindingKind: string; carriesAuthority: boolean; recordedValue: unknown; refreshRequiredOnResume: boolean }>;
  implementationVersions: Record<string, string>;
  planDigest: string;
  requiredFacts: Array<{ factId: string; missingReason?: string; present: boolean; provenance?: string | Provenance; value?: unknown }>;
  "x-extension"?: Record<string, unknown>;
}

export interface ToolInvocation extends RecordEnvelope {
  completedAt?: string;
  errorClass?: string;
  idempotencyKey: string;
  implementation: string | Implementation;
  invocationId: string;
  resultDigest?: string;
  startedAt: string;
  terminalStatus: Status;
  "x-extension"?: Record<string, unknown>;
}

export interface Transaction extends RecordEnvelope {
  closedAt?: string;
  committed: boolean;
  openedAt: string;
  operationId: string;
  transactionId: string;
  "x-extension"?: Record<string, unknown>;
}

/** An independent recomputation of a proposition. Produced only inside the auditor package. */
export interface Verification extends RecordEnvelope {
  claimId?: string;
  commonModeDependencies: Array<string>;
  independenceLevel: string;
  mode: string;
  producerStatus?: unknown;
  proposition?: string | Proposition;
  reason: string;
  recomputedValue?: unknown;
  recordType?: string;
  status: Status;
  "x-extension"?: Record<string, unknown>;
}

export interface VerificationCostSet {
  auditorTokens: string | ResourceUsage;
  managerTokens: string | ResourceUsage;
  recoveryTokens: string | ResourceUsage;
  "x-extension"?: Record<string, unknown>;
}

/** Bounded unit of work with an accounting identity. */
export interface WorkItem extends RecordEnvelope {
  accountingId: string;
  accountingPartition: string;
  contracts: Array<string | Contract>;
  lifecycle: LifecycleState;
  limits?: Record<string, unknown>;
  parentOutcome: string | Outcome;
  permittedSideEffects: Array<string>;
  prerequisites?: Array<string | WorkItem>;
  requiredCapabilities: Array<string | Capability>;
  title: string;
  "x-extension"?: Record<string, unknown>;
}

/** Bounded dispatch extension. Not a different completed-work unit by default. */
export interface WorkPacket extends RecordEnvelope {
  finalAuditAuthority: boolean;
  frozenInterfaceVersion: string;
  ownedPaths: Array<string>;
  ownerRole: string;
  packetId: string;
  requirementIds: Array<string>;
  "x-extension"?: Record<string, unknown>;
}

/** Predeclared, versioned acceptance universe with frozen weights. Weighting is frozen before any benchmark or release measurement. */
export interface WorkUnitPolicy extends RecordEnvelope {
  acceptanceUniverse: Array<{ accountingId: string; partialCreditDefined: boolean; partition: string; requiredGateIds: Array<string>; weight: string }>;
  frozen: boolean;
  frozenAt?: string;
  policyVersion: string;
  "x-extension"?: Record<string, unknown>;
}

export const KERNEL_CONCEPTS = [
  "Artifact",
  "Capability",
  "Checkpoint",
  "Contract",
  "Decision",
  "EfficiencyClaim",
  "EquivalenceContract",
  "Evidence",
  "ExecutionPlan",
  "ExecutionTrace",
  "Gate",
  "Implementation",
  "Outcome",
  "ResourceUsage",
  "StateSnapshot",
  "WorkItem",
] as const;

export const ALLOWED_CLOSURES: ReadonlyArray<readonly [string, string]> = [
  ["directPrerequisite", "dependsOn"],
  ["directlyDerivedFrom", "derivedFrom"],
  ["directlyPrecedes", "precedes"],
] as const;
