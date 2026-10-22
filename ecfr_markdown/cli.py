"""ecfr-md: export eCFR regulations to Markdown.

  ecfr-md part --title 7 --part 273 --out out/ [--date 2026-10-08] [--since 2024-01-01] [--as-of 2024-06-01]
  ecfr-md catalog programs.json --out corpus/ [--since 2024-01-01] [--only snap,wic]
  ecfr-md index corpus/          # write index.md per directory + manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import Client
from .export import export_part, front_matter


def _unquote(v: str) -> str:
    """Undo export._yaml's double-quoting (it only escapes backslashes and quotes, a subset of JSON)."""
    return json.loads(v) if len(v) > 1 and v[0] == v[-1] == '"' else v


def build_index(root: Path) -> dict:
    """index.md (type: Index) per directory and a manifest.json of every document."""
    manifest = []
    for d in sorted([root, *[p for p in root.rglob("*") if p.is_dir()]]):
        docs = sorted(p for p in d.glob("*.md") if p.name != "index.md")
        subs = sorted(p for p in d.iterdir() if p.is_dir())
        if not docs and not subs:
            continue
        rel = d.relative_to(root).as_posix()
        lines = [front_matter({"type": "Index", "title": f"Index of {'corpus' if rel == '.' else rel}"}), ""]
        lines += [f"- [{s.name}/]({s.name}/index.md)" for s in subs]
        for p in docs:
            title = next((_unquote(ln[7:].strip()) for ln in p.read_text(encoding="utf-8").splitlines()[:6]
                          if ln.startswith("title: ")), p.stem)
            lines.append(f"- [{title}]({p.name})")
            manifest.append({"path": p.relative_to(root).as_posix(), "title": title})
        (d / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return {"documents": len(manifest)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ecfr-md")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("part", help="export one CFR part")
    p.add_argument("--title", required=True); p.add_argument("--part", required=True)
    p.add_argument("--out", required=True); p.add_argument("--date", default=None)
    p.add_argument("--as-of", action="append", default=[]); p.add_argument("--program", default="")
    p.add_argument("--since", default=None, help="also write every version in force since this date")
    p.add_argument("--flat", action="store_true", help="write files directly into --out")
    c = sub.add_parser("catalog", help="export every part listed in a catalog JSON")
    c.add_argument("catalog"); c.add_argument("--out", required=True); c.add_argument("--as-of", action="append", default=[])
    c.add_argument("--only", default="", help="comma-separated program keys")
    c.add_argument("--since", default=None, help="also write every version in force since this date")
    i = sub.add_parser("index", help="write index.md files and manifest.json")
    i.add_argument("root")
    a = ap.parse_args(argv)
    cl = Client()
    if a.cmd == "part":
        w = export_part(cl, a.title, a.part, Path(a.out), a.date, tuple(a.as_of), a.program,
                        layout="flat" if a.flat else "nested", since=a.since)
        print(f"wrote {len(w)} files")
    elif a.cmd == "catalog":
        cat = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
        only = set(filter(None, a.only.split(",")))
        for key, prog in cat["programs"].items():
            if only and key not in only:
                continue
            for title, parts in prog["cfr"].items():
                for part in parts:
                    try:
                        w = export_part(cl, title, str(part), Path(a.out), None, tuple(a.as_of), prog["name"],
                                        tags=tuple(prog.get("tags", [key])), since=a.since)
                        print(f"{key}: {title} CFR {part}: {len(w)} files", flush=True)
                    except Exception as e:  # keep going; report
                        print(f"{key}: {title} CFR {part}: FAILED {e}", file=sys.stderr, flush=True)
        print(build_index(Path(a.out)))
    elif a.cmd == "index":
        print(build_index(Path(a.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
