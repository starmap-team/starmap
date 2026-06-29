# Crawler subsystem knowledge base

## OVERVIEW
Job-market ingestion subsystem: spiders, Scrapy/Playwright pipelines, dedup, compliance logging, persistence, and dedicated crawler tests.

## STRUCTURE
```text
starmap/crawler/
├── spiders/             # source-specific crawlers (boss/job51/lagou + stealth variants)
├── pipelines/           # cleaning, dedup, and persistence pipeline helpers
├── persistence/         # ORM models, migrations, DAO/storage helpers
├── scripts/             # crawler ops/debug/export scripts
├── tests/               # crawler-focused unit/integration tests
├── compliance.py        # robots checks, QPS limits, logging, proxy fetch helper
├── dedup.py             # hash/SimHash dedup utilities
├── config.py            # runtime crawler config
└── requirements.txt     # crawler-specific dependencies
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/change source crawl logic | `starmap/crawler/spiders/` | One spider per site family |
| Change clean/persist behavior | `starmap/crawler/pipelines/` | Keep pipeline steps modular |
| Adjust persistence schema | `starmap/crawler/persistence/` | Use crawler-local migrations |
| Work on compliance rules | `starmap/crawler/compliance.py` | robots, rate limiting, logging, proxy behavior |
| Run/debug crawler helpers | `starmap/crawler/scripts/` | ESCO mapping, export, integration, golden tests |

## CONVENTIONS
- Keep crawler dependencies separate from backend dependencies.
- Persist compliance logs even when the main request flow fails.
- Treat stealth/browser automation as high-friction paths and keep them isolated per spider.

## ANTI-PATTERNS
- Do **not** bypass rate limits or robots checks.
- Do **not** commit persistence schema changes without migrations.
- Do **not** mix crawler persistence assumptions directly into backend application models.


