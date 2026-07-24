# StarMap 脚本目录

本目录保存可重复执行的初始化、同步、质量和验证工具。一次性调试脚本不应继续堆在仓库根目录。

## 分类

| 类别 | 入口示例 |
|---|---|
| 契约/Schema | `export_json_schemas.py`、`check-contract-sync.js`、`verify-contract.ts` |
| 数据库/图谱初始化 | `init_neo4j_schema.py`、`import_esco_skill.py` |
| PG/Neo4j 同步 | `rebuild_graph.py`、`reconcile_graph.py`、`sync_extractions_to_graph.py` |
| 数据一致性 | `ensure_data_consistency.py`、`validate_graph_data.py` |
| 评估与质量 | `measure_*.py`、`quality_report.py` |
| 离线 fixture | `offline/`；不得混入生产数据 |
| 已废弃 | `deprecated/`；只用于历史参考 |
| 运维 | `daily-integration.sh`、`server-*.sh`、`deploy-lightweight.sh` |

## 使用规则

- 先运行 `<script> --help` 并确认当前环境、数据库和目标范围。
- 可能写数据库或重建图投影的脚本在运行前必须备份并核对连接参数。
- Python 脚本通常从仓库根或 `backend` Poetry 环境执行，具体以 import 路径为准。
- fixture、demo、离线脚本必须保持显式命名，不能伪装成真实采集结果。
- 新脚本必须幂等或明确声明非幂等，并提供 dry-run/确认机制（适用时）。

常用验证：

```bash
python starmap-contracts/validate.py
cd backend && poetry run python ../scripts/export_json_schemas.py
cd .. && pwsh -File scripts/check-docs.ps1
```