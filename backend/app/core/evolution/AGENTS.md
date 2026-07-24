# Evolution subsystem knowledge base

## OVERVIEW

Tracks position-skill change over time. PostgreSQL stores snapshots, changelogs, paths and skill time series; Neo4j remains a derived graph projection.

## WHERE TO LOOK

| Task | Location |
|---|---|
| Create idempotent snapshots | `snapshot_manager.py` |
| Compute change classes | `diff_engine.py` |
| Score change trust | `trust_scorer.py` |
| Detect emerging/rising signals | `emergence_finder.py` |
| Load skill time series | `timeseries_loader.py` |
| Recommend evolution paths | `path_recommender.py` |
| Run the complete flow | `orchestrator.py` |
| API aggregation | `app/services/evolution_service.py`, `app/services/timeseries_service.py` |
| Celery entrypoint | `app/tasks/celery_app.py::run_evolution_pipeline` |

## CONVENTIONS

- Snapshot creation must be idempotent for its position/time window.
- Changelog trust values come from `TrustScorer`; never insert placeholder confidence.
- A single position failure is reported in the run summary without discarding successful positions.
- Route handlers delegate to services/core and do not recompute evolution metrics.
- Tests assert change types, thresholds, idempotency and failure isolation; do not pin historical pass counts.

## ANTI-PATTERNS

- Do not seed demo snapshots and present them as market evidence.
- Do not bypass snapshot/diff services with ad hoc table writes.
- Do not treat bounded path recommendations as an exhaustive position graph.