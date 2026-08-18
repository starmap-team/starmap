"""Loop step modules — split (/).

One module per pipeline step:
 - validate.py — Step 1: JD input validation + target_position resolution
 - extract.py — Step 2: LLM-based skill extraction
 - graph_update.py — Step 3: Neo4j graph sync
 - match.py — Step 4: Match diagnosis vs target position
 - learning_path.py — Step 5: Derive learning path from match gaps

Each module exposes plain ``async def run_*_step(...) -> LoopStepResult``
functions that can be invoked independently of ``LoopOrchestrator`` (the
compat shell still calls them via thin delegation). All shared types live
in ``loop.common``.
"""
from __future__ import annotations

__all__: list[str] = []
