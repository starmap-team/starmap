# 数据源契约 v1（草稿，待 R0 李帅 + R3 杨博文签字）

**Owner**: R1 罗智峰（后端-数据） ｜ **Reviewers**: R0 李帅、R3 杨博文
**适用**: 阶段1（M1 验收）｜ **W2 周五前必须签字**

---

## 一、目标

明确「R1 爬虫 → jd_raw 表 → R3 抽取」的输入输出契约，让 R3 杨博文 在 W3 可以并行开发抽取引擎而**不需要等 R1 真把 300 条都跑出来**。

## 二、数据源清单（D5 决策：异构数据最小可行 3 源）

| 源 | 站点 | 难度 | 单源目标 | 抓取方式 | 备注 |
|---|---|---|---|---|---|
| **S1** | 拉勾网 | ⭐ | 100 条 | Scrapy（列表 + 详情） | 反爬最弱，首选 |
| **S2** | 前程无忧 | ⭐⭐ | 100 条 | Scrapy | 列表页结构稳定 |
| **S3** | BOSS直聘 | ⭐⭐⭐⭐ | 100 条 | Playwright | 反爬最强，备用 |
| **合计** | - | - | **≥300 条** | - | M1 验收硬指标 |

> ⚠️ 如果 S3 BOSS 直爬不动，**R0 李帅有 24h 内决定是否替换为猎聘 / 智联**。

## 三、关键词白名单（D8：聚焦新一代信息技术领域）

爬虫只抓以下 5 类关键词的 JD（其他关键词的 JD 不入库）：

```
1. Python
2. Java
3. 算法
4. 前端
5. 大模型 / LLM / AIGC
```

## 四、jd_raw 表契约（PostgreSQL schema）

```sql
CREATE TABLE jd_raw (
    id              BIGSERIAL PRIMARY KEY,
    source_site     VARCHAR(32)  NOT NULL,    -- 'lagou' | '51job' | 'bosszhipin'
    source_url      TEXT         NOT NULL UNIQUE,  -- 原始详情页 URL（去重键）
    raw_html        TEXT,                      -- 原始 HTML（清洗前，可选）
    clean_text      TEXT         NOT NULL,    -- 清洗后正文
    job_title       VARCHAR(200) NOT NULL,
    company         VARCHAR(200),
    salary_min      INT,                       -- 单位元/月，nullable
    salary_max      INT,
    location        VARCHAR(100),
    publish_date    DATE,
    crawled_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    content_hash    CHAR(64)     NOT NULL,    -- SimHash（16进制64字符）
    status          VARCHAR(16)  NOT NULL DEFAULT 'raw',  -- raw | extracted | failed
    error_msg       TEXT                      -- 抽取失败原因
);

CREATE INDEX idx_jd_raw_status        ON jd_raw(status);
CREATE INDEX idx_jd_raw_source_site   ON jd_raw(source_site);
CREATE INDEX idx_jd_raw_crawled_at    ON jd_raw(crawled_at DESC);
CREATE INDEX idx_jd_raw_content_hash  ON jd_raw(content_hash);
```

**字段约束（强契约，违反即拒收）**：

| 字段 | 是否可空 | 取值范围 / 格式 | 验证方式 |
|---|---|---|---|
| source_site | NOT NULL | 枚举：lagou / 51job / bosszhipin | Pydantic enum |
| source_url | NOT NULL | 合法 URL，唯一 | UNIQUE 约束 |
| clean_text | NOT NULL | 长度 200-20000 字符 | Pydantic |
| job_title | NOT NULL | 长度 2-100 | Pydantic |
| salary_min/max | NULLABLE | 0 < x < 1000000 | Pydantic |
| content_hash | NOT NULL | 64 位 hex（SimHash 输出） | SimHash 工具 |
| status | NOT NULL | 枚举：raw / extracted / failed | 默认 raw |

## 五、compliance_log 表契约（合规审计）

```sql
CREATE TABLE compliance_log (
    id              BIGSERIAL PRIMARY KEY,
    source_site     VARCHAR(32)  NOT NULL,
    target_url      TEXT         NOT NULL,
    robots_allowed  BOOLEAN      NOT NULL,
    user_agent      VARCHAR(200) NOT NULL,
    qps             FLOAT        NOT NULL,     -- 实际请求间隔（秒）
    response_code   INT          NOT NULL,
    response_bytes  INT,
    crawled_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**4 项硬规则（红线）**：

1. ✅ **robots.txt 检查**：先 `GET /robots.txt`，解析 `Disallow`，命中则不入库
2. ✅ **QPS ≤ 1**：相邻请求间隔 ≥ 1 秒
3. ✅ **只爬公开数据**：禁止登录态抓取、禁止绕验证码
4. ✅ **完整日志**：每条请求记一行 `compliance_log`

## 六、SimHash 去重契约

- 工具函数：`simhash(text: str) -> int`（64-bit）
- 字段映射：`content_hash = format(simhash(clean_text), '016x')`（零填充 16 位 hex）
- 距离阈值：**Hamming 距离 ≤ 3** 视为重复
- 重复处理：保留先入库的，后到的直接 `UPDATE jd_raw SET status='duplicate'`

## 七、交付物清单（M1 验收 6/19 周五前）

- [ ] 3 个站点的爬虫代码 `crawler/spiders/{lagou,51job,bosszhipin}.py`
- [ ] SimHash 去重工具 `crawler/dedup.py`
- [ ] SQLAlchemy ORM 模型 + Alembic 迁移 `crawler/persistence/`
- [ ] compliance_log 写入逻辑 `crawler/compliance.py`
- [ ] 入库 ≥300 条 `jd_raw`（数据可在 mock 模式下生成，但 schema 必须真实）
- [ ] 单元测试 `crawler/tests/`，覆盖率 ≥60%

## 八、R1 ↔ R3 交付时序

```
R1 W2 周五 22:00:  jd_raw schema 签字 + 50 条真实数据入库（验证 pipeline）
R1 W3 周一 22:00: 300 条入库
R3 W3 周三 22:00: 抽取 pipeline 接 jd_raw 表，开始联调
```

## 九、签字栏

| 角色 | 姓名 | 签字 | 时间 |
|---|---|---|---|
| 提供方 R1 | 罗智峰 | ☐ | 2026-06-19 |
| 接收方 R3 | 杨博文 | ☐ | 2026-06-19 |
| 仲裁 R0 | 李帅 | ☐ | 2026-06-19 |

---

> 草稿 v1 生成于 2026-06-16 by R1 罗智峰
> 请在群里 @ 上述 3 人确认 / 提出修改意见
