# Research provenance with COW

COW is best used as an evidentiary/execution-provenance layer, not as a replacement for bibliographic standards. A publication package should retain persistent identifiers and conventional metadata externally while COW records execution, evidence, gates, and resumable state.

Useful conceptual mappings:

- COW Evidence/Artifact -> provenance entity
- ExecutionTrace / activity -> provenance activity
- human, model, software, organization -> provenance agent
- digest/derivedFrom -> derivation identity
- Checkpoint/StateSnapshot -> resumable execution state
- GateResult/Verification -> evidentiary qualification

For external interoperability, prefer export adapters to W3C PROV / RO-Crate rather than redesigning the COW kernel around those standards.
