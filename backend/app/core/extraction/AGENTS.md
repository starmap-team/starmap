# Extraction subsystem knowledge base

## OVERVIEW

JD and resume extraction, shared LLM fallback, prompt governance, skill normalization and validated graph-write preparation.

## WHERE TO LOOK

| Task | Location |
|---|---|
| JD flow | `jd_extract.py` |
| Resume flow | `resume_extract.py` |
| Provider fallback and parsing | `llm_client.py` |
| Prompt versions and A/B routing | `prompt.py` |
| Alias/string normalization | `normalize.py` |
| Graph write adapter | `graph_writer.py` |
| Evaluation helpers | `resume_eval.py` |

## CONVENTIONS

- JD and resume are separate input contracts.
- Parse and validate LLM JSON before normalization or persistence.
- Every extracted skill keeps confidence/trust and evidence provenance.
- Development must work without ChromaDB; vector matching is optional.
- Provider-specific calls go through the shared fallback client.

## ANTI-PATTERNS

- Do not leak Golden Set truth into prompts or extraction input.
- Do not persist raw provider payloads as validated business data.
- Do not write PG/Neo4j directly from route handlers.