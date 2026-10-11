"""Export CFR parts to Markdown files, one per section/appendix, with effective dates.

Output layout (default): <out>/title-<T>/part-<P>/<T>-cfr-<section>.md, plus
<T>-cfr-<section>--as-of-<date>.md for each earlier version that differs from
the current text. Every file opens with YAML front matter (Open Knowledge
Format v0.1 style: `type` plus title, description, resource, tags,
timestamp; extensions: citation, title_number, part, subpart,
effective_from, effective_to, retrieved).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .client import Client
from .render import Unit, iter_units


def _yaml(v) -> str:
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_yaml(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def front_matter(fm: dict) -> str:
    return "---\n" + "".join(f"{k}: {_yaml(v)}\n" for k, v in fm.items() if v not in (None, [])) + "---\n"


def slug(s: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def section_dates(versions: list[dict]) -> dict[str, list[str]]:
    out: dict[str, set] = {}
    for v in versions:
        out.setdefault(v.get("identifier", ""), set()).add(v["date"])
    return {k: sorted(v) for k, v in out.items()}


def day_before(d: str) -> str:
    """effective_to is the last day a version was in force: the day before the next version starts."""
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat() if d else ""


def unit_doc(u: Unit, title: str, date_from: str, date_to: str, as_of: str | None, program: str = "",
             tags: tuple = (), retrieved: str = "") -> tuple[str, str]:
    name = re.sub(r"^§+\s*[\w.\-]+\s*", "", u.heading).rstrip(".") if u.kind == "section" else u.heading
    url = (f"https://www.ecfr.gov/on/{as_of}/title-{title}/section-{u.number}" if as_of
           else f"https://www.ecfr.gov/current/title-{title}/section-{u.number}")
    if u.kind == "appendix":
        url = (f"https://www.ecfr.gov/{'on/' + as_of if as_of else 'current'}/title-{title}/part-{u.part}")
    span = f"in force {date_from} to {date_to}" if date_to else (f"in force since {date_from}" if date_from else "")
    lead = re.sub(r"\s+", " ", re.sub(r"[#>*|]", " ", u.markdown.split("\n", 1)[-1]))[:240].strip()
    fm = {
        "type": "PolicyDocument",
        "title": f"{u.citation} {name}".strip() + (f" (version in force {as_of})" if as_of else ""),
        "description": (f"{program + ': ' if program else ''}{u.citation}" + (f" ({u.subpart})" if u.subpart else "")
                        + (f"; text {span}" if span else "") + f". {lead}").strip(),
        "resource": url,
        "tags": [t for t in [*tags, f"title-{title}", f"part-{u.part}", "cfr", "regulation"] if t],
        "timestamp": retrieved or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "citation": u.citation,
        "title_number": title,
        "part": u.part,
        "subpart": u.subpart,
        "effective_from": date_from,
        "effective_to": date_to,
    }
    stem = f"{title}-cfr-{slug(u.number)}" + (f"--as-of-{as_of}" if as_of else "")
    return stem, front_matter(fm) + "\n" + u.markdown


def export_part(client: Client, title: str, part: str, out: Path, current: str | None = None,
                as_of: tuple[str, ...] = (), program: str = "", tags: tuple = (), layout: str = "nested",
                since: str | None = None) -> list[Path]:
    """Write the part's current sections and earlier versions. Returns written paths.

    as_of: write the version in force on each date, where it differs from the current text.
    since: write every distinct version in force at any time from that date on (each version once,
    named --as-of-<date it took effect>, or --as-of-<since> for the version already in force then).
    """
    current = current or client.latest_date(title)
    dates = section_dates(client.versions(title, part))
    raw = client.full_xml(title, current, part)
    cur = {u.number: u for u in iter_units(raw, title)}
    d = out / f"title-{title}" / f"part-{part}" if layout == "nested" else out
    d.mkdir(parents=True, exist_ok=True)
    written = []
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for n, u in cur.items():
        hist = [x for x in dates.get(n, []) if x <= current]
        stem, text = unit_doc(u, title, hist[-1] if hist else "", "", None, program, tags, retrieved)
        (d / f"{stem}.md").write_text(text); written.append(d / f"{stem}.md")
    done: set[tuple[str, str]] = set()  # (section, version start) already written

    def write_version(u: Unit, when: str) -> None:
        if u.number in cur and cur[u.number].markdown == u.markdown:
            return
        hist = dates.get(u.number, [])
        frm = max([x for x in hist if x <= when], default="")
        nxt = min([x for x in hist if x > when], default="")
        if (u.number, frm) in done:
            return
        done.add((u.number, frm))
        stem, text = unit_doc(u, title, frm, day_before(nxt), when, program, tags, retrieved)
        (d / f"{stem}.md").write_text(text); written.append(d / f"{stem}.md")

    query_dates = list(as_of)
    if since:
        starts = sorted({x for hist in dates.values() for x in hist if since < x < current})
        query_dates += [since] + starts
    for when in sorted(set(query_dates)):
        for u in iter_units(client.full_xml(title, when, part), title):
            write_version(u, when)
    meta = {"title": title, "part": part, "current": current, "as_of": list(as_of), "since": since, "program": program,
            "files": len(written), "retrieved": retrieved}
    (d / "_part.json").write_text(json.dumps(meta, indent=1))
    return written
