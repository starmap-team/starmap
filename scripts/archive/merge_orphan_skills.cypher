// ─────────────────────────────────────────────────────────────
// D5 fix (2026-08-12): 孤儿 Skill 合并（修正版 —— coalesce 单目标）
// exact-name canonical 优先；无 exact 则取大小写不敏感唯一匹配。
// 处理 pytest/Pytest 双 canonical 的情况（PG 侧也有大小写双行，另行 dedup 记录）
// ─────────────────────────────────────────────────────────────

// 1. Skill: 迁移 REQUIRES 边（单目标 coalesce）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
OPTIONAL MATCH (c1:Skill) WHERE c1.canonical_id IS NOT NULL AND c1.name = o.name
OPTIONAL MATCH (c2:Skill) WHERE c2.canonical_id IS NOT NULL AND toLower(c2.name) = toLower(o.name) AND (c1 IS NULL OR c2 <> c1)
WITH o, coalesce(c1, c2) AS c
WHERE c IS NOT NULL
MATCH (o)-[r:REQUIRES]->(s)
MERGE (c)-[:REQUIRES]->(s)
WITH o, r DELETE r;

// 2. Skill: 迁移 PREREQUISITE 边
MATCH (o:Skill) WHERE o.canonical_id IS NULL
OPTIONAL MATCH (c1:Skill) WHERE c1.canonical_id IS NOT NULL AND c1.name = o.name
OPTIONAL MATCH (c2:Skill) WHERE c2.canonical_id IS NOT NULL AND toLower(c2.name) = toLower(o.name) AND (c1 IS NULL OR c2 <> c1)
WITH o, coalesce(c1, c2) AS c
WHERE c IS NOT NULL
MATCH (o)-[r:PREREQUISITE]->(s)
MERGE (c)-[:PREREQUISITE]->(s)
WITH o, r DELETE r;

// 3. Skill: 迁移 USES 边（如有）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
OPTIONAL MATCH (c1:Skill) WHERE c1.canonical_id IS NOT NULL AND c1.name = o.name
OPTIONAL MATCH (c2:Skill) WHERE c2.canonical_id IS NOT NULL AND toLower(c2.name) = toLower(o.name) AND (c1 IS NULL OR c2 <> c1)
WITH o, coalesce(c1, c2) AS c
WHERE c IS NOT NULL
MATCH (o)-[r:USES]->(s)
MERGE (c)-[:USES]->(s)
WITH o, r DELETE r;

// 4. Skill: 删除已合并孤儿（仅删存在 canonical 目标者；9 个待提升新技能无目标，保留）
MATCH (o:Skill) WHERE o.canonical_id IS NULL
OPTIONAL MATCH (c1:Skill) WHERE c1.canonical_id IS NOT NULL AND c1.name = o.name
OPTIONAL MATCH (c2:Skill) WHERE c2.canonical_id IS NOT NULL AND toLower(c2.name) = toLower(o.name) AND (c1 IS NULL OR c2 <> c1)
WITH o, coalesce(c1, c2) AS c
WHERE c IS NOT NULL
DETACH DELETE o;
