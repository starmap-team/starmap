"""Check Neo4j data and graph endpoint behavior."""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.config import settings
from app.services.resources import resources
import httpx


async def main():
    # 1. Direct Neo4j count
    if resources.neo4j_driver is None:
        from app.services.resources import init_resources
        await init_resources()
    async with resources.neo4j_driver.session() as session:
        result = await session.run("MATCH (n) RETURN count(n) AS nodes, labels(n) AS labels")
        record = await result.single()
        print(f"Neo4j total nodes: {record['nodes']}")

        # Per-label counts
        result2 = await session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC"
        )
        print("Per-label counts:")
        async for rec in result2:
            print(f"  {rec['label']}: {rec['cnt']}")

        # Total relationships
        result3 = await session.run("MATCH ()-[r]->() RETURN count(r) AS rels")
        rec3 = await result3.single()
        print(f"Total relationships: {rec3['rels']}")

    await resources.close()

    # 2. Test graph endpoints
    print("\n=== Graph endpoints via running backend ===")
    # Login first
    import urllib.request, urllib.error, json
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username": "admin", "password": "starmap2024"}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        token = json.loads(r.read())["access_token"]
    print(f"Got token: {token[:30]}...")

    # Try several graph endpoints
    for path in [
        "/api/v1/graph/overview",
        "/api/v1/graph/nodes",
        "/api/v1/graph/positions",
        "/api/v1/graph/skills",
        "/api/v1/positions",
        "/api/v1/skills",
        "/api/v1/panorama",
    ]:
        req = urllib.request.Request(
            f"http://localhost:8000{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                body = json.loads(r.read())
                # Truncate
                text = json.dumps(body, ensure_ascii=False)
                print(f"\n[{r.status}] {path}: {len(text)} chars")
                print(f"   preview: {text[:300]}")
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
            except Exception:
                body = {}
            print(f"\n[{e.code}] {path}: {body}")
        except Exception as e:
            print(f"\n[ERR] {path}: {type(e).__name__}: {e}")


asyncio.run(main())