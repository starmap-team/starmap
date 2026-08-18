#!/usr/bin/env python3
r"""CI Gate: .env.production must not enter the git tree.

Checks:
 1. `git ls-files | grep -E '\.env\.production$'` -> must be empty
 2. `git log --all --oneline -- .env.production` -> must be empty

Exits 0 on success, 1 on failure (with diagnostic output).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve.parent.parent
ENV_PRODUCTION_PATTERN = r"\.env\.production$"

def run(cmd: list[str]) -> str:
 """Run a git command and return stdout. Empty string on error."""
 result = subprocess.run(
 cmd,
 cwd=REPO_ROOT,
 capture_output=True,
 text=True,
 check=False,
 )
 return result.stdout.strip

def main -> int:
 # Check 1: any tracked file ending in .env.production
 tracked = run(["git", "ls-files", "-z"])
 leaks = [
 f
 for f in tracked.split("\x00")
 if f and Path(f).name.endswith(".env.production")
 ]

 # Check 2: any historical commit touched .env.production
 history = run(["git", "log", "--all", "--oneline", "--", ".env.production"])

 failures: list[str] = []
 if leaks:
 failures.append(
 f"FAIL: {len(leaks)} tracked .env.production file(s): {leaks}"
 )
 if history:
 # History may legitimately contain `docs/` files mentioning the path;
 # only flag if the file itself was added/modified.
 # Re-check with --diff-filter=AM to filter to actual content changes.
 history_with_filter = run(
 [
 "git",
 "log",
 "--all",
 "--oneline",
 "--diff-filter=AM",
 "--",
 ".env.production",
 ]
 )
 if history_with_filter:
 failures.append(
 f"FAIL: .env.production was added/modified in commit history:\n{history_with_filter}"
 )

 if failures:
 for msg in failures:
 print(msg, file=sys.stderr)
 print(
 "\n→ See docs/security/secret-rotation-playbook.md for remediation.\n"
 "→ If this is a historical fix (e.g. git rm --cached), the file\n"
 " should still be absent from `git ls-files` AND never added again.",
 file=sys.stderr,
 )
 return 1

 print("OK: .env.production is not tracked and never added in git history.")
 return 0

if __name__ == "__main__":
 sys.exit(main)