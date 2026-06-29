# Evaluation knowledge base

## OVERVIEW
Evaluation tooling and artifacts: baseline keyword evaluation, LLM-sim evaluation, real LLM evaluation, judge scoring, golden sets, and generated reports.

## STRUCTURE
```text
starmap/evaluation/
├── run_baseline.py            # keyword-match baseline evaluation
├── simulate_llm_eval.py       # simulated LLM evaluation helper
├── run_llm_eval.py            # LLM evaluation runner
├── run_real_eval.py           # real end-to-end LLM evaluation entrypoint
├── judge_eval.py              # judge + F1 scoring utilities
├── analyze_baseline.py        # baseline analysis utilities
├── debug_match.py             # match debugging helper
├── golden_set.jsonl           # 50-item golden extraction set
├── golden_set_match.jsonl     # golden match evaluation set
├── golden_set_resume.jsonl    # golden resume evaluation set
├── system_baseline.jsonl      # baseline system outputs
├── system_llm_real.jsonl      # real LLM system outputs
├── system_llm_sim_*.jsonl     # simulated LLM outputs at various temperatures
├── baseline_report/           # baseline report artifacts
├── llm_sim_report/            # simulated LLM report artifacts
├── llm_real_report/           # real LLM report artifacts
└── real_eval_report/          # real eval outputs, analysis, and metadata
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|---|
| Change extraction golden set | `golden_set.jsonl` | Only update truth definitions here |
| Change match golden set | `golden_set_match.jsonl` | Match-specific golden pairs |
| Change resume golden set | `golden_set_resume.jsonl` | Resume-specific golden samples |
| Run real eval | `run_real_eval.py` | Requires real API credentials (MiMo); refuses mock-only |
| Tune judge logic | `judge_eval.py` | Precision/recall/F1/reporting logic |
| Debug match scoring | `debug_match.py` | Interactive match debugging |
| Analyze baseline results | `analyze_baseline.py` | Baseline comparison utilities |
| Check prior reports | `*_report/` | Generated outputs and analysis artifacts |

## CONVENTIONS
- Keep truth fields out of the extraction pipeline until scoring time.
- Treat generated reports as artifacts, not as editable source of truth.
- Preserve reproducibility metadata in the real eval output directory.
- Golden sets are split by domain (extraction, match, resume) — update only the relevant one.
- System output `.jsonl` files capture run results for reproducibility.

## ANTI-PATTERNS
- Do **not** inject golden truth into extraction runs.
- Do **not** edit generated reports manually as a substitute for rerunning evaluation.
- Do **not** mix simulated and real evaluations when making pipeline quality claims.
- Do **not** commit system output files without verifying they represent a clean run.
