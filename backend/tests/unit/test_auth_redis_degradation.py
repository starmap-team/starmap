"""Phase 20 D-03: /auth/login Redis degradation tests.

Verifies that token issuance does NOT collapse when Redis is unavailable.
Revocation writes are enqueued for deferred flush.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import User
from app.services.auth_service import (
    _revocation_queue,
    _RevocationQueue,
    create_access_token,
    create_tokens,
    hash_password,
)

# ── Helper: a User that's already authenticated (skip password verify) ──


def _user() -> User:
    return User(
        id="00000000-0000-0000-0000-000000000001",
        username="redis_test_user",
        password_hash=hash_password("testX123"),
        role="user",
    )


# ── Tests ──


@pytest.mark.asyncio
async def test_login_without_redis_succeeds():
    """Phase 20 D-03: redis=None → tokens still issued (no 503)."""
    user = _user()
    result = await create_tokens(user, redis=None)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["user"]["username"] == "redis_test_user"
    # access token is decodable
    import jwt as _jwt
    decoded = _jwt.decode(
        result["access_token"],
        options={"verify_signature": False},
    )
    assert decoded["sub"] == "redis_test_user"


@pytest.mark.asyncio
async def test_login_with_failing_redis_succeeds():
    """Redis client raises → tokens still issued, item enqueued for retry."""
    user = _user()

    failing_redis = MagicMock()
    failing_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))

    result = await create_tokens(user, redis=failing_redis)

    assert "access_token" in result
    # Allow the create_task scheduled by _enqueue_revocation to run
    await asyncio.sleep(0)
    # The queue should now have one item (subject to bounded size + lock)
    assert _revocation_queue.qsize() >= 1


@pytest.mark.asyncio
async def test_revocation_queue_drain_recovers():
    """drain_to_redis writes pending items when Redis is healthy again."""
    q = _RevocationQueue(maxsize=100)
    for i in range(5):
        await q.put((f"jti-{i}", f"uid-{i}", 60, None))

    fake_redis = MagicMock()
    fake_redis.set = AsyncMock(return_value=True)

    flushed = await q.drain_to_redis(fake_redis)
    assert flushed == 5
    assert q.qsize() == 0
    assert fake_redis.set.await_count == 5


@pytest.mark.asyncio
async def test_revocation_queue_re_enqueue_on_partial_failure():
    """If Redis errors mid-drain, remaining items are re-enqueued (preserving order)."""
    q = _RevocationQueue(maxsize=100)
    for i in range(5):
        await q.put((f"jti-{i}", f"uid-{i}", 60, None))

    call_count = 0

    async def flaky_set(_key, _value, ex=None):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise ConnectionError("redis dropped mid-drain")
        return True

    fake_redis = MagicMock()
    fake_redis.set = flaky_set

    flushed = await q.drain_to_redis(fake_redis)
    assert flushed == 2  # first two succeeded
    # Remaining items re-enqueued (first failure breaks the loop)
    assert q.qsize() >= 1


@pytest.mark.asyncio
async def test_revocation_queue_bounds_size():
    """Bounded queue drops oldest on overflow (prevents unbounded growth)."""
    q = _RevocationQueue(maxsize=3)
    for i in range(5):
        await q.put((f"jti-{i}", f"uid-{i}", 60, None))
    # deque(maxlen=3) auto-drops oldest; qsize should equal cap
    assert q.qsize() == 3
    # Surviving items are the most recent
    pending = list(q._items)  # noqa: SLF001 - test introspection
    assert pending[0][0] == "jti-2"
    assert pending[-1][0] == "jti-4"


def test_existing_create_access_token_still_works():
    """Sanity: pure JWT issuance (no redis touch) is unaffected by Phase 20."""
    token = create_access_token(_user())
    import jwt as _jwt
    header = _jwt.get_unverified_header(token)
    assert header["kid"]  # Phase 20 Task 2 already wired kid
