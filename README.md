# ecfr-markdown

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
timestamp: "2026-10-11T10:20:19Z"
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

The front matter follows Google Cloud's **Open Knowledge Format (OKF) v0.1** (`type` required; `title`, `description`, `resource`, `tags`, `timestamp` optional), plus a few extensions: `citation`, `title_number`, `part`, `subpart`, `effective_from`, `effective_to`.

**Effective dates.** Every current file says when its text took effect (the section's latest amendment). If you export with `--as-of 2024-06-01`, you also get the text that was in force on that date, but only for sections whose text has changed since; those files are named `...--as-of-2024-06-01.md` and carry `effective_to`. Together they answer "what did the rule say on date X?"

## Use it

```bash
pip install -e .            # or: python3 -m ecfr_markdown ...

# one part, current text, plus the mid-2024 version where it differs
ecfr-md part --title 7 --part 273 --out out/ --as-of 2024-06-01

# every program in a catalog, then index.md files and manifest.json
ecfr-md catalog programs.json --out corpus/ --as-of 2024-06-01

# rebuild indexes after editing
ecfr-md index corpus/
```

From Python:

```python
from ecfr_markdown import Client, iter_units

xml = Client().full_xml(7, "2026-10-08", "273")
for unit in iter_units(xml, 7):
    print(unit.citation, unit.heading, len(unit.markdown))
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
