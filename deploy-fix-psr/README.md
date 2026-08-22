# StarMap 公网服务器 PSR 修复部署指南

> 适用: 公网 47.120.72.196 部署的 StarMap
> 修复目标: 匹配诊断"差距分析空白" + 求职者分析"返回上传页"

## 根因

公网后端容器跑的 `extract_repo.py` **缺少 PSR 写入逻辑**:
抽取岗位时只写岗位+技能,从不写 `position_skill_relations`(技能关系表)
→ 岗位无 REQUIRES 边 → 匹配接口返回"暂无技能画像" → 差距分析空白

**验证证据**(公网 API 实测):
- 新抽取岗位 "Test PSR Check Engineer" 返回 4 技能,但匹配时 `match_score=0.0`
  `overall_assessment="该岗位在图谱中存在，但暂无技能画像（无 REQUIRES 关系）"`
- 公网 231 岗位中 71 个无技能关系

## 修复文件(共 3 个)

| 文件 | 用途 |
|---|---|
| `backend/app/repositories/extract_repo.py` | **核心修复**: 抽取时写 PSR(已提交 commit ff8b3e2) |
| `scripts/fix_psr_server.sh` | 一键部署脚本(替换文件+重启) |
| `scripts/backfill_psr_server.py` | 数据回填(补已有岗位的关系) |

## 部署步骤(服务器上执行)

### 方式 A: 一键脚本(推荐)

```bash
# 1. 从本地上传 3 个文件到服务器 /opt/starmap/ (scp 或任何方式)
scp backend/app/repositories/extract_repo.py root@47.120.72.196:/opt/starmap/
scp scripts/fix_psr_server.sh root@47.120.72.196:/opt/starmap/
scp scripts/backfill_psr_server.py root@47.120.72.196:/opt/starmap/

# 2. 执行部署脚本(替换容器内文件 + 重启 backend)
ssh root@47.120.72.196
cd /opt/starmap
bash fix_psr_server.sh

# 3. 数据回填(补已有岗位关系)
docker exec starmap-backend-prod python /opt/starmap/backfill_psr.py
#   或(容器名不同时)
docker exec starmap-backend python /opt/starmap/backfill_psr.py
```

### 方式 B: 手动(容器名不确定时)

```bash
# 1. 找到 backend 容器名
docker ps | grep backend

# 2. 替换容器内文件
docker cp extract_repo.py <容器名>:/app/app/repositories/extract_repo.py

# 3. 验证文件包含修复
docker exec <容器名> grep -c "position_skill_relations" /app/app/repositories/extract_repo.py
#   应输出 >= 2

# 4. 重启容器
docker restart <容器名>
```

## 验证修复生效

```bash
# 1. 服务健康
curl -sf http://localhost:8000/health && echo OK

# 2. 抽取一个新岗位,确认自动写 PSR
#    在浏览器: 匹配诊断 → 上传简历 → 选岗 → 差距分析应显示内容
#    或 API: POST /api/v1/match/position {"target_position":"<刚抽取的岗位>",...}
#    应返回 skill_gap_detail 非空,而非"暂无技能画像"
```

## 回填后建议

回填后跑一次对账,让 Neo4j 同步新关系:
```bash
# 浏览器 Admin → 图谱对账,或
curl -X POST http://localhost:8000/api/v1/admin/reconcile-neo4j \
  -H "Authorization: Bearer <token>"
```

## 附: 本地已完成的验证

- 本地容器实测: extract_repo 修复后新岗位自动写 PSR(Engineering Manager 0→6 关系)
- 本地 playwright 全流程: 匹配诊断 Step3/4 正常渲染, 求职者分析结果页正常
- 公网前端 = 本地构建 dist(无前端问题)
