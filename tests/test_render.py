import unittest
from pathlib import Path

from ecfr_markdown.export import section_dates, unit_doc
from ecfr_markdown.render import iter_units

XML = (Path(__file__).parent / "fixtures/mini_part.xml").read_bytes()


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.units = {u.number: u for u in iter_units(XML, 99)}

    def test_units_found_and_reserved_skipped(self):
        self.assertEqual(sorted(self.units), ["999.1", "999.2", "Appendix A to Part 999"])

    def test_context(self):
        u = self.units["999.2"]
        self.assertEqual(u.part, "999")
        self.assertEqual(u.subpart, "Subpart A—General")
        self.assertEqual(u.subject_group, "Eligibility")
        self.assertEqual(u.citation, "99 CFR 999.2")
        self.assertEqual(self.units["Appendix A to Part 999"].kind, "appendix")

    def test_markdown(self):
        md = self.units["999.1"].markdown
        self.assertTrue(md.startswith("# § 999.1 Definitions."))
        self.assertIn("(a) *Household* means a group of people who buy food together.", md)
        self.assertIn("counted *monthly*, see footnote.", md)
        self.assertIn("| Size | Limit |", md)
        self.assertIn("| 2 | $1,400 |", md)
        self.assertIn("> Quoted text.", md)
        self.assertIn("[Footnote] 1 Footnote text.", md)
        self.assertIn("> Source: [81 FR 100, Jan. 1, 2016]", md)
        self.assertIn("| x \\| y | z |", self.units["999.2"].markdown)

    def test_versions_and_front_matter(self):
        dates = section_dates([{"identifier": "999.1", "date": "2020-01-01"}, {"identifier": "999.1", "date": "2024-11-18"}])
        self.assertEqual(dates["999.1"], ["2020-01-01", "2024-11-18"])
        stem, text = unit_doc(self.units["999.1"], "99", "2020-01-01", "2024-11-18", "2024-06-01", "Example", ("example",))
        self.assertEqual(stem, "99-cfr-999-1--as-of-2024-06-01")
        self.assertIn("type: PolicyDocument", text)
        self.assertIn("effective_from: 2020-01-01", text)
        self.assertIn("effective_to: 2024-11-18", text)
        self.assertIn('resource: "https://www.ecfr.gov/on/2024-06-01/title-99/section-999.1"', text)
        self.assertIn("(version in force 2024-06-01)", text)


if __name__ == "__main__":
    unittest.main()
