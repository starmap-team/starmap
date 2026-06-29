# Extraction pipeline knowledge base

## OVERVIEW
Core subsystem for JD/resume extraction, multi-provider LLM integration, normalization, validation, and optional Neo4j persistence.

## STRUCTURE
```
backend/app/core/extraction/
├── jd_extract.py     # Orchestrates the full extraction pipeline (extract → validate → persist)
├── prompt.py         # Prompt registry, active versions, A/B tests
├── llm_client.py     # Multi-provider LLM client with fallback chain + LLMClient class
├── normalize.py      # Alias normalization and shared normalization helpers
└── graph_writer.py   # Extraction → Neo4j graph writes (GraphConfig, batch_write_extractions)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Change extraction flow | jd_extract.py | Pipeline control logic lives here |
| Update prompts | prompt.py | Versions and A/B routing are managed centrally |
| Tune LLM call behavior | llm_client.py | Timeout/retry/parsing logic; fallback chain: MiMo → DeepSeek → Xunfei → Qwen |
| Improve normalization | normalize.py | Alias tables and normalization logic |
| Persist extractions to graph | graph_writer.py | Neo4j write helpers; GraphConfig manages driver lifecycle |

## CONVENTIONS
- Normalize skills after LLM output, never before.
- Keep extraction output structured and Pydantic-validated before service/API layers consume it.
- Prompt/template versions should be explicitly tracked and switchable.
- `LLMClient` is the high-level interface: `extract_from_jd()`, `validate_extraction()`, `judge_quality()`.
- `call_llm_with_fallback()` handles provider chain; each provider has its own retry decorator (3 attempts, exponential backoff).
- LLM JSON responses are parsed through `parse_llm_json_response()` which strips markdown fences.

## ANTI-PATTERNS
- Do **not** send golden truth fields into extraction during evaluation.
- Do **not** bypass normalization/validation before persisting or scoring extraction results.
- Do **not** hardcode provider-specific assumptions without going through the shared LLM client.
- Do **not** call individual LLM provider functions directly; use `call_llm_with_fallback()`.
