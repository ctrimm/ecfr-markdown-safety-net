"""Tests for tools/build_feed.py - path mapping and feed generation.

No network, no git history needed: the feed build runs against a temp
directory holding a hand-written feed/changes.jsonl.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

TOOL = Path(__file__).resolve().parent.parent / "tools" / "build_feed.py"
spec = importlib.util.spec_from_file_location("build_feed", TOOL)
build_feed = importlib.util.module_from_spec(spec)
sys.modules["build_feed"] = build_feed
spec.loader.exec_module(build_feed)


class SectionPathTests(unittest.TestCase):
    def test_current_section(self):
        info = build_feed.parse_section_path(
            "corpus/title-7/part-273/7-cfr-273-9.md")
        self.assertEqual(info["citation"], "7 CFR 273.9")
        self.assertEqual(info["title_number"], 7)
        self.assertEqual(info["part"], 273)
        self.assertEqual(info["section"], "9")
        self.assertIsNone(info["version_date"])

    def test_historical_version(self):
        info = build_feed.parse_section_path(
            "corpus/title-42/part-435/42-cfr-435-1102--as-of-2024-03-01.md")
        self.assertEqual(info["citation"], "42 CFR 435.1102")
        self.assertEqual(info["version_date"], "2024-03-01")

    def test_appendix_files(self):
        info = build_feed.parse_section_path(
            "corpus/title-7/part-277/7-cfr-appendix-a-to-part-277.md")
        self.assertEqual(info["citation"], "7 CFR Part 277, Appendix A")
        self.assertEqual(info["section"], "appendix-a")
        info = build_feed.parse_section_path(
            "corpus/title-24/part-5/"
            "24-cfr-appendix-a-to-subpart-a-of-part-5--as-of-2024-03-04.md")
        self.assertIsNotNone(info)
        self.assertEqual(info["version_date"], "2024-03-04")

    def test_non_section_files_rejected(self):
        for path in (
            "corpus/index.md",
            "corpus/title-7/index.md",
            "corpus/title-7/part-273/_part.json",
            "corpus/manifest.json",
            "README.md",
        ):
            self.assertIsNone(build_feed.parse_section_path(path), path)


class FrontMatterTests(unittest.TestCase):
    def test_flat_keys(self):
        text = (
            "---\n"
            "type: PolicyDocument\n"
            'title: "7 CFR 273.9 Income and deductions"\n'
            "citation: 7 CFR 273.9\n"
            "resource: https://www.ecfr.gov/current/title-7/section-273.9\n"
            "effective_from: 2025-01-17\n"
            "---\n\n# body\n"
        )
        fields = build_feed.parse_front_matter(text)
        self.assertEqual(fields["citation"], "7 CFR 273.9")
        self.assertEqual(fields["title"], "7 CFR 273.9 Income and deductions")
        self.assertEqual(fields["effective_from"], "2025-01-17")


class BuildFeedTests(unittest.TestCase):
    def test_feed_from_log(self):
        entries = [
            {
                "date": "2026-10-24T00:00:00Z",
                "citation": "ecfr-markdown-safety-net",
                "title": "Change feed launched - corpus baseline",
                "heading": "",
                "title_number": "",
                "part": "",
                "section": "",
                "version_date": None,
                "change_type": "feed-launched",
                "path": "feed.xml",
                "effective_from": "",
                "effective_to": "",
                "ecfr_url": "",
                "link": "https://github.com/ctrimm/ecfr-markdown-safety-net",
                "guid": "urn:test:seed",
                "description": "Seed item.",
            },
            {
                "date": "2026-10-25T13:00:00Z",
                "citation": "7 CFR 273.9",
                "title": "7 CFR 273.9 Income and deductions",
                "heading": "Income and deductions",
                "title_number": 7,
                "part": 273,
                "section": "9",
                "version_date": None,
                "change_type": "modified",
                "path": "corpus/title-7/part-273/7-cfr-273-9.md",
                "effective_from": "2025-01-17",
                "effective_to": "",
                "ecfr_url": "https://www.ecfr.gov/current/title-7/section-273.9",
                "link": "https://github.com/ctrimm/ecfr-markdown-safety-net/blob/main/corpus/title-7/part-273/7-cfr-273-9.md",
                "guid": "urn:test:1",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "feed").mkdir()
            with (root / "feed" / "changes.jsonl").open(
                    "w", encoding="utf-8", newline="\n") as fh:
                for entry in entries:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count = build_feed.build_feed_xml(root)
            self.assertEqual(count, 2)
            channel = ET.parse(str(root / "feed.xml")).getroot().find("channel")
            items = channel.findall("item")
            self.assertEqual(len(items), 2)
            # Newest first.
            self.assertEqual(items[0].findtext("guid"), "urn:test:1")
            self.assertIn("7 CFR 273.9", items[0].findtext("title"))
            self.assertIn("modified", items[0].findtext("title"))
            self.assertIn("Income and deductions",
                          items[0].findtext("description"))


if __name__ == "__main__":
    unittest.main()
