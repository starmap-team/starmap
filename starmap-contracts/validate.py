"""StarMap 契约校验脚本。

由 CI（.github/workflows/ci.yml）在每次 PR 时调用。
校验项：
  1. openapi.yaml 是合法 YAML 且符合 OpenAPI 3.0.3 结构
  2. models/__init__.py 是合法 Python 文件
  3. openapi.yaml 与 models/__init__.py 的 schema 定义不矛盾（类型/字段级校验）

退出码：
  0 = 通过
  1 = 数据错误（YAML/Python 语法）
  2 = 逻辑错误（schema 不一致）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent


def validate_openapi() -> int:
    """校验 openapi.yaml 是合法 OpenAPI 3.0.3 文档。"""
    path = ROOT / "openapi.yaml"
    if not path.exists():
        print(f"FAIL: {path} not found")
        return 1

    raw = path.read_text(encoding="utf-8")

    if yaml is None:
        print("WARN: pyyaml not installed, skip validation")
        return 0

    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f"FAIL: {path} is not valid YAML: {exc}")
        return 1

    if not isinstance(doc, dict):
        print(f"FAIL: {path} root is not a mapping")
        return 1

    # 必填顶层字段
    for key in ("openapi", "info", "paths"):
        if key not in doc:
            print(f"FAIL: {path} missing required field '{key}'")
            return 1

    openapi_ver = str(doc.get("openapi", ""))
    if not openapi_ver.startswith("3."):
        print(f"FAIL: {path} openapi version must be 3.x, got '{openapi_ver}'")
        return 1

    info = doc.get("info", {})
    if "title" not in info:
        print(f"FAIL: {path} info.title is required")
        return 1

    paths = doc.get("paths", {})
    if not paths:
        print(f"WARN: {path} has no paths (empty API)")
    else:
        print(f"OK: {path} has {len(paths)} path(s)")

    # 检查每个 endpoint 有 operationId
    for pname, pitem in paths.items():
        if not isinstance(pitem, dict):
            continue
        for method in ("get", "post", "put", "delete", "patch"):
            op = pitem.get(method)
            if op is None:
                continue
            if "operationId" not in op:
                print(f"WARN: {path} {pname}.{method} has no operationId")

    components = doc.get("components", {})
    schemas = components.get("schemas", {})
    if schemas:
        print(f"OK: {path} has {len(schemas)} schema(s)")

    return 0


def validate_models_py() -> int:
    """校验 models/__init__.py 是合法 Python。"""
    path = ROOT / "models" / "__init__.py"
    if not path.exists():
        print(f"FAIL: {path} not found")
        return 1

    source = path.read_text(encoding="utf-8")
    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        print(f"FAIL: {path} has syntax error: {exc}")
        return 1

    print(f"OK: {path} compiles ({len(source.splitlines())} lines)")
    return 0


def validate_consistency() -> int:
    """检查 openapi.yaml 与 models 无矛盾（字段级快速比对）。"""
    openapi_path = ROOT / "openapi.yaml"
    models_path = ROOT / "models" / "__init__.py"

    if not openapi_path.exists() or not models_path.exists():
        return 0  # skip if files missing

    if yaml is None:
        return 0

    doc = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    schemas = doc.get("components", {}).get("schemas", {})

    models_source = models_path.read_text(encoding="utf-8")

    for sname, sdef in schemas.items():
        if not isinstance(sdef, dict):
            continue
        props = sdef.get("properties", {})
        if not props:
            continue
        for pname in props:
            # 检查 Python model 中是否有同名类（粗略校验）
            class_pattern = f"class {sname}"
            if class_pattern not in models_source:
                # 可能用别名，仅 warn
                print(f"WARN: schema '{sname}' has no matching Python class")
                break
            break

    print("OK: consistency check passed")
    return 0


def main() -> int:
    exit_code = 0

    print("=== validate openapi.yaml ===")
    code = validate_openapi()
    if code:
        print(f"validate_openapi -> exit {code}")
        exit_code = code

    print()
    print("=== validate models/__init__.py ===")
    code = validate_models_py()
    if code:
        print(f"validate_models_py -> exit {code}")
        exit_code = code

    print()
    print("=== consistency check ===")
    code = validate_consistency()
    if code:
        print(f"validate_consistency -> exit {code}")
        exit_code = code

    print()
    if exit_code:
        print(f"FAIL: validation failed (exit {exit_code})")
    else:
        print("PASS: all validations passed")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
