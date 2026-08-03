"""Densify fixture JDExtractionRecords + run orchestrator, print summary."""
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, '.')
os.environ.setdefault('APP_ENV', 'development')

from sqlalchemy import func, select

from app.core.evolution.orchestrator import run_evolution_pipeline
from app.db.session import get_session_factory
from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
    SkillTimeseries,
)
from app.models.extraction_models import JDExtractionRecord


async def main():
    sf = get_session_factory()
    async with sf() as s:
        fixtures = [
            ('Python Backend Engineer', 'Senior Python backend for SaaS.',
             [('Python', 'hard', '熟悉'), ('FastAPI', 'hard', '熟悉'), ('PostgreSQL', 'hard', '熟悉'), ('Docker', 'tool', '了解')],
             [('Redis', 'tool', '了解')]),
            ('Data Analyst', 'Product metrics and A/B testing.',
             [('SQL', 'hard', '精通'), ('Python', 'hard', '熟悉'), ('Pandas', 'lib', '熟悉')],
             [('Tableau', 'tool', '了解')]),
            ('AI Engineer', 'LLM extraction pipelines.',
             [('Python', 'hard', '精通'), ('PyTorch', 'hard', '熟悉'), ('LangChain', 'framework', '熟悉')],
             [('Milvus', 'tool', '了解')]),
            ('Frontend Engineer', 'Vue3 + TypeScript dashboards.',
             [('Vue', 'hard', '精通'), ('TypeScript', 'hard', '精通'), ('Vite', 'tool', '熟悉')],
             [('G6', 'tool', '了解')]),
            ('DevOps Engineer', 'K8s platform.',
             [('Kubernetes', 'tool', '精通'), ('Docker', 'tool', '精通'), ('Terraform', 'tool', '熟悉')],
             [('Ansible', 'tool', '了解')]),
        ]
        now = datetime.now(UTC)
        seed = []
        # 灌 2 个相邻月份（带 30 天间隔），让 DiffEngine 真正能 diff
        for month_offset in [1, 2]:
            ts = now - timedelta(days=30 * month_offset)
            for rep in range(4):
                for pos_name, desc, req, pref in fixtures:
                    if month_offset == 1 and pos_name == 'Python Backend Engineer':
                        req = req + [('Redis', 'tool', '了解')]  # 加一项触发 added_required
                    payload = {
                        'position_name': pos_name, 'description': desc,
                        'required_skills': [{'name': n, 'category': c, 'level': p, 'importance': 'required'} for n, c, p in req],
                        'preferred_skills': [{'name': n, 'category': c, 'level': p, 'importance': 'bonus'} for n, c, p in pref],
                        'experience_required': 3, 'prompt_version': 'seeder-v2',
                        'validation': {'is_valid': True, 'confidence': 0.85, 'hallucinated_skills': [], 'issues': []},
                    }
                    seed.append(JDExtractionRecord(
                        jd_content=desc, job_title=pos_name,
                        extracted_skills=payload, experience_years=3,
                        confidence=0.85, hallucination_score=0.05,
                        status='completed',
                        created_at=ts - timedelta(hours=rep * 6),
                    ))
        # 当前月份
        ts0 = now
        for rep in range(4):
            for pos_name, desc, req, pref in fixtures:
                payload = {
                    'position_name': pos_name, 'description': desc,
                    'required_skills': [{'name': n, 'category': c, 'level': p, 'importance': 'required'} for n, c, p in req],
                    'preferred_skills': [{'name': n, 'category': c, 'level': p, 'importance': 'bonus'} for n, c, p in pref],
                    'experience_required': 3, 'prompt_version': 'seeder-v2',
                    'validation': {'is_valid': True, 'confidence': 0.85, 'hallucinated_skills': [], 'issues': []},
                }
                seed.append(JDExtractionRecord(
                    jd_content=desc, job_title=pos_name,
                    extracted_skills=payload, experience_years=3,
                    confidence=0.85, hallucination_score=0.05,
                    status='completed',
                    created_at=ts0 - timedelta(hours=rep * 6),
                ))
        s.add_all(seed)
        await s.commit()
        n_jd = (await s.execute(select(func.count(JDExtractionRecord.id)))).scalar()
        print(f'after_seed: jd_extractions={n_jd}')

        result = await run_evolution_pipeline(months_back=6)
        print('orchestrator_summary:')
        for k in ['positions_processed', 'snapshots_created', 'changelogs_written', 'paths_written', 'errors', 'warnings']:
            print(f'  {k}: {result.get(k)}')
        if result.get('timeseries'):
            print(f'  timeseries.skills_updated: {result["timeseries"].get("skills_updated")}')

        n_snap = (await s.execute(select(func.count(EvolutionSnapshot.id)))).scalar()
        n_log = (await s.execute(select(func.count(EvolutionChangelog.id)))).scalar()
        n_path = (await s.execute(select(func.count(EvolutionPath.id)))).scalar()
        n_ts = (await s.execute(select(func.count(SkillTimeseries.id)))).scalar()
        print(f'\nfinal DB rows: snapshots={n_snap} changelogs={n_log} paths={n_path} timeseries={n_ts}')


asyncio.run(main())
