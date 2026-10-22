# Notes for coding agents

ecfr-markdown exports the eCFR to Markdown: one file per CFR section, YAML front matter, effective dates.
`ecfr_markdown/` is the library and CLI; `corpus/` is a committed export of the parts in `programs.json`.

## Rules

- **Standard library only.** No runtime dependencies; keep `dependencies = []` in `pyproject.toml`.
- **UTF-8 everywhere.** Every `read_text`/`write_text`/`open` passes `encoding="utf-8"` (section signs and
  em dashes crash on Windows otherwise). Paths written into files use `as_posix()`.
- **Read every page.** The eCFR API pages results (the `versions` endpoint at 1,000; 20 CFR 416 has more).
  Any new endpoint call loops until `meta.total_pages`.
- **Dates.** `effective_from` is when a version took effect; `effective_to` is its **last day in force,
  inclusive** (`""` for current text). Versions of a section never overlap, but gaps are real: a section can be
  removed and restored (42 CFR 457.960 was gone 2024-06-03 to 2026-06-02). Reserved sections are skipped.
- **Output is deterministic.** The weekly sync deletes `corpus/` and re-exports, so a wall-clock time (or the
  eCFR's daily "up to date as of" date) anywhere in the output would change every file every week. `generated.at`
  is the version's effective date, not a retrieval time. `test_fresh_exports_are_byte_identical` guards this. In
  the nested layout an export owns its part directory (it deletes section files it didn't write).
- **OKF v0.2.** The corpus is an OKF v0.2 bundle (`tests/test_corpus_okf.py` checks it): `type` on every
  document, `generated: {by, at}` (not the v0.1 `timestamp`), `status: deprecated` on superseded versions, and
  `index.md` files with no front matter except `okf_version` on the root.
- **Be polite to the API.** Use `Client`; it pauses between requests and retries with backoff.

## Checks

```bash
python3 -m unittest discover -s tests    # CI runs this on Ubuntu and Windows, Python 3.9 and 3.13
```

Test rendering against `tests/fixtures/mini_part.xml` and exports against a fake client (see `tests/test_versions.py`);
tests never hit the network.

## Refreshing the corpus

```bash
python3 -m ecfr_markdown catalog programs.json --out corpus/ --since 2024-01-01
```

Takes about 45 minutes. Review `git diff --stat corpus` before committing; a real refresh touches only the
sections that changed upstream (and the indexes listing them). ctrimm/ecfr-mcp-safety-net builds its indexes from this corpus; rebuild its `data/` after a
refresh.

## Don'ts

- Don't hand-edit files in `corpus/`; change the renderer and re-export.
- Don't present the corpus as the official legal text (see the README caveats).
