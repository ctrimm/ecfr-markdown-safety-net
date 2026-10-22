"""The bundled corpus conforms to OKF v0.2 (GoogleCloudPlatform/knowledge-catalog okf/SPEC.md §11):
every concept document has frontmatter with a non-empty `type`, and reserved index.md files carry no
frontmatter except `okf_version` on the bundle root (§8). Standard library only, like the package."""
import re
import unittest
from pathlib import Path

CORPUS = Path(__file__).parent.parent / "corpus"
GENERATED = re.compile(r'generated: \{by: ecfr-markdown/[\w.]+(, at: "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")?\}')


@unittest.skipUnless(CORPUS.is_dir(), "no bundled corpus")
class CorpusOKFTests(unittest.TestCase):
    def test_documents(self):
        docs = [p for p in CORPUS.rglob("*.md") if p.name != "index.md"]
        self.assertTrue(docs)
        for p in docs:
            text = p.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n") and "\n---\n" in text, p)
            head = text[4:].split("\n---\n", 1)[0].splitlines()
            keys = {ln.split(":", 1)[0] for ln in head}
            self.assertRegex(next((ln for ln in head if ln.startswith("type: ")), ""), r"^type: \S", p)
            self.assertNotIn("timestamp", keys, p)  # v0.1 key, superseded by generated (§13.1)
            self.assertTrue(any(GENERATED.fullmatch(ln) for ln in head), p)
            self.assertEqual("status: deprecated" in head, "--as-of-" in p.name, p)

    def test_index_files(self):
        for p in CORPUS.rglob("index.md"):
            text = p.read_text(encoding="utf-8")
            if p.parent == CORPUS:
                self.assertTrue(text.startswith('---\nokf_version: "0.2"\n---\n'), p)
            else:
                self.assertFalse(text.startswith("---"), p)
            self.assertRegex(text, r"(?m)^# ", p)


if __name__ == "__main__":
    unittest.main()
