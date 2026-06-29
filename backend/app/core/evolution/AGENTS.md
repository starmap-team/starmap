# Evolution subsystem knowledge base

## OVERVIEW
Tracks position-skill evolution over time with snapshots, diffs, trust scoring, hallucination defense, emergence detection, and path recommendations. Orchestrator coordinates an 8-step pipeline.

## STRUCTURE
```
backend/app/core/evolution/
├── orchestrator.py          # 8-step pipeline: load→diff→trust→guard→emergence→paths→save→graph
├── snapshot_manager.py      # Create/retrieve position snapshots
├── diff_engine.py           # Compute changes between snapshots
├── trust_integration.py     # Weighted trust scoring
├── hallucination_guard.py   # Three-layer validation for skill claims
├── emergence_finder.py      # Detect emerging skills (Z-score + HDBSCAN)
└── path_recommender.py      # Recommend evolution paths (Jaccard similarity)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Change analysis workflow | orchestrator.py | 8-step pipeline; starts with SnapshotManager, ends with Neo4j EVOLVES_TO writes |
| Change snapshot storage | snapshot_manager.py | Snapshot creation and retrieval from PostgreSQL |
| Tune change detection | diff_engine.py | Diff logic between snapshots (added/removed/promoted/demoted) |
| Adjust trust logic | trust_integration.py | Weighted/exponential trust scoring |
| Tighten hallucination checks | hallucination_guard.py | Layered validation logic |
| Detect emerging skills | emergence_finder.py | Z-score and HDBSCAN-based emergence detection |
| Discover career paths | path_recommender.py | Jaccard similarity between position skill sets |

## CONVENTIONS
- Keep evolution modules focused on one responsibility each.
- Orchestrator uses SQLAlchemy `AsyncSession` for PostgreSQL and Neo4j driver for graph writes.
- Evolution models (snapshots, changelog, paths, timeseries) live in `app/models/evolution_models.py`.
- Trust scores range 0.0–1.0 and are stored alongside changelog entries.

## ANTI-PATTERNS
- Do **not** mix extraction normalization rules directly into evolution logic.
- Do **not** compute trust/emergence/trend in route handlers.
- Do **not** bypass the hallucination guard when surfacing newly detected skills.
