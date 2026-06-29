# Scripts knowledge base

## OVERVIEW
Operational scripts for database seeding, Neo4j schema setup, data export, graph expansion, and server deployment. Run from the starmap root directory.

## STRUCTURE
```
scripts/
├── init_neo4j_schema.py           # Create Neo4j constraints and indexes
├── import_esco_skill.py           # Import ESCO skill taxonomy into Neo4j
├── seed_jd_data.py                # Seed sample JD extraction records into PostgreSQL
├── seed_position_skill_records.py # Seed position-skill relational records
├── expand_graph_data.py           # Expand Neo4j graph with additional relationships
├── add_more_skills.py             # Add supplementary skill nodes
├── sync_extractions_to_graph.py   # Sync PostgreSQL extractions → Neo4j
├── quality_report.py              # Generate graph quality metrics
├── final_e2e_verify.py            # End-to-end verification script
├── test_qwen_ollama.py            # Test local Qwen/Ollama LLM connectivity
├── daily-integration.sh           # Daily integration smoke test
├── server-setup.sh                # Production server setup
├── server-daily.sh                # Daily server maintenance
├── deploy-lightweight.sh          # Lightweight deployment script
└── README.md                      # Script usage documentation
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Initialize graph schema | init_neo4j_schema.py | Run before first data import |
| Import skill taxonomy | import_esco_skill.py | Reads ESCO data, writes to Neo4j |
| Seed test data | seed_jd_data.py, seed_position_skill_records.py | PostgreSQL seed scripts |
| Expand graph | expand_graph_data.py, add_more_skills.py | Neo4j graph enrichment |
| Check quality | quality_report.py | Generates quality metrics report |

## CONVENTIONS
- Scripts are standalone; import from `app.*` only when needed for DB models.
- Run from starmap root: `python scripts/<script>.py`.
- Shell scripts use bash and expect `.env` to be present at project root.
- Seed scripts are idempotent where possible (upsert patterns).

## ANTI-PATTERNS
- Do **not** run seed scripts against production without explicit approval.
- Do **not** modify schema scripts without testing against a fresh Neo4j instance.
- Do **not** hardcode credentials; always read from `.env` via `app.config.settings`.
