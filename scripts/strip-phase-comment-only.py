#!/usr/bin/env python3
"""Strip ONLY `// Phase X.Y` / `/* Phase X.Y */` comment markers.

Safer than the bulk version: only touches comments, never field/type names.
Skips files containing TS interface declarations to be doubly safe.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\LiShuai\Desktop\Agents\starmap\frontend\src")

# match "Phase <number>" optionally followed by .digits / -digits, then a separator
PATTERNS: list[tuple[re.Pattern, str]] = [
    # Inline comment with Phase prefix: `// Phase 3.8.11: ...`
    (re.compile(r"(//)\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\s*"), r"\1 "),
    # Block comment opening with Phase prefix: `/* Phase 3.8.5: ... */`
    (re.compile(r"(/\*)\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\s*"), r"\1 "),
    # Full-width variant: `（Phase 23 ...）` -> `（）`
    (re.compile(r"（\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?[^）]*）"), "（）"),
    # Paren variant: `(Phase 24 §5.2)` already gone in v1, leftover may be (Phase 24)
    (re.compile(r"\(\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?[^)]*\)"), "()"),
    # § chapter refs inside comments/strings (we keep §X.Y in plain text outside comments for now)
    (re.compile(r"\s*§\s*\d+(?:\.\d+)+\s*"), " "),
    # Trailing comma/space + Phase 24 / Phase 26+
    (re.compile(r",\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?(?:\s*\+\s*)?\b"), ""),
    # Standalone "Phase " prefix in Vue templates (string-only) — only in template strings
    (re.compile(r"([\"'`])Phase\s+\d+(?:\.\d+)*(?:\s*-\s*\d+)?\s+"), r"\1"),
]


def process_file(p: Path) -> tuple[bool, int]:
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, 0
    original = text
    hits = 0
    for pat, repl in PATTERNS:
        new_text, n = pat.subn(repl, text)
        if n > 0:
            text = new_text
            hits += n
    if text != original:
        p.write_text(text, encoding="utf-8")
        return True, hits
    return False, 0


def main() -> None:
    total_changed = 0
    total_hits = 0
    changed_files: list[tuple[str, int]] = []
    for ext in ("*.vue", "*.ts"):
        for p in ROOT.rglob(ext):
            changed, hits = process_file(p)
            if changed:
                total_changed += 1
                total_hits += hits
                changed_files.append((str(p.relative_to(ROOT.parent)), hits))
    print(f"changed_files={total_changed}  total_substitutions={total_hits}")
    for name, hits in sorted(changed_files, key=lambda x: -x[1])[:40]:
        print(f"  {hits:4d}  {name}")


if __name__ == "__main__":
    main()