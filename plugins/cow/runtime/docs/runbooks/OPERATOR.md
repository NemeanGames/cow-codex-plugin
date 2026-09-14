# Operator runbook

Every command below was executed against this candidate on the host that built
it. None of them is an invented CLI name; `tests/platform/test_cli_and_platform.py`
runs the same commands and fails if one stops working.

## Setup

The core imports nothing outside the standard library and the preserved CityQA
source packages, so setup is a virtual environment and a path, not a dependency
resolution.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install "pytest==8.3.4"   # development only
```

Both source roots go on the path:

```bash
export PYTHONPATH="src:third_party/cityqa-deterministic/src"
```

After this point every command runs offline.

## Exit codes

Inherited unchanged from the CityQA suite, so existing callers keep working:

| Code | Meaning |
|---|---|
| 0 | PASS / APPROVE |
| 2 | FAIL / REJECT |
| 3 | UNKNOWN |
| 4 | ERROR |
| 5 | INVALID_CONTRACT |
| 6 | NOT_RUN / blocked by prior state |

## Inspect the model

```bash
python -m continuity_ontology.cli.main model
```

Reports the metamodel version, the semantic-model digest, whether all sixteen
kernel concepts are present, and the permitted closures.

```bash
python -m continuity_ontology.cli.main profiles
```

Describes every digest domain and the exact byte rules that define it. Read
this before assuming two digests are comparable — they usually are not.

## Validate a record

```bash
python -m continuity_ontology.cli.main validate ResourceUsage path/to/record.json
```

Exit 0 when valid, 2 when not. Unknown production fields are rejected;
versioned extension data belongs under `x-extension`, where it cannot affect
acceptance.

## Run the real end-to-end workflow

```bash
python -m continuity_ontology.cli.main run-e2e --source ./docs --run-root ./runs/demo
```

This is an observed execution, not a fixture. It packages real files, verifies
the archive, records events and spans from the monotonic clock, stores evidence
by content digest, seals a producer bundle, freezes an audit input, runs the
independent auditor, evaluates promotion, credits accepted work and commits a
checkpoint.

It reports `vendorTokens: UNKNOWN` because it calls no provider. That is the
honest value: the run supports timing, replay and correctness claims, and
supports no token-reduction claim at all.

## Resume from a checkpoint

```bash
python -m continuity_ontology.cli.main resume \
  --checkpoint-root ./runs/demo/checkpoints \
  --checkpoint-id cp.e2e \
  --observed '{"processId": 12345}'
