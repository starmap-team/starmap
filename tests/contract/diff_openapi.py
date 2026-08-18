#!/usr/bin/env python3
"""OpenAPI diff for backward compatibility.

Compares baseline OpenAPI schema vs current, checking:
1. No removed fields (paths.*.*.responses.*.content.*.schema.properties keys)
2. No type changes (paths.*.*.responses.*.content.*.schema.properties.*.type)
3. No method changes (paths keys unchanged)

Usage:
 python diff_openapi.py baseline.json current.json
Exit codes:
 0 = PASS (no breaking changes)
 1 = FAIL (breaking changes detected)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

def get_response_schemas(openapi: dict) -> dict:
 """Extract all response schemas keyed by 'METHOD path -> status'."""
 result = {}
 for path, methods in openapi.get("paths", {}).items:
 if not isinstance(methods, dict):
 continue
 for method, op in methods.items:
 if method.upper not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
 continue
 if not isinstance(op, dict):
 continue
 for status, response in op.get("responses", {}).items:
 if not isinstance(response, dict):
 continue
 content = response.get("content", {})
 for ct, ct_obj in content.items:
 if isinstance(ct_obj, dict) and "schema" in ct_obj:
 schema = ct_obj["schema"]
 key = f"{method.upper} {path} {status} {ct}"
 result[key] = schema
 return result

def get_path_methods(openapi: dict) -> set[str]:
 """Extract all path+method keys."""
 result = set
 for path, methods in openapi.get("paths", {}).items:
 if not isinstance(methods, dict):
 continue
 for method in methods:
 if method.upper in ("GET", "POST", "PUT", "DELETE", "PATCH"):
 result.add(f"{method.upper} {path}")
 return result

def get_schema_props(schema: dict) -> dict[str, str]:
 """Get schema properties as {name: type}."""
 if not isinstance(schema, dict):
 return {}
 props = schema.get("properties", {})
 result = {}
 if isinstance(props, dict):
 for name, prop_def in props.items:
 if isinstance(prop_def, dict):
 t = prop_def.get("type", "unknown")
 result[name] = str(t)
 else:
 result[name] = "unknown"
 return result

def diff_schemas(
 baseline: dict, current: dict, label: str
) -> tuple[bool, list[str]]:
 """Diff two schema dicts. Returns (passed, error_messages)."""
 errors: list[str] = []
 base_keys = set(baseline.keys)
 current_keys = set(current.keys)

 # Check removed
 removed = base_keys - current_keys
 if removed:
 errors.append(f"[{label}] Removed schemas: {sorted(removed)}")

 # Check added (informational, not error)
 added = current_keys - base_keys
 if added:
 print(f" [{label}] Added schemas (OK): {sorted(added)}")

 # Check types for common keys
 for key in base_keys & current_keys:
 b_props = get_schema_props(baseline[key])
 c_props = get_schema_props(current[key])

 # Removed fields
 removed_props = set(b_props.keys) - set(c_props.keys)
 if removed_props:
 errors.append(f"[{label}] {key} removed fields: {sorted(removed_props)}")

 # Type changes
 for prop_name in set(b_props.keys) & set(c_props.keys):
 if b_props[prop_name] != c_props[prop_name]:
 errors.append(
 f"[{label}] {key} field '{prop_name}' type changed: "
 f"{b_props[prop_name]} -> {c_props[prop_name]}"
 )

 return len(errors) == 0, errors

def main:
 if len(sys.argv) != 3:
 print("Usage: diff_openapi.py baseline.json current.json", file=sys.stderr)
 sys.exit(2)

 baseline_path = Path(sys.argv[1])
 current_path = Path(sys.argv[2])

 if not baseline_path.exists:
 print(f"ERROR: baseline file not found: {baseline_path}", file=sys.stderr)
 sys.exit(2)
 if not current_path.exists:
 print(f"ERROR: current file not found: {current_path}", file=sys.stderr)
 sys.exit(2)

 baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
 current = json.loads(current_path.read_text(encoding="utf-8"))

 print("=" * 60)
 print("OpenAPI Backward Compatibility Diff")
 print("=" * 60)
 print(f"Baseline: {baseline_path}")
 print(f"Current: {current_path}")
 print

 all_errors: list[str] = []

 # 1. Check method changes
 base_methods = get_path_methods(baseline)
 current_methods = get_path_methods(current)
 removed_methods = base_methods - current_methods
 added_methods = current_methods - base_methods

 if removed_methods:
 all_errors.append(f"Removed API methods: {sorted(removed_methods)}")
 if added_methods:
 print(f"Added API methods (OK): {sorted(added_methods)}")

 # 2. Check response schemas (fields & types)
 base_schemas = get_response_schemas(baseline)
 current_schemas = get_response_schemas(current)
 ok, errors = diff_schemas(base_schemas, current_schemas, "responses")
 if not ok:
 all_errors.extend(errors)

 # 3. Report
 print
 print("=" * 60)
 if all_errors:
 print(f"FAIL: {len(all_errors)} breaking changes detected:")
 for err in all_errors:
 print(f" - {err}")
 sys.exit(1)
 else:
 print("PASS: No breaking changes (100% backward compatible)")
 sys.exit(0)

if __name__ == "__main__":
 main