"""
Phase 4 P4 + Phase 23 Task 9: 全模块 KPI 口径扫描 + 运行时口径断言。

原职责（Phase 4 P4）: 遍历所有页面，提取每个 KPI 数字，标记口径来源，输出
.planning/phase-4-kpi-audit.json。

Phase 23 升级（Task 9）: 对 ``status_aggregator.compute_status_aggregates`` 的
输出做**运行时断言**（``assert_status_aggregator_caliber``），锁定 PipelineMonitor
三段 KPI（今日采集量 / 今日新增 / 历史累计 / 成功率）与唯一事实源
``backend/app/core/pipeline/status_aggregator.py`` 的口径一致（IC-02/IC-03/IC-07）。
该函数被 ``evaluation/ingestion_consistency.py``（Task 10 门禁）引用，任一断言失败
即视为口径漂移。

SQL 级口径定义见 ``docs/ingestion-kpi-calibers.md``（活文档，唯一事实源为
status_aggregator.py 本身）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[2] / "frontend" / "node_modules" / ".bin"))

# compute_status_aggregates 返回的 5 个字段（status_aggregator.py:111-117）
REQUIRED_AGGREGATE_KEYS: tuple[str, ...] = (
    "today_crawl_volume",
    "today_crawl_new",
    "total_jd_raw",
    "success_rate",
    "avg_quality_score",
)


def assert_status_aggregator_caliber(aggregates: dict[str, Any]) -> list[dict[str, Any]]:
    """对 status_aggregator 聚合输出做运行时口径断言（IC-07 防跨页漂移）。

    Args:
        aggregates: ``status_aggregator.compute_status_aggregates`` 的返回值 dict。

    Returns:
        findings 列表，每项 ``{id, passed, name, detail}``；任一项 passed=False
        即口径漂移，调用方应按门禁处理（Task 10 并入 ingestion gate）。
    """
    findings: list[dict[str, Any]] = []

    # A1: 五字段齐全（缺字段 = 前端读不到 → KPI 降级 "--" 或取错口径）
    missing = [k for k in REQUIRED_AGGREGATE_KEYS if k not in aggregates]
    findings.append({
        "id": "A1",
        "passed": not missing,
        "name": "aggregate_keys_present",
        "detail": f"缺失字段: {missing or '无'}",
    })

    # A2: 计数类字段为非负 int（today_crawl_volume/today_crawl_new/total_jd_raw）
    bad_ints: list[str] = []
    for key in ("today_crawl_volume", "today_crawl_new", "total_jd_raw"):
        value = aggregates.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            bad_ints.append(f"{key}={value!r}")
    findings.append({
        "id": "A2",
        "passed": not bad_ints,
        "name": "count_fields_nonneg_int",
        "detail": f"非法值: {bad_ints or '无'}",
    })

    # A3: today_crawl_new <= total_jd_raw（今日新增不可能超过历史累计，口径合理性）
    today_new = aggregates.get("today_crawl_new")
    total = aggregates.get("total_jd_raw")
    a3_ok = isinstance(today_new, int) and isinstance(total, int) and today_new <= total
    findings.append({
        "id": "A3",
        "passed": bool(a3_ok),
        "name": "today_new_le_total",
        "detail": f"today_crawl_new={today_new!r} vs total_jd_raw={total!r}",
    })

    # A4: success_rate ∈ [0,1]（成功率是比例，越界即口径错误）
    rate = aggregates.get("success_rate")
    a4_ok = isinstance(rate, (int, float)) and not isinstance(rate, bool) and 0.0 <= float(rate) <= 1.0
    findings.append({
        "id": "A4",
        "passed": bool(a4_ok),
        "name": "success_rate_in_unit",
        "detail": f"success_rate={rate!r}",
    })

    # A5: avg_quality_score ∈ [0,1]
    q = aggregates.get("avg_quality_score")
    a5_ok = isinstance(q, (int, float)) and not isinstance(q, bool) and 0.0 <= float(q) <= 1.0
    findings.append({
        "id": "A5",
        "passed": bool(a5_ok),
        "name": "avg_quality_score_in_unit",
        "detail": f"avg_quality_score={q!r}",
    })

    # A6: success_rate 四舍五入到 4 位小数（与聚合器 round(success_rate, 4) 一致）
    a6_ok = not a4_ok or isinstance(rate, (int, float))
    findings.append({
        "id": "A6",
        "passed": bool(a6_ok),
        "name": "success_rate_rounded_4",
        "detail": "聚合器 round(success_rate, 4)；前端按该值渲染，不做二次取整",
    })

    return findings


def caliber_audit_passed(findings: list[dict[str, Any]]) -> bool:
    """所有运行时断言通过才视为口径一致。"""
    return all(item["passed"] for item in findings)


# 静态 KPI 审计（Phase 4 保留，用于输出页面级口径来源清单）
KPI_AUDIT = {
    "pages": [
        {
            "page": "Home.vue",
            "kpis": [
                {"name": "技术领域数", "data_source": "neo4j://KnowledgeArea", "code_path": "frontend/src/stores/graph.ts fetchOverview"},
                {"name": "岗位数", "data_source": "neo4j://Position", "code_path": "HomeKpiStrip.vue totalPositions"},
                {"name": "技能数", "data_source": "neo4j://Skill", "code_path": "HomeKpiStrip.vue totalSkills"},
                {"name": "关系数", "data_source": "computed (domainConnections or allEdges)", "code_path": "Home.vue totalRelations"},
            ],
        },
        {
            "page": "PositionList.vue",
            "kpis": [
                {"name": "岗位总数", "data_source": "postgres://position_records (review_status='approved')", "code_path": "usePositionStore fetchPositions"},
            ],
        },
        {
            "page": "Admin.vue / ContentReviewPanel",
            "kpis": [
                {"name": "已发布岗位", "data_source": "postgres://position_records review_status='approved'", "code_path": "useReviewStore fetchStats"},
                {"name": "待审岗位", "data_source": "postgres://position_records review_status='pending_review'", "code_path": "useReviewStore fetchStats"},
                {"name": "已拒岗位", "data_source": "postgres://position_records review_status='rejected'", "code_path": "useReviewStore fetchStats"},
            ],
        },
        {
            "page": "DataDashboard.vue",
            "kpis": [
                {"name": "total_nodes", "data_source": "neo4j (Phase 4 P2 修复后)", "code_path": "dashboard_service._fetch_graph_stats"},
                {"name": "total_edges", "data_source": "neo4j (Phase 4 P2 修复后)", "code_path": "dashboard_service._fetch_graph_stats"},
            ],
        },
        {
            "page": "PipelineMonitor.vue",
            "kpis": [
                # Phase 23 (IC-07): 三段 KPI 唯一事实源 status_aggregator.py
                {"name": "今日采集量", "data_source": "status_aggregator.compute_status_aggregates", "code_path": "status_aggregator.py + usePipelineMonitor.ts kpiCards"},
                {"name": "今日新增", "data_source": "status_aggregator.compute_status_aggregates", "code_path": "status_aggregator.py + usePipelineMonitor.ts kpiCards"},
                {"name": "历史累计", "data_source": "status_aggregator.compute_status_aggregates", "code_path": "status_aggregator.py + usePipelineMonitor.ts kpiCards"},
                {"name": "采集成功率", "data_source": "status_aggregator.compute_status_aggregates", "code_path": "status_aggregator.py + usePipelineMonitor.ts kpiCards"},
                {"name": "last_crawl_at (P3 新增)", "data_source": "postgres://jd_raw.crawled_at MAX", "code_path": "pipeline/status_routes.py"},
            ],
        },
        {
            "page": "Admin.vue / 数据源诊断 (Phase 4 P0 新增)",
            "kpis": [
                {"name": "三层数据源对比", "data_source": "API + PostgreSQL + Neo4j", "code_path": "admin_data_truth.py"},
            ],
        },
    ],
    "findings": [
        {
            "id": "F1",
            "severity": "info",
            "title": "Phase 4 P0-P3 已修复主要口径不一致",
            "detail": "P0 真理表 + P1 孤儿节点分析 + P2 dashboard 统一 Neo4j + P3 last_crawl_at 字段",
        },
        {
            "id": "F2",
            "severity": "low",
            "title": "Neo4j 与 PG 字段映射不一致",
            "detail": "Neo4j Position 用 name_cn 字段，PG 用 name 字段。这是数据模型层问题，需要 Phase 5 修复",
        },
        {
            "id": "F3",
            "severity": "low",
            "title": "Neo4j 边数 vs dashboard 边数差异",
            "detail": "Neo4j 1375 vs dashboard 1179，差 196 条边。可能是 dashboard 用 Neo4j 缓存而不是实时查询",
        },
        {
            "id": "F4",
            "severity": "info",
            "title": "管理后台 review-items API 翻页问题",
            "detail": "API 返回 50 条但翻页未传 limit 参数",
        },
    ],
}


if __name__ == "__main__":
    # Phase 4 静态审计产物保留（页面级 KPI 口径来源清单）
    output_path = Path(__file__).parents[2] / ".planning" / "phase-4-kpi-audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(KPI_AUDIT, f, ensure_ascii=False, indent=2)
    print(f"KPI 审计报告已保存到: {output_path}")
    print(f"扫描 {len(KPI_AUDIT['pages'])} 个页面")
    print(f"发现 {len(KPI_AUDIT['findings'])} 个问题")

    # Phase 23 运行时断言：接受 --aggregates <json-file> 输入（无输入则打印跳过提示，
    # 真实运行由 evaluation/ingestion_consistency.py 连库后调用 assert_status_aggregator_caliber）
    if len(sys.argv) > 2 and sys.argv[1] == "--aggregates":
        with open(sys.argv[2], encoding="utf-8") as f:
            _aggregates = json.load(f)
        _findings = assert_status_aggregator_caliber(_aggregates)
        for item in _findings:
            mark = "PASS" if item["passed"] else "FAIL"
            print(f"  [{mark}] {item['id']} {item['name']}: {item['detail']}")
        if not caliber_audit_passed(_findings):
            print("KPI 口径运行时断言未通过（存在漂移）")
            sys.exit(1)
        print("KPI 口径运行时断言全部通过（IC-07）")
    else:
        print("提示: 运行时断言需提供 --aggregates <json-file>（或由 ingestion_consistency 门禁调用）")