```

Resume reads no conversation history. It restores the required-fact inventory
from committed state and reports continuity retention.

Omit `--observed` and it exits **6** with `resumable: false`, because the
checkpoint records a process id that must be freshly observed. A saved handle
is a historical note, never continuing authority. That refusal is the feature.

If an operation was interrupted after a possible side effect but before its
receipt, resume reports it as `RECONCILE_BEFORE_RETRY`. Probe actual state
before retrying; a missing receipt is not evidence that nothing happened.

## Answer competency questions

```bash
python -m continuity_ontology.cli.main query corpus.json
python -m continuity_ontology.cli.main query corpus.json --query-id q.accepted_work
```

Exit 3 when a question cannot be answered from the corpus. Every answer carries
the witness records it was computed from; an answer with no witnesses is not
returned.

## Render status and reports

```bash
python -m continuity_ontology.cli.main status state.json
python -m continuity_ontology.cli.main report state.json --out web/report.html
```

`status` is the default projection: compact, and it names every blocker even
when that exceeds the word budget. `report` writes an accessible read-only HTML
page and exits 2 if any accessibility check fails.

## Pershing integration profile

```bash
python -m continuity_ontology.cli.main pershing
python -m continuity_ontology.cli.main pershing --runbook PG5
```

The first validates every arithmetic and policy invariant in
`profiles/pershing/program.json`. The second renders that gate's runbook from
the profile — editing the rendered text has no effect; change the profile.

**Every gate is `BLOCKED_PENDING_AUTHORIZATION`.** Compiling a gate into an
executable contract requires an authorization receipt and, for PG6, the 24
sealed visual-sample building ids, which were not supplied and must be derived
and sealed rather than invented.

## SFD checksum qualification

```bash
python -m continuity_ontology.cli.main sfd
```

Exits **3 (UNKNOWN)**, deliberately. The v1 world checksum is implemented from
the reported source semantics and pinned by golden vectors, but the exact SFD
source files were not transferred with this handoff, so byte compatibility
cannot be certified. Admitting the source will confirm or contradict this
implementation.

## Scan the agent steering files

```bash
python scripts/scan_agent_steering.py            # scan AGENTS.md, CLAUDE.md, the skill
python scripts/scan_agent_steering.py --verify   # also check digests against the frozen release
python scripts/scan_agent_steering.py some.md    # scan an arbitrary file, e.g. from a PR
```

Run this on every fresh clone, fork and pull request **before** any agent
reads those files. They are followed at cold start, often unread by a human,
which makes them the cheapest place to plant a payload. Exit `0` is clean; exit
`2` names each finding with its line and why it matters. The payload build
runs the same scan over the built copies and refuses to ship on a finding.

What it detects: remote fetch-and-execute, encoded payloads, invisible and
direction-override characters, hidden HTML comments, instruction-override
phrasing, credential access, any external URL, safety-bypass and destructive
flags, non-ASCII in code spans (homoglyphs), commands the repository does not
contain, and files past the 32 KB bound. A clean result means no known pattern
was found; it does not certify intent, so a human still reads a PR diff.

## Regenerate and check generated artifacts

```bash
python scripts/generate_representations.py            # regenerate
python scripts/generate_representations.py --check    # detect drift
```

`--check` exits 1 and names each divergent path if a generated file was
hand-edited.

## Build the release candidate

Run in this order; each step consumes the previous one's receipt.

```bash
python scripts/freeze.py   # builds, checks the full suite, and verifies final identities
```

**Run the freeze chain after the last edit; `build_release.py` must be the last tree-writing command before commit. `tests/release/test_release_identity.py` checks that every release member and its digest match the final tree. Any later edit requires the chain again.**

`build_release.py` exits 2 if the two clean builds disagree. It writes
`dist/RELEASE_MANIFEST.json` and `dist/AUDIT_INPUT_MANIFEST.json` and stops:
it does not approve anything. The manifest's `archivePrivacy` block declares
the release archive INTERNAL and lists every sensitive-pattern hit inside it;
only the allowlisted public payload is built for publication.
`refresh_audit_log.py --check` exits 1 if the log has drifted from `dist/`.

## Seal an audit package

After committing the candidate, seal a read-only package for the independent
release auditor. The working tree must be clean; the archive is `git archive`
at the commit.

```bash
python scripts/build_audit_package.py --out ../ONT20/release-audit-<n>
```

Every file under the package root is in `MANIFEST.sha256` (LF line endings,
so `sha256sum -c` reads it). The runbook is rendered from
`docs/audit/RUN_RELEASE_AUDIT.md`. Reports the auditor returns are copied
byte-for-byte into `audits/<commit>/` with a `RECEIVED.json` receipt; their
statuses are the auditor's and never enter the requirement matrix.

## Migration

```python
from continuity_ontology.migration.legacy import migrate_record, migrate_status

migrate_status("PASS")
# -> producerStatus PASS, verificationStatus PRODUCER_ASSERTED,
#    independentlyVerified False
```

A v1 worker PASS becomes a producer assertion, not an independent v2 PASS.
Absent fields become UNKNOWN with a reason, never an invented default. Original
bytes are untouched and still verify under `ontology.core.v1`.

## Recovery

| Situation | Action |
|---|---|
| Resume exits 6 with missing required facts | The checkpoint is incomplete. Do not fabricate the facts; re-run from the last complete checkpoint. |
| Resume reports an open operation | Run the named reconciliation probe. Do not retry first. |
| Resume reports events after the sealed position | Verify the tail before treating it as committed. |
| `generate_representations.py --check` fails | A generated file was edited. Regenerate; do not hand-patch. |
| The event chain fails to verify | The log was altered. Preserve it as evidence and open a new run; do not repair in place. |
| A content-store object fails its digest | The store is corrupt. `ContentStore.verify_all()` lists every affected object. |
| Two clean builds disagree | `RELEASE_MANIFEST.json` lists `differingMembers`. Something time-bearing or cached entered the payload. |

Nothing here repairs production state automatically. A destructive action needs
the user's explicit one-time confirmation, and this program otherwise excludes
it.
