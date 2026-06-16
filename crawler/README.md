# R1 罗智峰 - 后端-数据 爬虫模块

**流A ｜ W1-W2 阶段1 M1 验收**

---

## 一、模块结构

```
crawler/
├── __init__.py
├── README.md
├── requirements.txt            # 独立依赖（不污染 backend）
├── config.py                   # 配置加载（从根 .env 读）
├── dedup.py                    # SimHash 去重
├── compliance.py               # 合规日志
├── persistence/                # 入库模块
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy ORM
│   ├── database.py             # engine/session 工厂
│   └── migrations/             # Alembic 迁移
│       ├── env.py
│       └── versions/
│           └── 0001_init_jd_raw.py
├── pipelines/                  # Scrapy 管道
│   ├── __init__.py
│   ├── clean.py                # 清洗 HTML/广告
│   ├── dedup.py                # 接入 dedup
│   └── persist.py              # 接入 persistence
├── spiders/
│   ├── lagou.py                # 拉勾
│   ├── job51.py                # 前程无忧
│   └── boss.py                 # BOSS直聘
├── tests/
│   ├── test_dedup.py
│   ├── test_persistence.py
│   └── fixtures/
│       └── sample_jd.json
└── run.py                      # CLI 入口
```

## 二、3 站点策略

| 站点 | 抓取方式 | 限速 | 反爬绕开 |
|---|---|---|---|
| 拉勾 | Scrapy | 1 req/2s | 随机 UA + Cookie |
| 前程无忧 | Scrapy | 1 req/2s | 随机 UA + 列表分页 |
| BOSS直聘 | Playwright | 1 req/3s | 无头浏览器 + 鼠标轨迹 |

## 三、运行

```bash
cd crawler
source .venv/Scripts/activate
python run.py --site lagou --max 100
python run.py --site 51job --max 100
python run.py --site bosszhipin --max 100
```

## 四、合规红线

- 必跑 `python -m crawler.compliance.check_robots <url>` 再开爬
- 任意请求间隔 < 1s → 自动暂停 60s
- 任意 HTTP 403/429 → 立即停爬并报警到群

> 维护人: R1 罗智峰 ｜ 更新于 2026-06-16
