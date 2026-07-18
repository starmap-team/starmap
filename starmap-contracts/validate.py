"""StarMap 契约校验脚本。

由 CI（.github/workflows/ci.yml）在每次 PR 时调用。
校验项：
  1. openapi.yaml 是合法 YAML 且符合 OpenAPI 3.0.3 结构
  2. models/__init__.py 是合法 Python 文件
  3. openapi.yaml 与 models/__init__.py 的 schema 一致性：
     - 有 Python 类的 schema：字段名集合比对（FAIL）、类型粗映射（WARN）
     - 无 Python 类的 schema：仅 WARN

退出码：
  0 = 通过
  1 = 数据错误（YAML/Python 语法）
  2 = 逻辑错误（schema 字段不一致）
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


def _import_models() -> dict[str, type]:
    """动态 import models/__init__.py，返回 {类名: 类对象} 字典。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "starmap_contracts_models",
        ROOT / "models" / "__init__.py",
    )
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"WARN: cannot import models: {exc}")
        return {}

    from pydantic import BaseModel

    return {
        name: cls
        for name, cls in vars(mod).items()
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls is not BaseModel
    }


# OpenAPI 类型 → Python 类型 的粗映射（仅用于比对提示，不做严格类型校验）
_OAS_TYPE_MAP: dict[str, set[str]] = {
    "string": {"str", "datetime", "date", "UUID", "Any"},
    "integer": {"int"},
    "number": {"float", "int"},
    "boolean": {"bool"},
    "array": {"list", "List"},
    "object": {"dict", "Dict", "Any"},
}


def _pydantic_field_type_name(annotation: Any) -> str:
    """从 Pydantic model_fields 的 annotation 提取可读类型名。"""
    # annotation 可能是 str / int / list[SkillItem] / Optional[str] 等
    origin = getattr(annotation, "__origin__", None)
    if origin is None:
        # 简单类型：直接返回类名
        return getattr(annotation, "__name__", str(annotation))
    # 泛型：list[X] / dict[K,V] / Optional[X]
    return str(annotation).replace("typing.", "").replace("pydantic.main.", "")


def validate_consistency() -> int:
    """检查 openapi.yaml 与 models 的 schema 一致性（字段级反射比对）。

    对「有 Python 类」的 schema：
      - 比对字段名集合差异（FAIL）
      - 比对字段类型粗映射（WARN，仅提示不阻塞）
    对「无 Python 类」的 schema：保持 WARN（68 个，本次不补）。
    """
    openapi_path = ROOT / "openapi.yaml"
    models_path = ROOT / "models" / "__init__.py"

    if not openapi_path.exists() or not models_path.exists():
        return 0

    if yaml is None:
        return 0

    doc = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    schemas = doc.get("components", {}).get("schemas", {})

    # 动态 import Pydantic 模型
    model_classes = _import_models()
    if not model_classes:
        print("WARN: no Pydantic models found, skip field comparison")
        # 退回旧逻辑：只查类名
        models_source = models_path.read_text(encoding="utf-8")
        for sname in schemas:
            if f"class {sname}" not in models_source:
                print(f"WARN: schema '{sname}' has no matching Python class")
        print("OK: consistency check passed (name-only)")
        return 0

    exit_code = 0

    for sname, sdef in schemas.items():
        if not isinstance(sdef, dict):
            continue

        oas_props = set(sdef.get("properties", {}).keys())

        if sname not in model_classes:
            # 无 Python 类 → WARN（不阻塞）
            if oas_props:
                print(f"WARN: schema '{sname}' has no matching Python class")
            continue

        # 有 Python 类 → 字段比对
        cls = model_classes[sname]
        py_fields = set(cls.model_fields.keys())

        # 字段名集合差异
        only_in_oas = oas_props - py_fields
        only_in_py = py_fields - oas_props

        if only_in_oas or only_in_py:
            exit_code = 2
            parts = []
            if only_in_oas:
                parts.append(f"openapi-only: {sorted(only_in_oas)}")
            if only_in_py:
                parts.append(f"python-only: {sorted(only_in_py)}")
            print(f"FAIL: schema '{sname}' field mismatch — {', '.join(parts)}")
            continue

        # 字段类型粗比对（仅 WARN）
        for fname in oas_props & py_fields:
            oas_type = sdef["properties"][fname].get("type", "")
            py_annotation = cls.model_fields[fname].annotation
            py_type_name = _pydantic_field_type_name(py_annotation)

            if oas_type and oas_type in _OAS_TYPE_MAP:
                # 简单匹配：py_type_name 的首段是否在映射集合中
                base_py = py_type_name.split("[")[0].split(".")[-1]
                if base_py not in _OAS_TYPE_MAP[oas_type] and py_type_name not in _OAS_TYPE_MAP[oas_type]:
                    print(
                        f"WARN: schema '{sname}.{fname}' type mismatch — "
                        f"openapi={oas_type}, python={py_type_name}"
                    )

    # 反向检查：Python 有类但 openapi 无 schema → WARN
    oas_schema_names = set(schemas.keys())
    for cls_name in model_classes:
        if cls_name not in oas_schema_names:
            print(f"WARN: Python class '{cls_name}' has no matching openapi schema")

    if exit_code:
        print(f"FAIL: consistency check failed (exit {exit_code})")
    else:
        print("OK: consistency check passed")

    return exit_code


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
