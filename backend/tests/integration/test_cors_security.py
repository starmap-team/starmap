"""Integration tests for CORS startup guard (CONCERN 1.2, security audit 2026-08-15).

The guard in app.main refuses startup if `cors_origins == ["*"]` while
`allow_credentials=True`. That combination is a CSRF-grade hole — Starlette
does not silently reject it on every FastAPI version, and operators
occasionally set the wildcard during debugging. Failing fast at startup is
the safer behaviour.

These tests reload the module under test with mocked settings to assert
both the rejection path and the boot path. They avoid hitting the live
``app.config.settings`` because the CORS-middleware code runs at import
time and is process-global — each test rewrites the module under a fresh
import.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest


class TestCorsStartupGuard:
    """CONCERN 1.2: cors_origins=['*'] + credentials must refuse to boot."""

    def test_wildcard_cors_with_credentials_refuses_to_import(self):
        """Importing app.main with cors_origins=['*'] raises ValueError.

        The CORSMiddleware setup runs at import time (module-level
        ``app.add_middleware(...)``), so we exercise the guard by
        stubbing ``app.config.settings.cors_origins`` before importing.
        """
        # Drop any cached app.main so the module re-evaluates under our stub.
        for mod_name in ("app.main",):
            sys.modules.pop(mod_name, None)

        fake_settings = SimpleNamespace(
            cors_origins=["*"],
            # Other attributes accessed at import time — keep minimal.
            app_env="development",
            app_log_level="INFO",
        )

        with patch("app.config.settings", fake_settings, create=True):
            with pytest.raises(ValueError, match="cors_origins=\\['\\*'\\]"):
                importlib.import_module("app.main")

    def test_explicit_cors_origins_with_credentials_boots_cleanly(self):
        """Explicit origins + credentials is the supported config and must
        not raise at import time."""
        for mod_name in ("app.main",):
            sys.modules.pop(mod_name, None)

        fake_settings = SimpleNamespace(
            cors_origins=["https://starmap.example.com"],
            app_env="development",
            app_log_level="INFO",
        )

        with patch("app.config.settings", fake_settings, create=True):
            # No exception → guard let the boot proceed.
            importlib.import_module("app.main")
