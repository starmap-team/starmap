# Crawler subsystem knowledge base

## OVERVIEW

Job-source ingestion, compliance checks, cleaning, deduplication, persistence adapters and pipeline integration.

## CURRENT SOURCE LAYOUT

- `spiders/v2ex_remote.py` is the active local spider.
- `spiders/_disabled/` contains non-runnable historical site implementations.
- `scripts/apify_*.py` are optional cloud collection tools, not local spider registrations.

## WHERE TO LOOK

| Task | Location |
|---|---|
| Compliance and throttling | `compliance.py` |
| Proxy circuit breaking | `middleware/proxy_middleware.py` |
| Cleaning/incremental storage | `pipelines/` |
| Crawler-local persistence | `persistence/` |
| Backend pipeline bridge | `pipeline_bridge.py` |
| Source/tool CLI | `run.py`, `scripts/` |

## CONVENTIONS

- Respect robots, rate limits, source terms and explicit source status.
- Preserve request/compliance logs even when collection fails.
- Keep crawler persistence migrations separate and intentional.
- Never activate a `_disabled` spider without a fresh selector, compliance and integration test.
- Credentials come from environment variables, not source or docs.