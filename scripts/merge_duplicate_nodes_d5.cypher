// ─────────────────────────────────────────────────────────────
// D5 fix (2026-08-12): 合并同名重复节点（canonical_id 已链接但节点未合并的副本）
// 背景: link_orphan_canonical_ids_d5.py 只 SET canonical_id 未合并节点 →
// 同名同 canonical_id 双节点并存（graph-promotion-d5 提升的 skill 每个都有副本）→
// 每对节点生成 2 条 REQUIRES 边（双库不统一根因）。
// 策略: 按 name 分组，保留 nodes[0]（elementId 最小），其余节点全类型双向迁移边后删除。
// 幂等: 无重复组时 no-op。运行: cypher-shell -f scripts/merge_duplicate_nodes_d5.cypher
// ─────────────────────────────────────────────────────────────

// ---- 1. Skill 同名重复节点合并 ----
MATCH (s:Skill)
WITH s.name AS name, collect(s) AS nodes
WHERE size(nodes) > 1
WITH nodes[0] AS keep, nodes[1..] AS dups
UNWIND dups AS dup
WITH keep, dup
// REQUIRES 出边
MATCH (dup)-[r:REQUIRES]->(x) MERGE (keep)-[nr:REQUIRES]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:REQUIRES]->(dup) MERGE (x)-[nr:REQUIRES]->(keep) SET nr += r DELETE r
WITH keep, dup
// PREREQUISITE 出边/入边
MATCH (dup)-[r:PREREQUISITE]->(x) MERGE (keep)-[nr:PREREQUISITE]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:PREREQUISITE]->(dup) MERGE (x)-[nr:PREREQUISITE]->(keep) SET nr += r DELETE r
WITH keep, dup
// USES 出边/入边
MATCH (dup)-[r:USES]->(x) MERGE (keep)-[nr:USES]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:USES]->(dup) MERGE (x)-[nr:USES]->(keep) SET nr += r DELETE r
WITH keep, dup
// BELONGS_TO 出边/入边
MATCH (dup)-[r:BELONGS_TO]->(x) MERGE (keep)-[nr:BELONGS_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:BELONGS_TO]->(dup) MERGE (x)-[nr:BELONGS_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
// APPLIES_TO 出边/入边
MATCH (dup)-[r:APPLIES_TO]->(x) MERGE (keep)-[nr:APPLIES_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:APPLIES_TO]->(dup) MERGE (x)-[nr:APPLIES_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
// RECOMMENDED_FOR 出边/入边
MATCH (dup)-[r:RECOMMENDED_FOR]->(x) MERGE (keep)-[nr:RECOMMENDED_FOR]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:RECOMMENDED_FOR]->(dup) MERGE (x)-[nr:RECOMMENDED_FOR]->(keep) SET nr += r DELETE r
WITH keep, dup
// EVOLVES_TO 出边/入边
MATCH (dup)-[r:EVOLVES_TO]->(x) MERGE (keep)-[nr:EVOLVES_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:EVOLVES_TO]->(dup) MERGE (x)-[nr:EVOLVES_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
// 删除空副本
DETACH DELETE dup
RETURN count(dup) AS skills_merged;

// ---- 2. Position 同名重复节点合并 ----
MATCH (p:Position)
WITH p.name AS name, collect(p) AS nodes
WHERE size(nodes) > 1
WITH nodes[0] AS keep, nodes[1..] AS dups
UNWIND dups AS dup
WITH keep, dup
MATCH (dup)-[r:REQUIRES]->(x) MERGE (keep)-[nr:REQUIRES]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:REQUIRES]->(dup) MERGE (x)-[nr:REQUIRES]->(keep) SET nr += r DELETE r
WITH keep, dup
MATCH (dup)-[r:USES]->(x) MERGE (keep)-[nr:USES]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:USES]->(dup) MERGE (x)-[nr:USES]->(keep) SET nr += r DELETE r
WITH keep, dup
MATCH (dup)-[r:BELONGS_TO]->(x) MERGE (keep)-[nr:BELONGS_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:BELONGS_TO]->(dup) MERGE (x)-[nr:BELONGS_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
MATCH (dup)-[r:APPLIES_TO]->(x) MERGE (keep)-[nr:APPLIES_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:APPLIES_TO]->(dup) MERGE (x)-[nr:APPLIES_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
MATCH (dup)-[r:RECOMMENDED_FOR]->(x) MERGE (keep)-[nr:RECOMMENDED_FOR]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:RECOMMENDED_FOR]->(dup) MERGE (x)-[nr:RECOMMENDED_FOR]->(keep) SET nr += r DELETE r
WITH keep, dup
MATCH (dup)-[r:EVOLVES_TO]->(x) MERGE (keep)-[nr:EVOLVES_TO]->(x) SET nr += r DELETE r
WITH keep, dup
MATCH (x)-[r:EVOLVES_TO]->(dup) MERGE (x)-[nr:EVOLVES_TO]->(keep) SET nr += r DELETE r
WITH keep, dup
DETACH DELETE dup
RETURN count(dup) AS positions_merged;
