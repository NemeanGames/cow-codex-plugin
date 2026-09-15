# COW — Continuity Of Work for Codex

A native Codex plugin that packages the **Continuity Of Work Ontology (COW)** as reusable skills plus the deterministic COW runtime.

COW separates model reasoning from durable state, evidence, verification, and audit-ready records. The plugin is skill-only: it does not require an external app or MCP server and does not contain private pilot transcripts or private program adapters.

## Included skills

- `cow-work-continuity` — checkpoint, resume, record work, status, and competency queries.
- `cow-audit-boundary` — preserve producer/auditor separation and five-state semantics.
- `cow-research-provenance` — structure research claims, evidence, provenance, and qualification status.

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

For a workspace marketplace, publish this repository to GitHub and import the repository from **Workspace settings → Plugins → Add → Import marketplace**. OpenAI's current Codex format uses `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json`.

## Runtime provenance

The bundled runtime is derived from the sanitized `continuity-ontology-public-runtime-v1.0.0` package. Legacy internal module names such as `continuity_ontology` and `ont20` remain unchanged for compatibility; the product name exposed by this plugin is **Continuity Of Work Ontology (COW)**.

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
