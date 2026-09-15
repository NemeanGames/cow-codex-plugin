---
name: cow-audit-boundary
description: Use COW when Codex is reviewing, auditing, qualifying, or challenging a work product and must preserve the producer/auditor boundary, sealed-candidate identity, evidence sufficiency, and five-state outcomes. Invoke explicitly when this workflow is requested.
---

# COW audit boundary

## Non-negotiable boundary

A producer cannot independently verify its own claim. Treat producer status as `PRODUCER_ASSERTED` until a separate audit or admitted verification establishes otherwise.

Audit a fixed candidate identity. Do not repair the candidate during the audit. If a defect is found, return the finding against that sealed identity; repairs belong to a new candidate revision.

Preserve five states exactly:

- `PASS`: requirement demonstrated by admitted evidence.
- `FAIL`: contradiction or failed requirement demonstrated.
- `UNKNOWN`: required evidence is unavailable or insufficient.
- `ERROR`: evaluation could not execute correctly.
- `NOT_RUN`: scope/gate prevented execution.

Never soften `FAIL` to `UNKNOWN`, and never promote `UNKNOWN` to `PASS` because a fixture or analogy looks similar.

## Audit workflow

1. Pin candidate identity and evidence inventory.
2. Recompute mechanical claims from admitted bytes where possible.
3. Compare requirement text to implementation, not only to the candidate's own test mapping.
4. Use adversarial probes for edge cases; preserve probe output as evidence.
5. Report PASS/FAIL/UNKNOWN/ERROR/NOT_RUN separately.
6. Name unresolved requirements explicitly.
7. Do not synthesize a global approval state unless the governing contract defines one.

For the ontology's detailed semantics, read `references/audit-semantics.md` only as needed.
