# StarMap 数据采集模块

`crawler/` 负责招聘数据采集、robots/限速合规、清洗、去重、持久化和后端流水线桥接。

## 当前来源状态

- `spiders/v2ex_remote.py` 是当前 `spiders/` 下唯一活跃实现。
- BOSS、拉勾和 51Job 的旧实现位于 `spiders/_disabled/`，不得注册为 active。
- `scripts/apify_*.py` 是按需的云采集工具，不等同于本地 spider。
- 数据源启停和抓取参数应由 `DataSourceRecord`/流水线配置驱动。

## 结构

| 路径 | 职责 |
|---|---|
| `compliance.py` | robots、限速和请求审计 |
| `dedup.py` | SimHash 等去重逻辑 |
| `middleware/` | 代理选择与失败熔断 |
| `persistence/` | crawler 本地 DAO、模型和迁移 |
| `pipelines/` | 清洗、增量处理、质量和存储 |
| `spiders/` | 活跃与禁用来源实现 |
| `scripts/` | Apify、ESCO、导出和联调工具 |
| `pipeline_bridge.py` | 与后端 pipeline 的边界 |

## 运行

从仓库根执行：

```bash
python -m crawler.run --help
python -m pytest crawler/tests -v
```

需要 Playwright、Apify token 或数据库的命令必须先阅读脚本参数和环境变量，不要把历史 PR 描述中的示例当成当前 CLI 契约。

## 合规要求

- robots 检查失败或明确拒绝时停止该来源，不以 stealth 作为绕过依据。
- 遇到 403/429 时触发退避或熔断并保留审计记录。
- 采集频率、代理和目标站点条款必须经数据合规确认。
- 禁止在代码和文档中保存账号、Cookie、代理凭据或数据库密码。