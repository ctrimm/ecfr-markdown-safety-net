import tempfile
import unittest
from pathlib import Path

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
            text = {n: (d / n).read_text() for n in names}
            self.assertIn("effective_from: 2020-01-01\neffective_to: 2024-02-29", text[names[0]])
            self.assertIn("effective_from: 2024-03-01\neffective_to: 2025-01-31", text[names[1]])
            self.assertIn("effective_from: 2025-02-01\neffective_to: \"\"", text[names[2]])
            self.assertFalse(list(d.glob("99-cfr-999-1--*.md")))  # unchanged section: current file only


if __name__ == "__main__":
    unittest.main()
