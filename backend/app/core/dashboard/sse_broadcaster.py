"""SSE event broadcaster using Redis pub/sub.

Publishes real-time dashboard events (pipeline updates, quality alerts,
data milestones, extraction completions) to connected SSE clients via
``starlette.responses.StreamingResponse``.  No extra dependencies —
uses the Redis async client already present in ``AppResources``.

Usage
-----
Publish an event from anywhere in the application::

    from app.core.dashboard.sse_broadcaster import publish_event
    await publish_event(redis, "pipeline_update", {"run_id": "...", "status": "completed"})

Consume in the API layer::

    from app.core.dashboard.sse_broadcaster import event_stream
    return StreamingResponse(event_stream(redis), media_type="text/event-stream")
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable
from typing import Any, cast

from loguru import logger
from redis.asyncio import Redis

from app.exceptions import DashboardError, StarMapError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHANNEL = "dashboard:events"
HEARTBEAT_INTERVAL = 15  # seconds
POLL_INTERVAL = 0.5  # seconds between checks
EVENT_TTL = 300  # seconds to keep events in Redis list for polling fallback
POLL_LIST_KEY = "dashboard:recent_events"
MAX_SSE_CLIENTS = 50  # AP-07: connection limit to prevent resource exhaustion

# Valid event types (informational; not enforced on publish)
VALID_EVENT_TYPES = frozenset({
    "pipeline_update",
    "quality_alert",
    "data_milestone",
    "extraction_complete",
})

# AP-07: Active SSE connection counter (process-local)
_active_sse_clients = 0


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------

async def publish_event(
    redis: Redis | None,
    event_type: str,
    data: dict[str, Any],
) -> bool:
    """Publish a real-time event to the SSE channel.

    Also appends the event to a capped Redis list so the polling
    fallback endpoint can retrieve recent events.

    Parameters
    ----------
    redis : Redis or None
        Async Redis client.  If ``None`` the call is a silent no-op.
    event_type : str
        One of the VALID_EVENT_TYPES (e.g. ``"pipeline_update"``).
    data : dict
        Arbitrary event payload.

    Returns
    -------
    bool
        ``True`` if the event was published, ``False`` on error.
    """
    if redis is None:
        return False

    payload = {
        "type": event_type,
        "data": data,
        "timestamp": time.time(),
    }
    try:
        message = json.dumps(payload, default=str)
        await redis.publish(CHANNEL, message)
        # Append to polling fallback list (LPUSH + LTRIM for capped list)
        await cast(Awaitable[Any], redis.lpush(POLL_LIST_KEY, message))
        await cast(Awaitable[Any], redis.ltrim(POLL_LIST_KEY, 0, 99))  # keep latest 100
        await redis.expire(POLL_LIST_KEY, EVENT_TTL)
        return True
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("SSE publish failed for {}", event_type)
        return False


# ---------------------------------------------------------------------------
# SSE event stream generator
# ---------------------------------------------------------------------------

async def event_stream(
    redis: Redis | None,
) -> AsyncIterator[str]:
    """Yield SSE-formatted messages from the Redis pub/sub channel.

    This is an async generator intended to be consumed by
    ``StreamingResponse(event_stream(redis), media_type="text/event-stream")``.

    Behaviour:
    - Subscribes to the ``dashboard:events`` Redis channel.
    - Sends a ``: heartbeat`` comment every 15 s to keep the connection alive.
    - Forwards every received message as an SSE ``event:`` + ``data:`` block.
    - Gracefully exits if the Redis connection drops.
    """
    if redis is None:
        # Fallback: send a single error event and close
        yield _format_sse("error", {"message": "Redis not available"})
        return

    # AP-07: Enforce connection limit
    global _active_sse_clients
    if _active_sse_clients >= MAX_SSE_CLIENTS:
        yield _format_sse("error", {"message": f"Max SSE clients ({MAX_SSE_CLIENTS}) reached"})
        return
    _active_sse_clients += 1

    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(CHANNEL)
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("SSE subscribe failed")
        yield _format_sse("error", {"message": f"Subscribe failed: {exc}"})
        return

    last_heartbeat = time.time()

    try:
        while True:
            # --- heartbeat ---
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                yield f": heartbeat {now}\n\n"
                last_heartbeat = now

            # --- check for messages ---
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=POLL_INTERVAL,
                )
            except TimeoutError:
                message = None
            except StarMapError:
                raise
            except (ConnectionError, OSError) as exc:
                logger.exception("pubsub connection error")
                await asyncio.sleep(POLL_INTERVAL)
                continue
            except Exception as exc:
                logger.exception("pubsub.get_message error")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if message and message.get("type") == "message":
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                if raw:
                    try:
                        event = json.loads(raw)
                        event_type = event.get("type", "unknown")
                        yield _format_sse(event_type, event)
                    except (json.JSONDecodeError, TypeError):
                        yield _format_sse("raw", {"data": str(raw)})

    except asyncio.CancelledError:
        logger.debug("SSE client disconnected")
    except StarMapError:
        raise
    except (ConnectionError, OSError) as exc:
        logger.exception("SSE subscriber connection error")
        # Continue — single subscriber failure shouldn't break broadcast
    except Exception as exc:
        logger.exception("SSE stream error")
        # Continue — don't break the broadcast loop
    finally:
        _active_sse_clients = max(0, _active_sse_clients - 1)
        try:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()
        except StarMapError:
            raise
        except (ConnectionError, OSError) as exc:
            logger.exception("SSE pubsub connection cleanup failed")
        except Exception as exc:
            logger.exception("SSE pubsub cleanup failed")


# ---------------------------------------------------------------------------
# Polling fallback
# ---------------------------------------------------------------------------

async def get_recent_events(
    redis: Redis | None,
    since: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent events from the capped Redis list.

    Used by the polling fallback endpoint.  If *since* is provided,
    only events with a timestamp strictly after *since* are returned.

    Parameters
    ----------
    redis : Redis or None
        Async Redis client.
    since : float or None
        Unix timestamp — only return events after this time.
    limit : int
        Maximum number of events to return.

    Returns
    -------
    list of dicts
        Each element has ``type``, ``data``, and ``timestamp`` keys.
    """
    if redis is None:
        return []

    try:
        raw_events = await cast(Awaitable[list[Any]], redis.lrange(POLL_LIST_KEY, 0, limit - 1))
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Polling fallback read failed")
        return []

    events: list[dict[str, Any]] = []
    for raw in raw_events:
        try:
            event = json.loads(raw) if isinstance(raw, str) else json.loads(str(raw))
            if since is not None and event.get("timestamp", 0) <= since:
                continue
            events.append(event)
        except (json.JSONDecodeError, TypeError):
            continue

    return events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE message block."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
