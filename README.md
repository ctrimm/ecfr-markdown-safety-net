# ecfr-markdown-safety-net

The **Electronic Code of Federal Regulations as Markdown**: one file per section, with effective dates, in a format both people and AI agents can read.

This repo has two parts:

1. **`ecfr_markdown/`**: a small Python library and command-line tool (standard library only) that pulls any CFR part from the official [eCFR API](https://www.ecfr.gov/developers/documentation/api/v1) at any date and writes clean Markdown.
2. **`corpus/`**: a ready-made Markdown copy of the federal rules for safety-net and benefit programs (SNAP, WIC, school meals, Summer EBT, TANF, Medicaid/CHIP, LIHEAP, SSI, housing vouchers, Lifeline, child care, unemployment insurance and more; see `programs.json`).

## Why

The eCFR's own text is excellent but locked in HTML pages and XML. Markdown files with a little metadata are easy to search, diff, cite, feed to a retrieval system, or drop into an agent's context. Each file is one section, which is how regulations are cited ("7 CFR 273.9").

## What a file looks like

```markdown
---
type: PolicyDocument
title: 7 CFR 273.9 Income and deductions
description: "Supplemental Nutrition Assistance Program (SNAP): 7 CFR 273.9 (Subpart D—Eligibility and Benefit Levels); text in force since 2025-01-17. ..."
resource: "https://www.ecfr.gov/current/title-7/section-273.9"
tags: [snap, nutrition, title-7, part-273, cfr, regulation]
generated: {by: ecfr-markdown/0.2.0, at: "2025-01-17T00:00:00Z"}
citation: 7 CFR 273.9
title_number: 7
part: 273
subpart: Subpart D—Eligibility and Benefit Levels
effective_from: 2025-01-17
effective_to: ""
---

# § 273.9 Income and deductions.

(a) *Income eligibility standards.* Participation in the Program shall be limited to ...
```

The corpus is a bundle in Google Cloud's **[Open Knowledge Format (OKF) v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)**:

- **Standard keys:** `type` (required), `title`, `description`, `resource` and `tags`.
- **`generated`:** `by` is this tool, in OKF's `<producer>/<version>` form. `at` is the day the version took effect: OKF defines it as the content's last meaningful change, and for a regulation that's the amendment.
- **`status: deprecated`:** marks superseded versions (the `--as-of-` files). OKF defines it as "kept for links and history; no longer current". Current text omits it, which OKF reads as `stable`.
- **Extension keys:** `citation`, `title_number`, `part`, `subpart`, `effective_from` and `effective_to`. OKF allows extra keys and has no point-in-time concept of its own.
- **Index files:** `index.md` files follow OKF §8. They have no front matter, except `okf_version: "0.2"` on the bundle root, and list `* [Title](link) - description` entries under headings.

**Effective dates.** Every current file says when its text took effect (the section's latest amendment). Export with `--since 2024-01-01` to also get every earlier version in force at any time since that date: one file per version, named `...--as-of-<date it took effect>.md` (or `--as-of-<since>` for the version already in force then), with `effective_from` and `effective_to` (its last day in force). Versions never overlap, so together they answer "what did the rule say on date X?" for any date since. A date can fall in a gap when a section was removed and later restored (42 CFR 457.960 was gone from 2024-06-03 to 2026-06-02). `--as-of <date>` writes just the version in force on one date, where it differs from today's text. The bundled `corpus/` is exported with `--since 2024-01-01`.

## Use it

```bash
pip install -e .            # or: python3 -m ecfr_markdown ...

# one part: current text plus every version in force since 2024
ecfr-md part --title 7 --part 273 --out out/ --since 2024-01-01

# every program in a catalog, with every version since 2024, then index.md files and manifest.json
ecfr-md catalog programs.json --out corpus/ --since 2024-01-01

# rebuild indexes after editing
ecfr-md index corpus/
```

Exports are deterministic: the same eCFR data always produces byte-identical files, because nothing records a wall-clock time. A fresh re-export (what the weekly sync does) therefore changes only what changed upstream. In the default nested layout each part directory is treated as the export's own, so section files that no longer apply (a section removed from the CFR, an old version that's no longer needed) are deleted.

From Python:

```python
from ecfr_markdown import Client, iter_units

xml = Client().full_xml(7, "2026-10-08", "273")
for unit in iter_units(xml, 7):
    print(unit.citation, unit.heading, len(unit.markdown))
```

## Change feed (RSS)

Every corpus change that lands on `main` is published to an RSS 2.0 feed:

**Feed URL:** https://raw.githubusercontent.com/ctrimm/ecfr-markdown-safety-net/main/feed.xml

(Also served via GitHub Pages at https://ctrimm.github.io/ecfr-markdown-safety-net/feed.xml - same file, same content.)

One item per changed section file: the citation (for example `7 CFR 273.9`), whether the file was added, modified or deleted, the date, and links to the file on GitHub and to the official section page on eCFR.gov. Historical `--as-of-` version files are included; index files are not. The feed carries the newest 200 changes, and the full append-only history lives in [`feed/changes.jsonl`](feed/changes.jsonl).

A GitHub Actions workflow (`.github/workflows/feed.yml`) does this automatically after each push to `main` that touches `corpus/`: it diffs the push, records the changed sections with `tools/build_feed.py`, regenerates `feed.xml`, and commits both files back. To record a range by hand:

```bash
python3 tools/build_feed.py record --before <sha> --after <sha>
python3 tools/build_feed.py build   # regenerate feed.xml from the log alone
```

## What's rendered

Paragraphs (with italics), subheadings, both of the eCFR's table formats (as Markdown tables), extracts and notes (as block quotes), source citations, editorial notes and footnotes. Formulas and images that have no text form are replaced by a note pointing to the official source. Reserved sections are skipped. Appendices become their own files.

## Caveats

- This is a convenience copy, not the official legal edition. The eCFR itself is an editorial compilation that the Office of the Federal Register updates daily; for legal purposes, cite the official CFR or the Federal Register.
- Laws passed but not yet written into regulations (for example SNAP changes in Public Law 119-21) won't appear here until agencies amend the CFR; agency guidance memos fill that gap.
- Be polite to the public API: the client waits briefly between requests and retries with backoff.

## Tests

```bash
python3 -m unittest discover -s tests
```

## License

Code: MIT (see `LICENSE`). The regulatory text in `corpus/` is a work of the U.S. government and is in the public domain.
