import tempfile
import unittest
from pathlib import Path

import json

from ecfr_markdown.cli import build_index
from ecfr_markdown.client import Client
from ecfr_markdown.export import day_before, export_part

XML = (Path(__file__).parent / "fixtures/mini_part.xml").read_bytes()


class FakeClient:
    """999.2 amended on 2024-03-01 and 2025-02-01; the text differs by date."""

    def latest_date(self, title):
        return "2026-01-01"

    def versions(self, title, part):
        return [{"identifier": "999.1", "date": "2020-01-01"},
                {"identifier": "999.2", "date": "2020-01-01"},
                {"identifier": "999.2", "date": "2024-03-01"},
                {"identifier": "999.2", "date": "2025-02-01"}]

    def full_xml(self, title, date, part):
        tag = "v3" if date >= "2025-02-01" else "v2" if date >= "2024-03-01" else "v1"
        return XML.replace(b"Income limits.", f"Income limits ({tag}).".encode())


class VersionTests(unittest.TestCase):
    def test_day_before(self):
        self.assertEqual(day_before("2025-03-01"), "2025-02-28")
        self.assertEqual(day_before(""), "")

    def test_since_writes_each_version_once_with_contiguous_dates(self):
        with tempfile.TemporaryDirectory() as t:
            export_part(FakeClient(), "99", "999", Path(t), since="2024-01-01")
            d = Path(t) / "title-99" / "part-999"
            names = sorted(p.name for p in d.glob("99-cfr-999-2*.md"))
            self.assertEqual(names, ["99-cfr-999-2--as-of-2024-01-01.md", "99-cfr-999-2--as-of-2024-03-01.md",
                                     "99-cfr-999-2.md"])
            text = {n: (d / n).read_text(encoding="utf-8") for n in names}
            self.assertIn("effective_from: 2020-01-01\neffective_to: 2024-02-29", text[names[0]])
            self.assertIn("effective_from: 2024-03-01\neffective_to: 2025-01-31", text[names[1]])
            self.assertIn("effective_from: 2025-02-01\neffective_to: \"\"", text[names[2]])
            self.assertFalse(list(d.glob("99-cfr-999-1--*.md")))  # unchanged section: current file only

    def test_reexport_keeps_unchanged_files_and_prunes_stale_ones(self):
        with tempfile.TemporaryDirectory() as t:
            export_part(FakeClient(), "99", "999", Path(t), since="2024-01-01")
            d = Path(t) / "title-99" / "part-999"
            cur = d / "99-cfr-999-1.md"
            before = cur.read_text(encoding="utf-8")
            (d / "99-cfr-999-9.md").write_text("gone from the CFR", encoding="utf-8")
            export_part(FakeClient(), "99", "999", Path(t))  # no --since this time
            self.assertEqual(cur.read_text(encoding="utf-8"), before)  # same text: timestamp not bumped
            self.assertFalse((d / "99-cfr-999-9.md").exists())
            self.assertFalse(list(d.glob("*--as-of-*.md")))

    def test_index_titles_and_posix_paths(self):
        with tempfile.TemporaryDirectory() as t:
            export_part(FakeClient(), "99", "999", Path(t))
            build_index(Path(t))
            root = (Path(t) / "index.md").read_text(encoding="utf-8")
            self.assertIn("title: Index of corpus", root)
            manifest = json.loads((Path(t) / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn({"path": "title-99/part-999/99-cfr-999-1.md", "title": "99 CFR 999.1 Definitions"}, manifest)


class PagingTests(unittest.TestCase):
    def test_versions_reads_every_page(self):
        pages = {1: [{"identifier": "1.1", "date": "2020-01-01"}], 2: [{"identifier": "1.2", "date": "2021-01-01"}]}

        class Paged(Client):
            def _get(self, path, params=None, accept="application/json"):
                return json.dumps({"content_versions": pages[params["page"]],
                                   "meta": {"page": str(params["page"]), "total_pages": "2"}}).encode()

        self.assertEqual([v["identifier"] for v in Paged().versions(1, "1")], ["1.1", "1.2"])


if __name__ == "__main__":
    unittest.main()
