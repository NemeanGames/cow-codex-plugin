# COW â€” Continuity Of Work for Codex

Native agent plugins that package the **Continuity Of Work Ontology (COW)** as reusable skills plus the deterministic COW runtime.

COW separates model reasoning from durable state, evidence, verification, and audit-ready records. The plugin is skill-only: it does not require an external app or MCP server and does not contain private pilot transcripts or private program adapters.

## Included skills

- `cow-work-continuity` â€” checkpoint, resume, record work, status, and competency queries.
- `cow-audit-boundary` â€” preserve producer/auditor separation and five-state semantics.
- `cow-research-provenance` â€” structure research claims, evidence, provenance, and qualification status.

## Install as a local Codex plugin

Public repository: [NemeanGames/cow-codex-plugin](https://github.com/NemeanGames/cow-codex-plugin).
Documentation: [COW for Codex](https://nemeangames.github.io/cow-codex-plugin/).

Clone the repository, then use the absolute path to your clone in the commands below:

```bash
git clone https://github.com/NemeanGames/cow-codex-plugin.git
```

The repository includes a Codex marketplace manifest at `.agents/plugins/marketplace.json` and the plugin at `plugins/cow`.

For a non-default local marketplace, add the repository root and install the plugin:

```bash
codex plugin marketplace add /path/to/cow-codex-plugin-repo
codex plugin add cow@cow-local
```

Then start a new Codex thread so the new skills are discovered.

For a workspace marketplace, publish this repository to GitHub and import the repository from **Workspace settings â†’ Plugins â†’ Add â†’ Import marketplace**. OpenAI's current Codex format uses `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json`.

## Runtime provenance

The current public runtime subset is derived from cycle-8 commit `ab1b179b02996500050e547eff4d846ca0e836ed`. Its source allowlist and public adaptations are recorded in `plugins/cow/UPSTREAM_PROVENANCE.json`; current bytes are pinned in `RUNTIME_MANIFEST.sha256`. Legacy internal module names such as `continuity_ontology` and `ont20` remain unchanged for compatibility; the product name exposed by this plugin is **Continuity Of Work Ontology (COW)**.

## Scope

The plugin preserves `PASS`, `FAIL`, `UNKNOWN`, `ERROR`, and `NOT_RUN` as distinct states. It does not convert a producer assertion into independent verification and does not make a general efficiency, monetary-savings, or cross-domain reliability claim.

## Release history and validation

The original annotated `v1.0.0` tag points to `8f6d3bf96e7f9d5c4bf8e39fd2864cc901864c64`.
Publication and documentation changes follow that tag without rewriting it.
`AUDIT_LOG.json` and `work_packets/` describe the original author-side packaging checks, not an independent release audit.

Python 3.10 or later is required to run the bundled runtime. Check the installation with:

```bash
python plugins/cow/skills/cow-work-continuity/scripts/cow_cli.py model
python scripts/validate_plugin.py plugins/cow
```

The historical bootstrap is generic execution guidance. The public profile in
`AGENT_BOOTSTRAP_v4.1.md` does not authorize operations or establish that independent agents ran.
Private research archives, transcripts, credentials, and real execution records must remain outside this repository.

## v1.0.1 corrective release

The previous corrective release was v1.0.1. The original v1.0.0 tag remains available for historical provenance, but its Git source has inconsistent line endings and frozen digests. The original standalone v1.0.0 ZIP passes its own frozen identity checks; it still lacks startup enforcement and contains unsupported entry points.

v1.0.1 normalizes runtime source bytes, regenerates representations, checks model/extension/artifact digests before every wrapper command, removes unavailable integration commands, and corrects the runbook. Its semantic identity is `sha256:419687df6a57c009f9657437e1bec5d2739c2c8e17ba5f5978a85f2cee84d40e`. This is a new identity, not a relabeling of historical records. No automatic migration or cross-verification with old identities is claimed.

The audit skill supplies review guidance, not an independent auditor executable. Resume observations establish freshness only; they do not authenticate OS processes or authorize side effects. The bundled runtime is a public subset, not the full upstream research distribution.

## Cycle 8 candidate: Codex 1.0.2 / Claude Code 1.0.3

Required Claims and evidence are checked before checkpoint commit, on resume, and
by `task verify`. Missing bodies, altered records, duplicate bindings and corrupt
CAS content block continuation. Read [CHANGELOG.md](CHANGELOG.md) for compatibility
and qualification limits. Old checkpoints are preserved; recover by recording
preserved inputs into a new run root. A resume command should pass both
`--checkpoint-root <run>/checkpoints` and `--cas-root <run>/cas`.

The independent upstream audit closed R13/R17 and F4/F5. Its overall disposition
remains INDETERMINATE because R31/R39/R41 remain UNKNOWN. The adapted plugin package
has its own regression checks; upstream acceptance is not blanket package approval.
Native client installation and live-editor testing are not claimed.

### Claude Code

The root `.claude-plugin/marketplace.json` points to the same `plugins/cow`
public runtime. Add the local clone in Claude Code:

```text
/plugin marketplace add /absolute/path/to/cow-codex-plugin
/plugin install cow@cow-claude
```

Invoke `/cow:cow-work-continuity` explicitly. For manual commands, replace the
skill-path placeholder with the actual installed directory. No background hooks
or automatic transcript collection are configured.

### Build and check both packages

```bash
python -m pip install pytest==8.3.4
python scripts/validate_plugin.py plugins/cow
python scripts/build_plugins.py --out dist
python -B -m pytest tests -q -p no:cacheprovider
```

The builder emits separate Codex and Claude marketplace ZIPs and SHA256SUMS.
It rejects runtime bytes that differ from the committed manifest. Maintainers
must deliberately use `--refresh-runtime-manifest` after reviewing runtime edits.
CI tests both Windows and Linux. Generated model identity checks run through the
wrapper; regression tests exercise Claim integrity, evidence association, atomicity
and both freshly extracted packages. Tests use synthetic fixtures, not project data.
