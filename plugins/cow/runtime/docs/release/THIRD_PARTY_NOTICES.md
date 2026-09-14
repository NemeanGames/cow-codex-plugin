# Third-party notices

Every component reused by this release, its licence status, and what that
status permits. A component whose redistribution rights could not be
established is listed as a blocker rather than assumed permissive.

## Redistributed

### CityQA Deterministic Suite 1.0.0

- **Location:** `third_party/cityqa-deterministic/`
- **Licence:** MIT-style permissive, retained verbatim at
  `third_party/cityqa-deterministic/LICENSE`
- **Disposition:** `REUSE_UNCHANGED`
- **Modifications:** none. The tree is byte-identical to the admitted archive
  (`sha256:835ba45f2a04ddff…`). It is preserved as a source package rather than
  forked, so there is one QA engine in this repository and it is the original.
- **What is reused:** `cityqa.engine.canonical`, `hashing`, `atomic`,
  `evidence`, `schema`, `statuses`, `contracts`, `cache`, `impact`,
  `state_closure`, `runner`; the `cityqa_audit` recomputation boundary; the
  `cityqa_promote` evaluation/actuation split; `cityqa_visual` render profiles.
- **Runtime dependencies it adds:** none. It imports only the standard library.
- **Verification:** its own 128 tests were re-observed passing on this host
  under CPython 3.10.8, rather than accepted from its archived
  `TEST_RESULTS.json`.

## Not redistributed

### continuity-ontology 0.1.0

- **Location:** private reference only, under gitignored `source_snapshots/`.
  Deliberately absent from this repository and from every payload.
- **Licence:** **NONE FOUND.** The archive contains no `LICENSE`, `COPYING` or
  `NOTICE` file, and its README makes no licence statement.
- **Disposition:** `REFERENCE_ONLY`
- **Consequence:** redistribution rights are unknown, which is a publication
  blocker rather than permission to relicense. It was removed from
  `third_party/` once that was established.
- **What survives:** the `ontology.core.v1` entry in the hash-profile registry
  reproduces that package's serialization *format* — compact separators,
  `ensure_ascii=False`, no terminal newline, bare hexdigest — so identities
  produced by 0.1.0 keep verifying. That is a compatibility interface described
  from observed behaviour, not a copy of the package.

### continuity-aio 2.0.0

- **Location:** admitted during intake as `L02`, private reference only.
- **Disposition:** `REFERENCE_ONLY`
- **Consequence:** a different product with its own versions and manifests. It
  is not this release's repository and was not repurposed as one.

## Development-only

### pytest 8.3.4

- **Licence:** MIT
- **Scope:** test runner only. Nothing under `src/` imports it, so it is absent
  from any runtime path and from the release payload.

## Optional and not installed

### cairosvg

- **Licence:** LGPL-3.0
- **Scope:** optional raster backend, declared under the `raster` extra and
  **not installed** in this environment.
- **Consequence:** SVG is the authoritative view format. With no backend
  importable, a raster view is reported `UNAVAILABLE` with a reason — never a
  PASS, and never a claim that a picture was produced.
- **Note:** the LGPL obligations are not engaged by this release, which neither
  ships nor links it.

## Fonts

**No font binaries are included** in this repository or in any payload. Views
use a system font stack (`system-ui, sans-serif`) declared in CSS, so no font
licence is engaged and none is redistributed.

## Standards references

JSON Schema (draft 2020-12), JSON-LD 1.1, SHACL and RDF vocabularies are
referenced by URI and used as format specifications. No normative text is
reproduced, and no remote context, schema or shape is resolved at runtime —
`ontology/generated/context.jsonld` is locally pinned and
`runtimePolicy.remoteContextResolution` is `false`.

## Summary

| Component | Licence | Redistributed | Blocker |
|---|---|---|---|
| cityqa-deterministic 1.0.0 | MIT-style | yes | none |
| continuity-ontology 0.1.0 | none found | **no** | unknown redistribution rights |
| continuity-aio 2.0.0 | not assessed | **no** | different product |
| pytest 8.3.4 | MIT | no (dev only) | none |
| cairosvg | LGPL-3.0 | no (not installed) | none |
| fonts | n/a | **no** | none |
