# Git operations for M1 delivery
$repo = "E:\java1\starmap"
Set-Location $repo

# Check if git repo
if (Test-Path ".git") {
    Write-Output "=== GIT REPO EXISTS ==="
    git status
    Write-Output "=== LOG ==="
    git log --oneline -5
    Write-Output "=== BRANCHES ==="
    git branch -a
} else {
    Write-Output "=== NOT A GIT REPO ==="
    Write-Output "Initializing..."
    git init
    git add .
    git -c user.name="杨博文" -c user.email="yang.bowen@starmap.com" commit -m "M1 契约交付 - 杨博文 2026-06-16

交付内容:
  1. openapi.yaml v1 (15 endpoints, 12 schemas)
  2. 共享Pydantic模型 22个
  3. Neo4j本体7类节点+8类关系 (§2.1/§2.2)
  4. PostgreSQL 8张表 (Alembic 001+002)
  5. Cypher查询模板15个
  6. ESCO种子127技能
  7. JD抽取管线 (Prompt+星火API+归一化+防幻觉)
  8. 评测模块 (F1评估+5条Golden)

基础设施:
  - Docker: neo4j/postgres/redis/chroma 全运行
  - 测试: pytest 28/28通过
  - E2E: 星火API真实调用成功"
    git branch -M r3/yangbowen/m1
}
