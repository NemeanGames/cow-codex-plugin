# Changelog

## Codex 1.0.2 / Claude Code 1.0.3 — cycle 8 candidate

- Refresh the public runtime from upstream commit `ab1b179b02996500050e547eff4d846ca0e836ed`.
- Verify required standalone and bundled Claims before commit, during resume and in `task verify`, including checkpoints with zero artifacts.
- Reject duplicate/conflicting Claim pins and evidence associations; verify each bundle member's revision body and referenced CAS bytes.
- Preserve legitimate equal-content files at different paths and prevent failed recording from replacing a committed run.
- Keep the public plugin's complete next-action text and word-boundary compact status formatting.
- Add a Claude Code marketplace alongside the Codex marketplace, sharing the same public runtime and skills.
- Add deterministic archives, runtime file hashes, focused regressions and fresh-extraction wrapper tests for both clients.

Compatibility: no historical migration. Required Claim bodies missing from old runs remain UNKNOWN and block resume. Record preserved inputs into a new run instead of rewriting old evidence. No-CAS verification remains NOT_RUN. The core hash profile and separate contentDigest binding check are unchanged.

Upstream source audit: R13/R17/F4/F5 PASS; 49 mandatory PASS, zero FAIL, R31/R39/R41 UNKNOWN; overall INDETERMINATE. The offline handoff trial passed. These are scoped source/trial findings, not independent approval of this adapted plugin package, native client validation, live-editor qualification or a general efficiency claim.

This candidate does not replace or rewrite existing release tags. No private research archives, real project receipts, historical runs or host-specific paths are included.

## Previous public packages

- Codex 1.0.1 corrected frozen identity checks and public workflows.
- Claude Code 1.0.2 additionally corrected compact next-action truncation in the separately distributed Claude package.
- Original 1.0.0 artifacts remain historical identities.
