#!/usr/bin/env python3
"""Minimal bootstrap — alembic upgrade + optional admin seed."""

import os
import subprocess
import sys


def run(cmd: list[str], *, cwd: str | None = None) -> None:
    print(f"[bootstrap] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)

def main() -> int:
    # Alembic upgrade
    if os.path.exists("alembic.ini"):
        try:
            run([sys.executable, "-m", "alembic", "upgrade", "head"])
        except subprocess.CalledProcessError as e:
            print(f"[bootstrap] alembic upgrade failed: {e}")
            return 1

    # Optional admin seed
    seed_script = "scripts/seed_admin.py"
    if os.path.exists(seed_script):
        try:
            run([sys.executable, "-m", "scripts.seed_admin"])
        except subprocess.CalledProcessError:
            print("[bootstrap] admin seed failed (non-critical)")

    print("[bootstrap] complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
