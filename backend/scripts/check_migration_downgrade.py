"""CI guard (CONCERN 9.5): detect forward-only Alembic migrations.

Some migrations legitimately cannot be downgraded:
  - merge migrations (combine two heads) — downgrade is `pass` by design
  - irreversible data fixes (column drops that lose data)

Convention: such migrations must set
    _DOWNGRADE_NOTE = "merge"   OR   "irreversible"
in module scope so this guard can suppress the warning.

Exits 0 always; reports empty-downgrade migrations to stdout.
Warn-only: does not fail CI on its own (callers may `grep WARNING`).
"""
from __future__ import annotations

import ast
import glob
import sys


def main() -> int:
    empty: list[str] = []
    no_downgrade: list[str] = []

    for path in sorted(glob.glob("alembic/versions/*.py")):
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except SyntaxError as exc:
            print(f"WARN: cannot parse {path}: {exc}", file=sys.stderr)
            continue

        has_downgrade = False
        downgrade_is_empty = False
        has_note = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "_DOWNGRADE_NOTE":
                        has_note = True
            if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
                has_downgrade = True
                body = node.body
                # Drop docstring
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                ):
                    body = body[1:]
                # Empty if only Pass statements remain
                real = [b for b in body if not isinstance(b, ast.Pass)]
                if not real:
                    downgrade_is_empty = True

        if has_downgrade and downgrade_is_empty and not has_note:
            empty.append(path)
        elif not has_downgrade:
            no_downgrade.append(path)

    if empty:
        print(
            f"WARNING: {len(empty)} migration(s) have empty downgrade() "
            f"without justification:"
        )
        for f in empty:
            print(f"  {f}")
        print()
        print(
            "Add `_DOWNGRADE_NOTE = 'merge'|'irreversible'` to module scope,"
            "\nor implement a real downgrade."
        )

    if no_downgrade:
        print(
            f"WARNING: {len(no_downgrade)} migration(s) have no downgrade() at all:"
        )
        for f in no_downgrade[:5]:
            print(f"  {f}")
        if len(no_downgrade) > 5:
            print(f"  ... and {len(no_downgrade) - 5} more")

    print(
        f"OK: downgrade-body check completed "
        f"({len(empty)} forward-only without justification, "
        f"{len(no_downgrade)} without downgrade)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
