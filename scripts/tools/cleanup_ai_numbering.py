"""Clean AI tracking numbers from code comments.

Removes Phase/§/P0-N/D8c/US-N/NEW-N/DEV-N/IC-N/DC-N/SEC-N/AUDIT_VERIFICATION
prefixes from comments while preserving the actual technical content.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns to remove (with surrounding whitespace handling)
PATTERNS: list[tuple[str, str]] = [
    # Phase X Task Y (desc): → desc:
    (r'Phase\s+\d+(?:\.\d+)?(?:\s+Task\s+\d+(?:\.\d+)?)?\s*[（(][^)）]*[)）]\s*[:：]?\s*', ''),
    # Phase X: →
    (r'Phase\s+\d+(?:\.\d+)?(?:\s+Step\s+\d+)?\s*[:：]\s*', ''),
    # Phase X — →
    (r'Phase\s+\d+(?:\.\d+)?\s*—\s*', ''),
    # §X.Y desc — → desc —
    (r'§\d+(?:\.\d+)?\s*', ''),
    # (P0-N) or P0-N:
    (r'[（(]P\d+-\d+[)）]\s*', ''),
    (r'P\d+-\d+\s*(?:fix|闭环|校验|根治|治理|规范)\s*[:：]?\s*', ''),
    # D8c/D8f/D8i etc
    (r'D\d+[a-z]\s*(?:fix|闭环|校验|根治)\s*[:：]?\s*', ''),
    # US-N
    (r'US-\d+\s*', ''),
    # NEW-N, DEV-N
    (r'NEW-\d+\s*', ''),
    (r'DEV-\d+\s*', ''),
    # IC-N, DC-N, DF-N, IS-N
    (r'(?:IC|DC|DF|IS)-\d+\s*', ''),
    # SEC-N
    (r'SEC-\d+\s*', ''),
    # AUDIT_VERIFICATION §X.Y
    (r'AUDIT_VERIFICATION\s*§\d+(?:\.\d+)?\s*', ''),
    # CRON-03 etc
    (r'CRON-\d+\s*', ''),
    # PIPE-03 etc
    (r'PIPE-\d+\s*', ''),
    # (functional-review 2026-XX-XX):
    (r'[（(]functional-review\s+\d{4}-\d{2}-\d{2}[)）]\s*[:：]?\s*', ''),
    # clean trailing: — desc → — desc (keep)
    # Clean double spaces left after removal
    (r'  +', ' '),
    # Clean leading whitespace damage in comments
    (r'(#\s{2,})', '# '),
]

# Files to skip
SKIP_PATTERNS = ['test_', '__pycache__', '.venv', 'site-packages', '.planning']


def clean_line(line: str) -> str:
    """Clean AI tracking numbers from a single line."""
    # Only process comment lines or docstring content
    stripped = line.lstrip()
    is_comment = stripped.startswith('#')
    is_docstring_content = False  # We'll handle docstrings at file level

    if not is_comment and not is_docstring_content:
        return line

    original = line
    for pattern, replacement in PATTERNS:
        line = re.sub(pattern, replacement, line)

    # Clean up empty comments: "# " → remove line? No, keep empty comments as they
    # might be structural. Just clean double spaces.
    if line.strip() == '#' or line.strip() == '# :':
        return original  # Don't strip structural comment markers

    return line


def clean_file(filepath: Path) -> int:
    """Clean AI tracking numbers from a file. Returns number of lines changed."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return 0

    lines = content.split('\n')
    changed = 0
    new_lines = []

    in_docstring = False
    for line in lines:
        stripped = line.strip()

        # Track docstring state
        if '"""' in stripped or "'''" in stripped:
            count = stripped.count('"""') + stripped.count("'''")
            if count == 1:
                in_docstring = not in_docstring
            # If count == 2, it opens and closes on same line

        # Clean if it's a comment or inside a docstring
        if stripped.startswith('#') or in_docstring:
            new_line = clean_line(line)
            if new_line != line:
                changed += 1
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if changed:
        filepath.write_text('\n'.join(new_lines), encoding='utf-8')

    return changed


def main() -> None:
    root = Path('backend/app')
    total_changed = 0
    files_changed = 0

    for py_file in root.rglob('*.py'):
        # Skip test files and cache
        if any(skip in str(py_file) for skip in SKIP_PATTERNS):
            continue

        n = clean_file(py_file)
        if n:
            total_changed += n
            files_changed += 1
            print(f'  {py_file}: {n} lines cleaned')

    print(f'\nTotal: {total_changed} lines changed across {files_changed} files')


if __name__ == '__main__':
    main()
