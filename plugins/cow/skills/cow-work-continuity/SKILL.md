---
name: cow-work-continuity
description: Use COW when Codex needs to resume prior work, checkpoint progress, record an execution trace, bind evidence by digest, render compact status, or leave a verified handoff for another agent. Invoke explicitly when this workflow is requested.
---

# COW work continuity

COW means **Continuity Of Work Ontology**. Legacy runtime identifiers (`continuity_ontology`, `ont20`) are implementation compatibility names.

## Core rule

Resume durable state before reconstructing from conversation. Keep mechanical state and verification outside model context.

Use the bundled wrapper; do not inspect runtime source just to learn record shapes:

```bash
python "<absolute-work-continuity-skill-path>/scripts/cow_cli.py" model
```

The wrapper resolves the plugin's bundled runtime automatically.

## Resume first

If `.cow/checkpoints` exists, list checkpoint files and resume the intended checkpoint:

```bash
python "<absolute-work-continuity-skill-path>/scripts/cow_cli.py" resume   --checkpoint-root .cow/checkpoints   --checkpoint-id <checkpoint-id>   --observed '{"processId": <current-pid>}'
```

Interpret exit codes semantically: `0 PASS`, `2 FAIL`, `3 UNKNOWN`, `4 ERROR`, `5 invalid contract`, `6 blocked/NOT_RUN`. Never turn `UNKNOWN` into zero or retry a blocked side effect without reconciliation.

## Record new work

Prefer one model call at the end. During execution, use the deterministic step logger rather than asking the model to author bookkeeping JSON:

```bash
python "<absolute-work-continuity-skill-path>/scripts/log_step.py" --file .cow/steps.jsonl --step start
# do work
python "<absolute-work-continuity-skill-path>/scripts/log_step.py" --file .cow/steps.jsonl --step build --purpose GENERATION
# verify work
python "<absolute-work-continuity-skill-path>/scripts/log_step.py" --file .cow/steps.jsonl --step verify --purpose VERIFICATION
```

Then record the completed task:

```bash
python "<absolute-work-continuity-skill-path>/scripts/cow_cli.py" task record   --root .cow   --task-id <id>   --evidence <input>::source   --evidence <output>   --steps .cow/steps.jsonl   --fact <key>=<value>   --quiet
```

Report the compact CLI status verbatim. A producer status is a producer assertion, not independent verification.

For intermediate milestones, run `task record` with distinct task/checkpoint IDs. Read `references/operations.md` for supported operations and checkpoint formats.

## Status

Use compact projections instead of loading full record stores:

```bash
python "<absolute-work-continuity-skill-path>/scripts/cow_cli.py" status <state.json>
```

If a query returns `UNKNOWN`, report that the corpus cannot support the answer. Do not fill the gap from intuition.

## Before handing off

Report only changed facts, current gate/status, evidence references, blockers, checkpoint id, and next recorded actions. Keep `PASS`, `FAIL`, `UNKNOWN`, `ERROR`, and `NOT_RUN` distinct.

## Interpreter and state formats

Choose an available Python 3.10+ interpreter before running examples: `python3`, `python`, or Windows `py -3`. Use forward slashes in evidence paths. Validate `.cow/records/checkpoint.json` as a Checkpoint envelope; use `resume` for checkpoint-store bodies. Read `references/operations.md` before interpreting changed process bindings.

## Script paths

Replace `<absolute-work-continuity-skill-path>` with this installed skill directory before running examples. Keep the working directory at the user project so `.cow` records are written there, not inside the plugin installation.
