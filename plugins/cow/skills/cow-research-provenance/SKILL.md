---
name: cow-research-provenance
description: >-
  Use COW to structure research provenance for AI-assisted or computational work: connect claims to evidence, execution traces, checkpoints, agents, transformations, digests, and qualification state. Invoke explicitly when this workflow is requested.
---

# COW research provenance

Treat research provenance as more than file lineage. Preserve three layers:

1. **Artifact provenance** — what bytes/data/software a result came from.
2. **Execution provenance** — what activity, agent, environment, and transformation produced it.
3. **Evidentiary provenance** — why the admitted evidence is sufficient (or insufficient) to support a claim.

## Minimum record for a research claim

Capture:

- claim statement and scope;
- evidence references by digest/path, without inlining large content;
- producer/agent identity and role;
- execution trace or method reference;
- environment/model/tool identity when materially relevant;
- transformation/derivation links;
- checkpoint or state snapshot if work must resume;
- verification/gate result;
- unresolved evidence as explicit `UNKNOWN`.

Do not describe matching retained transcript bytes as cryptographic provider-origin authentication. Byte consistency and provider authentication are separate claims.

Do not turn pilot measurements into general monetary, reliability, or cross-domain efficiency claims. If discussing COW's own pilot results, read `references/research-status.md` first.

For mappings to common provenance concepts and recommended publication packaging, read `references/research-provenance.md`.
