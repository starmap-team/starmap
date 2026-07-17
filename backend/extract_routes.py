"""Extract all backend API routes with their database dependencies."""
import os
import re

api_dir = os.path.join(os.path.dirname(__file__), "app", "api", "v1")
routes = []

for f in sorted(os.listdir(api_dir)):
    if not f.endswith(".py") or f.startswith("__"):
        continue
    filepath = os.path.join(api_dir, f)
    with open(filepath, encoding="utf-8") as fh:
        content = fh.read()

    prefix_m = re.search(r'prefix=["\'](/?\w+)["\']', content)
    prefix = prefix_m.group(1) if prefix_m else ""

    for m in re.finditer(r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']', content):
        method, path = m.group(1).upper(), m.group(2)
        full = prefix + path

        summary_m = re.search(r'summary=["\']([^"\']+)["\']', content[m.end():m.end() + 300])
        summary = summary_m.group(1) if summary_m else ""

        deps = []
        chunk = content[max(0, m.start() - 200):m.end() + 1000]
        if "neo4j_driver" in chunk or "get_neo4j_driver" in chunk:
            deps.append("Neo4j")
        if "get_db_session" in chunk or "AsyncSession" in chunk:
            deps.append("PG")
        if "get_redis_client" in chunk or "redis" in chunk.lower():
            deps.append("Redis")

        routes.append((f, method, full, summary, "+".join(deps) or "none"))

for r in routes:
    print(f"{r[0]:30s} {r[1]:6s} {r[2]:55s} {r[3]:35s} {r[4]}")
