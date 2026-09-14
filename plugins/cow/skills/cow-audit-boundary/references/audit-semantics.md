# COW audit semantics

COW separates mechanical verification from adversarial audit. Deterministic validators can establish schema, digest, contract, and state-transition properties; separate audit sessions challenge whether the implementation and admitted evidence satisfy the governing specification.

A sealed candidate is immutable for the duration of an audit. Findings are evidence about that candidate identity. A repaired candidate receives a new identity and a new audit.

`UNKNOWN` is an evidence status, not a soft failure or a value of zero. `ERROR` describes evaluator execution failure. `NOT_RUN` describes gated or out-of-scope evaluation.
