"""Layer boundary tests.

Verifies that the module dependency rules are followed:
- api/v1/ -> services/ -> core/
- No direct api/v1/ -> core/ imports
"""
from __future__ import annotations

import ast
import pathlib


def _get_imports(filepath: str) -> list[tuple[str, str]]:
    """Return (module, name) import tuples from a Python file."""
    tree = ast.parse(pathlib.Path(filepath).read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(("", alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append((mod, alias.name))
    return imports


API_ROUTE_FILES = [
    "app/api/v1/evolution.py",
    "app/api/v1/extract.py",
    "app/api/v1/judge.py",
    "app/api/v1/learning.py",
    "app/api/v1/match.py",
    "app/api/v1/position.py",
    "app/api/v1/quality.py",
    "app/api/v1/resume.py",
]


def test_api_routes_do_not_import_core_directly():
    """API routes must go through services/ layer, not core/ directly."""
    violations = []
    for rel_path in API_ROUTE_FILES:
        imports = _get_imports(rel_path)
        for mod, name in imports:
            if mod.startswith("app.core") or name.startswith("app.core"):
                violations.append(f"{rel_path}: {mod}.{name}")
    assert not violations, (
        f"API routes importing from core/ directly: {violations}"
    )


def test_api_routes_import_from_services():
    """API routes should import from services/ for business logic."""
    for rel_path in API_ROUTE_FILES:
        imports = _get_imports(rel_path)
        service_imports = [
            (mod, name) for mod, name in imports
            if mod.startswith("app.services") or name.startswith("app.services")
        ]
        assert service_imports, (
            f"{rel_path} has no imports from services/ layer"
        )
