#!/usr/bin/env python3
"""RSS change feed for the ecfr-markdown-safety-net corpus.

Whenever corpus changes land on main, the feed workflow
(.github/workflows/feed.yml) runs this tool to:

  1. record: diff two commits (git diff --name-status over corpus/),
     parse each changed section file's OKF front matter, and append one
     JSON object per changed section to feed/changes.jsonl (append-only).
  2. build: regenerate feed.xml (RSS 2.0, newest MAX_ITEMS items) from
     feed/changes.jsonl.

Standard library only, like the rest of this repo. All file IO is UTF-8.

Usage:
    python3 tools/build_feed.py record --before SHA --after SHA [--date ISO]
    python3 tools/build_feed.py build

Run from anywhere; paths resolve relative to the repository root (the
parent of this file's directory), or pass --repo-root.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_URL = "https://github.com/ctrimm/ecfr-markdown-safety-net"
FEED_URL = (
    "https://raw.githubusercontent.com/ctrimm/ecfr-markdown-safety-net"
    "/main/feed.xml"
)
FEED_TITLE = "ecfr-markdown-safety-net - corpus changes"
FEED_DESCRIPTION = (
    "Changes to the safety-net slice of the eCFR as Markdown: one item per "
    "CFR section file added, modified or deleted on main. 15 programs, "
    "35 CFR parts. A convenience copy, not the official legal edition - "
    "cite the official CFR or the Federal Register for legal purposes."
)
MAX_ITEMS = 200
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# corpus/title-7/part-273/7-cfr-273-9.md
# corpus/title-7/part-273/7-cfr-273-9--as-of-2024-11-18.md
SECTION_RE = re.compile(
    r"^corpus/title-(?P<title>\d+)/part-(?P<part>\d+)/"
    r"(?P=title)-cfr-(?P=part)-(?P<section>[0-9A-Za-z.\-]+?)"
    r"(?:--as-of-(?P<version>\d{4}-\d{2}-\d{2}))?\.md$"
)

# Appendices are their own files too:
# corpus/title-7/part-277/7-cfr-appendix-a-to-part-277.md
# corpus/title-24/part-5/24-cfr-appendix-a-to-subpart-a-of-part-5--as-of-2024-03-04.md
APPENDIX_RE = re.compile(
    r"^corpus/title-(?P<title>\d+)/part-(?P<part>\d+)/"
    r"(?P=title)-cfr-appendix(?:-(?P<letter>[a-z0-9]+))?"
    r"-to-(?:subpart-[a-z0-9]+-of-)?part-(?P=part)"
    r"(?:--as-of-(?P<version>\d{4}-\d{2}-\d{2}))?\.md$"
)

STATUS_TO_CHANGE = {"A": "added", "M": "modified", "D": "deleted", "T": "modified"}


def parse_section_path(path):
    """Map a corpus path to its citation parts, or None if not a section."""
    m = SECTION_RE.match(path)
    if m:
        title = int(m.group("title"))
        part = int(m.group("part"))
        section = m.group("section")
        return {
            "title_number": title,
            "part": part,
            "section": section,
            "citation": "%d CFR %s.%s" % (title, part, section),
            "version_date": m.group("version"),
        }
    m = APPENDIX_RE.match(path)
    if m:
        title = int(m.group("title"))
        part = int(m.group("part"))
        letter = m.group("letter")
        section = "appendix-" + letter if letter else "appendix"
        if letter:
            citation = "%d CFR Part %d, Appendix %s" % (
                title, part, letter.upper())
        else:
            citation = "%d CFR Part %d, Appendix" % (title, part)
        return {
            "title_number": title,
            "part": part,
            "section": section,
            "citation": citation,
            "version_date": m.group("version"),
        }
    return None


def parse_front_matter(text):
    """Pull the flat keys we need out of a file's YAML front matter.

    The corpus front matter is machine-generated with simple `key: value`
    lines, so a line scan is enough (no YAML dependency - stdlib only).
    """
    fields = {}
    if not text.startswith("---"):
        return fields
    end = text.find("\n---", 3)
    if end == -1:
        return fields
    for line in text[3:end].splitlines():
        if ":" not in line or line.startswith((" ", "\t", "-")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise SystemExit("git %s failed: %s" % (args[0], result.stderr.strip()))
    return result.stdout


def read_file_at(repo_root, rev, path):
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", "%s:%s" % (rev, path)],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def changed_corpus_files(repo_root, before, after):
    """Yield (status, path) for every corpus file changed between two revs."""
    out = git(
        repo_root, "diff", "--name-status", "-z", "--no-renames",
        before, after, "--", "corpus/",
    )
    tokens = [t for t in out.split("\0") if t]
    pairs = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        path = tokens[i + 1] if i + 1 < len(tokens) else ""
        i += 2
        if path:
            pairs.append((status, path))
    return sorted(pairs, key=lambda p: p[1])


def commit_date(repo_root, rev):
    raw = git(repo_root, "log", "-1", "--format=%cI", rev).strip()
    return raw or None


def describe_entry(entry):
    if entry.get("description"):
        return entry["description"]
    bits = ["%s was %s in the corpus." % (entry["citation"], entry["change_type"])]
    if entry.get("heading"):
        bits.append("Section heading: %s." % entry["heading"])
    section = str(entry.get("section") or "")
    if section.startswith("appendix"):
        bits.append(
            "Title %s, Part %s, %s."
            % (entry.get("title_number"), entry.get("part"),
               section.replace("-", " ").capitalize())
        )
    else:
        bits.append(
            "Title %s, Part %s, Section %s."
            % (entry.get("title_number"), entry.get("part"), section)
        )
    if entry.get("version_date"):
        bits.append(
            "This file is the historical version in force from %s."
            % entry["version_date"]
        )
    elif entry.get("effective_from"):
        bits.append("Text in force since %s." % entry["effective_from"])
    if entry.get("effective_to"):
        bits.append("In force until %s." % entry["effective_to"])
    bits.append("File: %s" % entry["path"])
    if entry.get("ecfr_url"):
        bits.append("Official text: %s" % entry["ecfr_url"])
    return " ".join(bits)


def record_changes(repo_root, before, after, date=None):
    """Append entries for sections changed between two commits."""
    if before and set(before) == {"0"}:
        before = EMPTY_TREE
    if not date:
        date = commit_date(repo_root, after)
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    log_path = repo_root / "feed" / "changes.jsonl"
    existing = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.add(json.loads(line)["guid"])

    new_entries = []
    for status, path in changed_corpus_files(repo_root, before, after):
        info = parse_section_path(path)
        if info is None:
            continue  # index.md, _part.json and friends are not sections
        change_type = STATUS_TO_CHANGE.get(status)
        if change_type is None:
            continue
        rev = before if change_type == "deleted" else after
        fields = parse_front_matter(read_file_at(repo_root, rev, path))
        heading = ""
        title_field = fields.get("title", "")
        citation = fields.get("citation", info["citation"])
        if title_field.startswith(citation):
            heading = title_field[len(citation):].strip()
        ecfr_url = fields.get("resource", "")
        if change_type == "deleted":
            link = "%s/commit/%s" % (REPO_URL, after)
        else:
            link = "%s/blob/main/%s" % (REPO_URL, path)
        guid = "urn:ecfr-markdown-safety-net:%s@%s#%s" % (path, date, change_type)
        if guid in existing:
            continue
        entry = {
            "date": date,
            "citation": citation,
            "title": title_field or citation,
            "heading": heading,
            "title_number": info["title_number"],
            "part": info["part"],
            "section": info["section"],
            "version_date": info["version_date"],
            "change_type": change_type,
            "path": path,
            "effective_from": fields.get("effective_from", ""),
            "effective_to": fields.get("effective_to", ""),
            "ecfr_url": ecfr_url,
            "link": link,
            "guid": guid,
        }
        entry["description"] = describe_entry(entry)
        new_entries.append(entry)

    if new_entries:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as fh:
            for entry in new_entries:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
                fh.write("\n")
    return new_entries


def load_log(repo_root):
    log_path = repo_root / "feed" / "changes.jsonl"
    entries = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
    entries.sort(
        key=lambda e: (e.get("date", ""), e.get("path", ""), e.get("guid", "")),
        reverse=True,
    )
    return entries


def parse_date(value):
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def rfc822(value):
    dt = parse_date(value)
    if dt is None:
        dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return format_datetime(dt.astimezone(timezone.utc))


def build_feed_xml(repo_root):
    """Regenerate feed.xml from the change log. Returns the item count."""
    entries = load_log(repo_root)
    items = entries[:MAX_ITEMS]

    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = FEED_TITLE
    ET.SubElement(channel, "link").text = REPO_URL
    ET.SubElement(channel, "description").text = FEED_DESCRIPTION
    ET.SubElement(channel, "language").text = "en-us"
    if entries:
        ET.SubElement(channel, "lastBuildDate").text = rfc822(entries[0]["date"])
    self_link = ET.SubElement(
        channel, "{http://www.w3.org/2005/Atom}link",
        {"href": FEED_URL, "rel": "self", "type": "application/rss+xml"},
    )
    self_link.text = None

    for entry in items:
        item = ET.SubElement(channel, "item")
        title = entry.get("title") or entry.get("citation", "")
        change_type = entry.get("change_type", "changed")
        if change_type == "feed-launched":
            ET.SubElement(item, "title").text = title
        else:
            ET.SubElement(item, "title").text = "%s - %s" % (title, change_type)
        ET.SubElement(item, "link").text = entry.get("link", REPO_URL)
        guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
        guid.text = entry.get("guid", "")
        ET.SubElement(item, "pubDate").text = rfc822(entry.get("date", ""))
        ET.SubElement(item, "description").text = describe_entry(entry)
        change_cat = ET.SubElement(item, "category")
        change_cat.text = entry.get("change_type", "")
        if entry.get("title_number") and entry.get("part"):
            part_cat = ET.SubElement(item, "category")
            part_cat.text = "Title %s Part %s" % (
                entry["title_number"], entry["part"])

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    out_path = repo_root / "feed.xml"
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    return len(items)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", default=None,
        help="repository root (default: parent of this file's directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="record changes between two commits")
    rec.add_argument("--before", required=True)
    rec.add_argument("--after", required=True)
    rec.add_argument("--date", default=None,
                     help="ISO date for the entries (default: commit date)")
    sub.add_parser("build", help="regenerate feed.xml from the change log")
    args = parser.parse_args(argv)

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent

    if args.command == "record":
        new_entries = record_changes(
            repo_root, args.before, args.after, date=args.date)
        count = build_feed_xml(repo_root)
        print("recorded %d new change(s); feed now holds %d item(s)"
              % (len(new_entries), count))
    else:
        count = build_feed_xml(repo_root)
        print("feed rebuilt with %d item(s)" % count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
