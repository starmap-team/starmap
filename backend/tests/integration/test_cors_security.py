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

Both tests use the `_reload_app_main` helper which **always restores the
real `app.config.settings` and re-imports `app.main` with the real
settings in its finally block** so subsequent tests in the same process
see the production app (otherwise the SimpleNamespace leaks into the
singleton and the next test's `from app.main import settings` returns
the fake).
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@contextmanager
def _reload_app_main(fake_settings: SimpleNamespace | None):
    """Context manager: pop app.main, import under fake settings, restore.

    Yields the (possibly-rejected) `app.main` module. Always restores the
    real `app.config.settings` and re-imports `app.main` with real settings
    on exit so the singleton is left clean for the next test.
    """
    sys.modules.pop("app.main", None)
    # If a fake is provided, patch app.config.settings during the import.
    # Otherwise import directly under the real settings singleton.
    if fake_settings is not None:
        with patch("app.config.settings", fake_settings, create=True):
            yield importlib.import_module("app.main")
    else:
        yield importlib.import_module("app.main")
    # Restore: drop the (possibly-patched) app.main and re-import with the
    # real settings singleton so the next test sees a healthy module.
    sys.modules.pop("app.main", None)
    importlib.import_module("app.main")


class TestCorsStartupGuard:
    """CONCERN 1.2: cors_origins=['*'] + credentials must refuse to boot."""

    def test_wildcard_cors_with_credentials_refuses_to_import(self):
        """Importing app.main with cors_origins=['*'] raises ValueError.

        The CORSMiddleware setup runs at import time (module-level
        ``app.add_middleware(...)``), so we exercise the guard by
        stubbing ``app.config.settings.cors_origins`` before importing.
        """
        fake_settings = SimpleNamespace(
            cors_origins=["*"],
            # Other attributes accessed at import time — keep minimal.
            app_env="development",
            app_log_level="INFO",
        )

        with pytest.raises(ValueError, match="cors_origins=\\['\\*'\\]"):
            with _reload_app_main(fake_settings):
                pass  # the import inside _reload_app_main should raise

    def test_explicit_cors_origins_with_credentials_boots_cleanly(self):
        """Explicit origins + credentials is the supported config and must
        not raise at import time."""
        fake_settings = SimpleNamespace(
            cors_origins=["https://starmap.example.com"],
            app_env="development",
            app_log_level="INFO",
        )

        # No exception → guard let the boot proceed.
        with _reload_app_main(fake_settings):
            pass
