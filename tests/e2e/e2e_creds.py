"""E2E 测试凭据单一入口（PLAN-007 / NEW-20）。

此前 admin 引导凭据硬编码散落在 16+ 个 e2e/脚本文件中。本模块收敛为单一来源：
优先读环境变量，默认值为 dev compose 播种的引导账号（生产被 config.py
fail-fast 阻断，不会进入生产库）。覆盖方式：

    STARMAP_TEST_ADMIN_USER / STARMAP_TEST_ADMIN_PASSWORD
"""
from __future__ import annotations

import os

ADMIN_USER = os.environ.get("STARMAP_TEST_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("STARMAP_TEST_ADMIN_PASSWORD", "starmap2024")


def login_payload() -> dict[str, str]:
    """登录请求体（POST /auth/login）。"""
    return {"username": ADMIN_USER, "password": ADMIN_PASSWORD}
