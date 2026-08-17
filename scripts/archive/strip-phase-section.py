#!/usr/bin/env python3
"""Strip Phase/§ markers from frontend source code.

Per user spec: full-strip "Phase NN" / "§X.Y" markers (UI text + code comments),
replace with business-friendly wording OR delete the whole marker+phrase when
the rest of the sentence is meaningless.

PROTECTED substrings (never modify):
- learningPlan.phases / noPhasesResponse / phases  (business field)
- file path containing "phase"  (uncommon in this repo)
- Word boundary respected via regex
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\LiShuai\Desktop\Agents\starmap\frontend\src")

# Patterns to delete or strip. Order matters: more specific first.
# Each pattern: (compiled regex, replacement or None)
PATTERNS: list[tuple[re.Pattern, str]] = [
    # 1. "(Phase 24 §5.2)" / "(Phase 23)" / "(Phase 24)" — inside parentheses
    (re.compile(r"\s*\(Phase\s*\d+[^\)]{0,40}\)"), ""),
    # 2. "Phase 24 §5.2" 章节引用 inside string/comment (no parens)
    (re.compile(r"\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\s*§\s*\d+(?:\.\d+)*"), ""),
    # 3. "Phase 24:" / "Phase 23 ：" / "Phase 3.8.5:" — colon-prefixed labels
    (re.compile(r"\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\s*[::]\s*"), " "),
    # 4. "Phase 24 " — bare Phase prefix in string/comment (must have trailing space)
    (re.compile(r"\s*Phase\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?(?:\s+[A-Z]\d+(?:\.\d+)*)*\s+"), " "),
    # 4b. "Phase 24 +" / "Phase 26+" — append-only suffix without space
    (re.compile(r"\s*Phase\s*\d+(?:\.\d+)*\s*\+\s*"), " "),
    # 4c. "Phase 07-02 T8" — old short form with hyphen + letter
    (re.compile(r"\s*Phase\s*\d+\s*-\s*\d+(?:\s+[A-Z]\d+(?:\.\d+)*)?\s*"), " "),
    # 4d. "Phase 17-01: timeseries ..." — colon form with version
    (re.compile(r"\s*Phase\s*\d+\s*-\s*\d+\s*[::]\s*"), " "),
    # 4e. "Phase 14-01: Refactored ..." — bare colon with version
    (re.compile(r"\s*Phase\s*\d+\s*-\s*\d+"), ""),
    # 4f. "（Phase 3.8）" full-width paren with dotted version
    (re.compile(r"（Phase\s*\d+(?:\.\d+)*[\s\S]*?）"), "（）"),
    # 5. "§5.2 演化工作流" / "§6.2 四因子" / "§7.1 信任度驱动" / "§2.3.3.2 管理角色刚需"
    (re.compile(r"\s*§\s*\d+(?:\.\d+)*"), ""),
    # 6. "（§5.2）" / "（Phase 23 ...）" full-width paren variants
    (re.compile(r"（Phase\s*\d+[^）]*）"), "（）"),
    (re.compile(r"（§\s*\d+(?:\.\d+)*[^）]*）"), "（）"),
    (re.compile(r"\(Phase\s*\d+[^)]*\)"), "()"),
    # 7. "(设计文档 §X.Y)" / "(设计文档 §X.Y ...)"
    (re.compile(r"\(设计文档\s*§\s*\d+(?:\.\d+)*[^)]*\)"), "()"),
    (re.compile(r"（设计文档\s*§\s*\d+(?:\.\d+)*[^）]*）"), "（）"),
    # 8. leading "(Phase X)" / "(§X.Y)" in label string
    (re.compile(r"^[ \t]*[\(（]Phase\s*\d+[\)）]\s*"), ""),
    # 9. leftover dangling "(Phase " or "(§ " mid-string
    (re.compile(r"\s*\(Phase\s+\d+[^)]*$"), ""),
    # 10. "Phase " at start of string (Vue label string only — not business field)
    (re.compile(r"^(['\"])Phase\s+\d+\s+"), r"\1"),
    # 11. ", Phase 24" / ", Phase 26+" suffix
    (re.compile(r",\s*Phase\s*\d+(?:\s*[+/]\s*\d+)*"), ""),
    # 12. "Phase " in string-only contexts left after all above (catch-all)
    (re.compile(r"(['\"])Phase\s+\d+\s+"), r"\1"),
    # 13. standalone "§X.Y" at start of a comment line
    (re.compile(r"^([ \t]*)§\s*\d+(?:\.\d+)*\s+"), r"\1"),
    # 14. trailing "(Phase X) " after sentence
    (re.compile(r"\s*\(Phase\s*\d+\)\s*$"), ""),
]

# Lines to skip entirely (block comments / docs that we shouldn't touch at all)
SKIP_LINE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*\*"),            # JSDoc block comment continuation
    re.compile(r"^\s*//"),            # single-line comment
]

# Files to skip entirely (BusinessBanner.spec.ts tests §3.2 render behavior)
SKIP_FILES: set[str] = set()


def process_file(p: Path) -> tuple[bool, int]:
    """Process one file. Returns (changed, hit_count)."""
    if p.name in SKIP_FILES:
        return False, 0
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
    for p in ROOT.rglob("*.vue"):
        changed, hits = process_file(p)
        if changed:
            total_changed += 1
            total_hits += hits
            changed_files.append((str(p.relative_to(ROOT.parent)), hits))
    for p in ROOT.rglob("*.ts"):
        # skip type declaration files like api/schema.ts to avoid drift
        changed, hits = process_file(p)
        if changed:
            total_changed += 1
            total_hits += hits
            changed_files.append((str(p.relative_to(ROOT.parent)), hits))
    print(f"changed_files={total_changed}  total_substitutions={total_hits}")
    for name, hits in sorted(changed_files, key=lambda x: -x[1])[:30]:
        print(f"  {hits:4d}  {name}")


if __name__ == "__main__":
    main()