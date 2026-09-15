# Supported plugin operations

Use the bundled cow_cli.py wrapper, which validates frozen identity before dispatch.
Choose an installed Python 3.10+ interpreter: `python3`, `python`, or Windows `py -3`.
Use forward slashes in evidence paths, including on Windows.

Supported documented workflow: `model`, `profiles`, `task record`, `resume`,
`validate`, `status`, `report`, and `run-e2e`. Consult each command's `--help`.
Use `task record` at each completed milestone with a distinct task and checkpoint id.
The advanced manifest-based task commands and hand-assembled query corpus are
not documented workflows in this plugin. `query --list` only lists available queries.

Validate the record envelope at `.cow/records/checkpoint.json` using
`validate Checkpoint`. Files inside `.cow/checkpoints/` are checkpoint-store bodies;
use `resume` to inspect them, not the record-envelope validator.

Resume without fresh processId observation is blocked. A new supplied processId
can satisfy freshness even when it differs. This is not OS process authentication
or permission to reuse old handles. Inspect current resources and reacquire handles
before side effects. `--fact` stores strings and does not reconcile typed ephemeral
bindings; do not use a processId fact as a substitute for `--observed`.

Audit and research skills guide review; neither invokes an independent auditor.
No private integration, release-sealing scripts, or full upstream tests are shipped.
