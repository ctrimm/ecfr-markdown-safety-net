"""eCFR XML -> Markdown.

The eCFR's XML nests DIV5 (part) > DIV6 (subpart) > DIV7 (subject group) >
DIV8 (section), with DIV9 for appendices. Inside a section: HEAD, P / FP
paragraphs with <I>/<E> emphasis, HD1-HD3/HED subheadings, tables (either
HTML-like TABLE/TR/TD or GPO's GPOTABLE/BOXHD/ROW/ENT), EXTRACT and NOTE
blocks, CITA (source citation), EDNOTE, FTNT footnotes, and MATH/img for
formulas and figures that have no text form.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_WS = re.compile(r"[ \t\r\n]+")


@dataclass
class Unit:
    """One section or appendix, rendered."""
    number: str          # "273.9" or "Appendix A to Part 273"
    heading: str         # "§ 273.9 Income and deductions."
    kind: str            # "section" | "appendix"
    part: str
    subpart: str = ""    # "Subpart A—General Provisions"
    subject_group: str = ""
    markdown: str = ""
    citation: str = ""
    extra: dict = field(default_factory=dict)


def inline(el: ET.Element) -> str:
    out = [el.text or ""]
    for ch in el:
        t = inline(ch)
        if ch.tag in ("I", "E", "EM"):
            t = f"*{t.strip()}*" if t.strip() else t
        elif ch.tag in ("B",):
            t = f"**{t.strip()}**" if t.strip() else t
        elif ch.tag == "SU":
            t = f"^{t.strip()}"
        elif ch.tag in ("FTREF",):
            t = ""
        elif ch.tag == "br":
            t = " "
        out.append(t)
        out.append(ch.tail or "")
    return _WS.sub(" ", "".join(out))


def _md_table(rows: list[list[str]]) -> str:
    rows = [[c.replace("|", "\\|") for c in r] for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    return "\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w] +
                     ["| " + " | ".join(r) + " |" for r in rows[1:]])


def table(el: ET.Element) -> str:
    if el.find(".//ROW") is not None:  # GPO table
        head = [inline(c).strip() for c in el.iter("CHED")]
        rows = [[inline(c).strip() for c in row if c.tag == "ENT"] for row in el.iter("ROW")]
        return _md_table(([head] if head else []) + rows)
    rows = [[inline(c).strip() for c in tr if c.tag in ("TD", "TH")] for tr in el.iter("TR")]
    return _md_table(rows)


def blocks(el: ET.Element, depth: int = 0) -> list[str]:
    """Markdown blocks for a container's children."""
    out: list[str] = []
    for ch in el:
        tag = ch.tag
        if tag == "HEAD":
            continue
        if tag == "P" or tag.startswith("FP"):
            t = inline(ch).strip()
            if t:
                out.append(t)
        elif tag in ("HD1", "HD2", "HD3", "HED", "HD"):
            t = inline(ch).strip()
            if t:
                out.append(f"## {t}")
        elif tag in ("TABLE", "GPOTABLE") or (tag == "DIV" and ch.find(".//TR") is not None):
            t = table(ch)
            if t:
                out.append(t)
        elif tag in ("EXTRACT", "NOTE", "EXAMPLE"):
            inner = blocks(ch, depth + 1)
            if inner:
                label = {"NOTE": "Note: ", "EXAMPLE": "Example: "}.get(tag, "")
                out.append("\n>\n".join("> " + (label if i == 0 else "") + b.replace("\n", "\n> ")
                                        for i, b in enumerate(inner)))
        elif tag == "CITA":
            out.append(f"> Source: {inline(ch).strip()}")
        elif tag == "SOURCE":
            out.append(f"> Source: {inline(ch).strip()}")
        elif tag == "AUTH":
            out.append(f"> Authority: {inline(ch).strip()}")
        elif tag == "EDNOTE":
            out.append(f"> Editorial note: {inline(ch).strip()}")
        elif tag == "FTNT":
            t = inline(ch).strip()
            if t:
                out.append(f"[Footnote] {t}")
        elif tag in ("MATH", "img", "GPH") or ch.find(".//img") is not None or ch.find(".//MATH") is not None:
            out.append("*[A formula or figure appears here in the official text; see the source link.]*")
        elif tag == "PSPACE" or tag.startswith("PSPACE"):
            t = inline(ch).strip()
            if t:
                out.append(t)
        elif tag.startswith("DIV"):
            continue  # nested units are handled by iter_units
        else:
            t = inline(ch).strip()
            if t:
                out.append(t)
    return out


def render_unit(el: ET.Element) -> str:
    head = inline(el.find("HEAD")).strip() if el.find("HEAD") is not None else el.attrib.get("N", "")
    return "\n\n".join([f"# {head}"] + blocks(el)).strip() + "\n"


def iter_units(xml: bytes, title: int | str):
    """Yield a Unit for every section (DIV8) and appendix (DIV9) in a part's XML."""
    root = ET.fromstring(xml)
    part = ""

    def walk(el, subpart="", group=""):
        nonlocal part
        for ch in el:
            if not ch.tag.startswith("DIV"):
                continue
            typ = ch.attrib.get("TYPE", "")
            head = inline(ch.find("HEAD")).strip() if ch.find("HEAD") is not None else ""
            if typ == "PART":
                part = ch.attrib.get("N", part)
                yield from walk(ch, subpart, group)
            elif typ == "SUBPART":
                yield from walk(ch, head, "")
            elif typ == "SUBJGRP":
                yield from walk(ch, subpart, head)
            elif typ in ("SECTION", "APPENDIX"):
                n = ch.attrib.get("N", head)
                if "[Reserved]" in head and len([c for c in ch if c.tag != "HEAD"]) == 0:
                    continue
                kind = "section" if typ == "SECTION" else "appendix"
                cite = f"{title} CFR {n}" if kind == "section" else f"{title} CFR Part {part}, {n}"
                yield Unit(number=n, heading=head, kind=kind, part=part, subpart=subpart,
                           subject_group=group, markdown=render_unit(ch), citation=cite)
            else:
                yield from walk(ch, subpart, group)

    if root.tag.startswith("DIV") and root.attrib.get("TYPE") == "PART":
        part = root.attrib.get("N", "")
    yield from walk(root)
