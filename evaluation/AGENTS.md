# Evaluation knowledge base

## OVERVIEW

Reproducible extraction, resume, match and pipeline evaluations using domain-specific Golden Sets.

## WHERE TO LOOK

| Task | Location |
|---|---|
| JD extraction truth | `golden_set.jsonl` |
| Resume truth | `golden_set_resume.jsonl` |
| Match truth | `golden_set_match.jsonl` |
| Pipeline truth | `golden_set_pipeline.jsonl` |
| Baseline entry | `run_baseline.py`, `run_resume_baseline.py` |
| Simulated LLM | `simulate_llm_eval.py` |
| Real LLM | `run_real_eval.py` |
| Scoring/judge | `judge_eval.py` |
| Labeling rules | `annotation_guideline.md` |

## CONVENTIONS

- Keep Golden truth isolated from the system under test.
- Report baseline, simulated and real LLM runs separately.
- Store model, prompt, dataset commit and timestamp with real evaluation output.
- Rerun evaluation instead of editing generated reports.
- Do not maintain sample counts or F1 claims in AGENTS; derive them from data and current runs.