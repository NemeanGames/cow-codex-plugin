# Supported plugin operations

Use the bundled `cow_cli.py` wrapper with Python 3.10+. It verifies generated
model identities before dispatch. Keep the working directory in the user project;
write runs outside the installed plugin. Use forward slashes in evidence paths.

Supported workflows: `model`, `profiles`, `task record`, `task verify`, `resume`,
`validate`, `status`, `report`, and `run-e2e`. Consult each command's `--help`.
The private `pershing` and `sfd` providers are not included.

Record each independent run into a new root. Verify with `task verify --root <run>`.
Resume with `--checkpoint-root <run>/checkpoints --cas-root <run>/cas` and a fresh
`--observed` process binding. Observations establish declared freshness, not OS
authentication, authorization or permission to reuse old handles.

Task verification exits: PASS 0, FAIL 2, UNKNOWN 3, ERROR 4, NOT_RUN 6.
Resume exits 6 when Claim or evidence integrity blocks continuation.
Missing required Claim bodies are UNKNOWN; malformed, duplicated, mis-bound or
modified records are FAIL. Evaluation/I/O errors are ERROR. A missing CAS is
NOT_RUN; it never disables Claim checking. No Claim obligation is non-blocking NOT_RUN.

Standalone Claim pins, bundled revision bodies, each member's own evidence/CAS
references, and exact path/ID/digest associations are checked. Identical bytes at
distinct paths remain legitimate. The top-level contentDigest hash exclusion is
unchanged; a separate binding cross-check protects that field.

Historical runs are never migrated automatically. Old bundles without required
Claim bodies remain non-resumable. Recover from preserved inputs into a new run;
do not rewrite the original checkpoint. Producer self-checks are not independent
verification. No plugin workflow grants live adapter or release approval.

Validate record envelopes such as `<run>/records/checkpoint.json` with
`validate Checkpoint`; use resume for checkpoint-store bodies in `checkpoints/`.
