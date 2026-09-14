# COW operations reference

Use the bundled wrapper `scripts/cow_cli.py`; it loads the plugin runtime without installing packages globally.

## One-call record

`task record` authors and validates Outcome, WorkItem, ExecutionPlan, Evidence, Claim, ExecutionTrace, and Checkpoint records. Use `--root .cow` for project-local state.

## Multi-session record

Use `task init` before work, `task step` after plan steps, and `task finish` once deliverables exist. This is appropriate only when a checkpoint must exist before the task finishes.

## Resume semantics

A resume block is not permission to bypass the checkpoint. Supply fresh ephemeral observations, reconcile possibly-effectful open operations, verify event tails, or return to a complete checkpoint as named by the blocker.

## Evidence discipline

Reference evidence by digest/record id. Load full content only when the task genuinely requires inspection.
