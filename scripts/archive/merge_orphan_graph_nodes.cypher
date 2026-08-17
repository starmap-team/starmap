// ─────────────────────────────────────────────────────────────
// D5 fix (2026-08-12): 孤儿图节点合并 —— 同名 canonical 重复节点去重
// 7 orphan Position + 4 orphan Skill（含大小写变体 Fastapi→FastAPI / Postgresql→PostgreSQL）
// 边迁移到 canonical 节点后删除孤儿。备份见 docs/archive/orphan-graph-backup-2026-08-12.txt
// ─────────────────────────────────────────────────────────────

// 1. Position: 迁移 REQUIRES 边
MATCH (o:Position) WHERE o.canonical_id IS NULL
MATCH (c:Position {name: o.name}) WHERE c.canonical_id IS NOT NULL
MATCH (o)-[r:REQUIRES]->(s)
MERGE (c)-[:REQUIRES]->(s)
WITH o, r DELETE r;

// 2. Position: 迁移 USES 边
MATCH (o:Position) WHERE o.canonical_id IS NULL
MATCH (c:Position {name: o.name}) WHERE c.canonical_id IS NOT NULL
MATCH (o)-[r:USES]->(s)
MERGE (c)-[:USES]->(s)
WITH o, r DELETE r;

// 3. Position: 删除孤儿节点（无边残留）
MATCH (o:Position) WHERE o.canonical_id IS NULL
DELETE o;

// 4. Skill: 迁移 REQUIRES 边（大小写不敏感匹配 canonical）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
MATCH (c:Skill) WHERE c.canonical_id IS NOT NULL AND toLower(c.name) = toLower(o.name)
MATCH (o)-[r:REQUIRES]->(s)
MERGE (c)-[:REQUIRES]->(s)
WITH o, r DELETE r;

// 5. Skill: 迁移 PREREQUISITE 边
MATCH (o:Skill) WHERE o.canonical_id IS NULL
MATCH (c:Skill) WHERE c.canonical_id IS NOT NULL AND toLower(c.name) = toLower(o.name)
MATCH (o)-[r:PREREQUISITE]->(s)
MERGE (c)-[:PREREQUISITE]->(s)
WITH o, r DELETE r;

// 6. Skill: 迁移 USES 边（如有）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
MATCH (c:Skill) WHERE c.canonical_id IS NOT NULL AND toLower(c.name) = toLower(o.name)
MATCH (o)-[r:USES]->(s)
MERGE (c)-[:USES]->(s)
WITH o, r DELETE r;

// 7. Skill: 删除已合并的孤儿（仅剩 9 个待提升的新技能，它们不匹配 canonical 同名校验，不会被误删）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
AND EXISTS { MATCH (c:Skill) WHERE c.canonical_id IS NOT NULL AND toLower(c.name) = toLower(o.name) }
DELETE o;
