# Contracts knowledge base

## OVERVIEW
Cross-team single source of truth: OpenAPI spec, shared Pydantic models, Cypher templates, and contract validation.

## STRUCTURE
```text
starmap/starmap-contracts/
├── openapi.yaml                        # OpenAPI 3.0.3 spec (authoritative API definition)
├── models/__init__.py                  # Pydantic v2 shared models (must stay in sync with openapi.yaml)
├── graph_cypher/query_templates.cypher # Neo4j Cypher query templates
├── validate.py                         # CI validation script (YAML syntax + schema consistency check)
├── CHANGELOG.md                        # Contract version history
└── README.md
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/change API endpoints | openapi.yaml | Edit here FIRST, then update backend routes and frontend types |
| Add/change shared models | models/__init__.py | Pydantic v2; must not contradict openapi.yaml schemas |
| Update Cypher templates | graph_cypher/query_templates.cypher | Shared query patterns for Neo4j layers |
| Validate contract consistency | alidate.py | Exit 0=pass, 1=data error, 2=logic/schema mismatch |

## CONVENTIONS
- Contract-first workflow: changes to API shape MUST start here.
- alidate.py runs in CI on every PR; changes that break it will block merges.
- Schema field types in models/__init__.py must exactly match openapi.yaml definitions.

## ANTI-PATTERNS
- Do **not** add backend routes before updating the contract.
- Do **not** edit openapi.yaml and models/__init__.py independently — keep them synchronized.
- Do **not** skip CHANGELOG.md entries when bumping contract versions.