#!/usr/bin/env python3
"""Confere que o build do Vite serve em GitHub Pages de projeto (caminhos relativos)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> int:
    html_path = DIST / "index.html"
    if not html_path.exists():
        print("dist/index.html ausente. Rode npm run build.", file=sys.stderr)
        return 1
    if not (DIST / ".nojekyll").exists():
        print("dist/.nojekyll ausente.", file=sys.stderr)
        return 1
    html = html_path.read_text(encoding="utf-8")
    refs = re.findall(r'\b(?:src|href)="([^"]+)"', html)
    ruins = [r for r in refs if r.startswith("/") and not r.startswith("//")]
    if ruins:
        print("referências absolutas no index.html:", ", ".join(ruins), file=sys.stderr)
        return 1
    if not any(r.startswith("./") for r in refs):
        print("nenhum asset com caminho relativo:", refs, file=sys.stderr)
        return 1
    print("build com caminhos relativos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
