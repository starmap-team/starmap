"""Sync Neo4j data from old container (localhost:7474) to prod container.

Connects to both neo4j instances via bolt and replays:
- All nodes
- All relationships
- All constraints/indexes (skipped - use existing schema)
"""
import asyncio
import sys
from neo4j import AsyncGraphDatabase


OLD_URI = "bolt://localhost:7687"
OLD_AUTH = ("neo4j", "starmap123456")
# prod is on Docker network; we can't connect directly from host,
# so we'll dump via HTTP and replay via the prod backend container.
# Instead, do this: dump to JSON via old neo4j HTTP API, then write file
# that gets pushed to backend container for replay.


async def dump_old_neo4j():
    """Dump all nodes + relationships from old neo4j to JSON files."""
    driver = AsyncGraphDatabase.driver(OLD_URI, auth=OLD_AUTH)
    nodes = []
    rels = []

    async with driver.session() as s:
        # All nodes
        result = await s.run("MATCH (n) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props")
        async for r in result:
            nodes.append({"id": r["id"], "labels": r["labels"], "props": dict(r["props"])})
        print(f"  Nodes: {len(nodes)}")

        # All relationships
        result = await s.run(
            "MATCH (a)-[r]->(b) RETURN id(r) AS id, type(r) AS type, "
            "id(a) AS source, id(b) AS target, properties(r) AS props"
        )
        async for r in result:
            rels.append({
                "id": r["id"], "type": r["type"],
                "source": r["source"], "target": r["target"],
                "props": dict(r["props"]),
            })
        print(f"  Relationships: {len(rels)}")

    await driver.close()
    return nodes, rels


def to_cypher(nodes, rels):
    """Convert nodes/rels to a single big Cypher script."""
    lines = []
    lines.append("// === Schema constraints ===")
    lines.append("CREATE CONSTRAINT knowledgearea_name IF NOT EXISTS FOR (n:KnowledgeArea) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT position_name IF NOT EXISTS FOR (n:Position) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (n:Skill) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT tool_name IF NOT EXISTS FOR (n:Tool) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT industry_name IF NOT EXISTS FOR (n:Industry) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (n:Domain) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT certificate_name IF NOT EXISTS FOR (n:Certificate) REQUIRE n.name IS UNIQUE;")
    lines.append("CREATE CONSTRAINT learningresource_name IF NOT EXISTS FOR (n:LearningResource) REQUIRE n.name IS UNIQUE;")
    lines.append("")
    lines.append("// === Nodes ===")
    for n in nodes:
        # Map old id → new variable name (in this script we re-use id)
        labels = ":".join(n["labels"])
        # Filter props to JSON-safe values (Neo4j Date/Time need conversion)
        safe_props = {}
        for k, v in n["props"].items():
            if v is None:
                continue
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif isinstance(v, (list, dict)):
                # truncate complex props to avoid cypher escaping issues
                v = str(v)[:200]
            safe_props[k] = v
        if not safe_props:
            continue
        # Use Cypher parameter syntax
        prop_str = ", ".join(f"{k}: ${k}_{n['id']}" for k in safe_props)
        lines.append(
            f"MERGE (n{labels.replace(':', '')}{n['id']}:{labels} {{name: $name_{n['id']}}}) "
            f"SET n{labels.replace(':', '')}{n['id']} += {{{prop_str}}};"
        )
        # Append params as separate file
    lines.append("// === Relationships ===")
    for r in rels:
        lines.append(
            f"MATCH (a{{id: {r['source']}}}), (b{{id: {r['target']}}}) "
            f"MERGE (a)-[:{r['type']}]->(b);"
        )
    return "\n".join(lines)


async def main():
    print("Step 1: Dump from old neo4j...")
    nodes, rels = await dump_old_neo4j()

    print("Step 2: Build cypher script...")
    cypher = to_cypher(nodes, rels)

    with open("C:/Users/LiShuai/Desktop/Agents/starmap/backend/_sync_neo4j.cypher", "w") as f:
        f.write(cypher)
    print(f"  Written: _sync_neo4j.cypher ({len(cypher)} bytes)")


asyncio.run(main())