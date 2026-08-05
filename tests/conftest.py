"""Root tests/ conftest (frontend integration tests).

These tests are designed for the Playwright integration environment
(``pytest-playwright`` providing a real ``page`` fixture). The backend
unit-test environment has no Playwright, so referencing ``page`` causes
``fixture 'page' not found`` setup errors. Marking them as skip makes the
intent explicit: these belong in a separate integration run, not the
backend unit suite.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def page(request):  # noqa: ARG001 — signature required by Playwright-style tests
    pytest.skip(
        "requires pytest-playwright integration environment (not in backend unit deps)"
    )
