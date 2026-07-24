"""Stage 4+5: run orchestrator + verify APIs (after real LLM extraction)."""
import asyncio, os, sys, json, urllib.request
for k, v in {
    'POSTGRES_HOST': 'localhost', 'POSTGRES_PORT': '5433',
    'POSTGRES_USER': 'starmap', 'POSTGRES_PASSWORD': 'starmap123456',
    'POSTGRES_DB': 'starmap',
    'REDIS_URI': 'redis://localhost:6379/0',
    'NEO4J_URI': 'bolt://localhost:7687', 'NEO4J_USER': 'neo4j',
    'NEO4J_PASSWORD': 'starmap123456',
    'MIMO_API_KEY': '', 'DEEPSEEK_API_KEY': '', 'XUNFEI_API_KEY': '',
    'QWEN_MODEL_PATH': 'http://localhost:11434',
}.items():
    os.environ.setdefault(k, v)
sys.path.insert(0, '.')

from sqlalchemy import select, func
from app.db.session import get_session_factory
from app.models.extraction_models import JDExtractionRecord
from app.core.evolution.orchestrator import run_evolution_pipeline


async def main():
    sf = get_session_factory()
    async with sf() as s:
        n = (await s.execute(select(func.count(JDExtractionRecord.id)))).scalar() or 0
        print(f'JDExtractionRecord total = {n}')
        recent = (await s.execute(
            select(JDExtractionRecord).order_by(JDExtractionRecord.id.desc()).limit(2)
        )).scalars().all()
        for r in recent:
            data = r.extracted_skills or {}
            print(f'  recent id={str(r.id)[:8]} pos={data.get("position_name") or r.job_title!r}')

    print('\n--- run_evolution_pipeline(months_back=6) ---')
    result = await run_evolution_pipeline(months_back=6)
    for k in ['positions_processed', 'snapshots_created', 'changelogs_written', 'paths_written', 'errors', 'warnings']:
        print(f'  {k}: {result.get(k)}')
    if result.get('timeseries'):
        print(f'  timeseries.skills_updated: {result["timeseries"].get("skills_updated")}')
    if result.get('timeseries'):
        print(f'  timeseries.windows_created: {result["timeseries"].get("windows_created")}')

    print('\n--- API verify on :8001 ---')
    req = urllib.request.Request(
        'http://localhost:8001/api/v1/auth/login',
        data=json.dumps({'username': 'admin', 'password': 'starmap2024'}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    token = json.loads(urllib.request.urlopen(req).read())['access_token']
    auth = {'Authorization': f'Bearer {token}'}

    for ep in ['snapshots', 'changelog/Python', 'paths/all', 'emerging-skills', 'trends']:
        url = f'http://localhost:8001/api/v1/evolution/{ep}' + ('?limit=10' if 'all' in ep or 'snapshots' in ep or 'changelog' in ep else '')
        body = urllib.request.urlopen(urllib.request.Request(url, headers=auth)).read()
        data = json.loads(body)
        if isinstance(data, list):
            print(f'  {ep:25} : {len(data)} items')
        elif isinstance(data, dict):
            if 'items' in data:
                print(f'  {ep:25} : items={len(data["items"])}')
            elif 'history' in data:
                print(f'  {ep:25} : history_entries={len(data["history"])}')
            else:
                print(f'  {ep:25} : dict keys={list(data.keys())}')
        else:
            print(f'  {ep:25} : {type(data).__name__}')


asyncio.run(main())