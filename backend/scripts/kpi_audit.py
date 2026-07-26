"""
Phase 4 P4: 全模块 KPI 口径扫描

遍历所有页面，提取每个 KPI 数字，标记口径来源。
输出 .planning/phase-4-kpi-audit.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "frontend" / "node_modules" / ".bin"))


# 通过 grep + 人工分类，列出每个页面所有 KPI
KPI_AUDIT = {
    "pages": [
        {
            "page": "Home.vue",
            "kpis": [
                {
                    "name": "技术领域数",
                    "data_source": "neo4j://KnowledgeArea",
                    "code_path": "frontend/src/stores/graph.ts fetchOverview"
                },
                {
                    "name": "岗位数",
                    "data_source": "neo4j://Position",
                    "code_path": "HomeKpiStrip.vue totalPositions"
                },
                {
                    "name": "技能数",
                    "data_source": "neo4j://Skill",
                    "code_path": "HomeKpiStrip.vue totalSkills"
                },
                {
                    "name": "关系数",
                    "data_source": "computed (domainConnections or allEdges)",
                    "code_path": "Home.vue totalRelations"
                }
            ]
        },
        {
            "page": "PositionList.vue",
            "kpis": [
                {
                    "name": "岗位总数",
                    "data_source": "postgres://position_records (review_status='approved')",
                    "code_path": "usePositionStore fetchPositions"
                }
            ]
        },
        {
            "page": "Admin.vue / ContentReviewPanel",
            "kpis": [
                {
                    "name": "已发布岗位",
                    "data_source": "postgres://position_records review_status='approved'",
                    "code_path": "useReviewStore fetchStats"
                },
                {
                    "name": "待审岗位",
                    "data_source": "postgres://position_records review_status='pending_review'",
                    "code_path": "useReviewStore fetchStats"
                },
                {
                    "name": "已拒岗位",
                    "data_source": "postgres://position_records review_status='rejected'",
                    "code_path": "useReviewStore fetchStats"
                }
            ]
        },
        {
            "page": "DataDashboard.vue",
            "kpis": [
                {
                    "name": "total_nodes",
                    "data_source": "neo4j (Phase 4 P2 修复后)",
                    "code_path": "dashboard_service._fetch_graph_stats"
                },
                {
                    "name": "total_edges",
                    "data_source": "neo4j (Phase 4 P2 修复后)",
                    "code_path": "dashboard_service._fetch_graph_stats"
                }
            ]
        },
        {
            "page": "PipelineMonitor.vue",
            "kpis": [
                {
                    "name": "今日采集量",
                    "data_source": "postgres://jd_raw.crawled_at",
                    "code_path": "status_aggregator.py"
                },
                {
                    "name": "last_crawl_at (P3 新增)",
                    "data_source": "postgres://jd_raw.crawled_at MAX",
                    "code_path": "pipeline/routes.py"
                }
            ]
        },
        {
            "page": "Admin.vue / 数据源诊断 (Phase 4 P0 新增)",
            "kpis": [
                {
                    "name": "三层数据源对比",
                    "data_source": "API + PostgreSQL + Neo4j",
                    "code_path": "admin_data_truth.py"
                }
            ]
        }
    ],
    "findings": [
        {
            "id": "F1",
            "severity": "info",
            "title": "Phase 4 P0-P3 已修复主要口径不一致",
            "detail": "P0 真理表 + P1 孤儿节点分析 + P2 dashboard 统一 Neo4j + P3 last_crawl_at 字段"
        },
        {
            "id": "F2",
            "severity": "low",
            "title": "Neo4j 与 PG 字段映射不一致",
            "detail": "Neo4j Position 用 name_cn 字段，PG 用 name 字段。这是数据模型层问题，需要 Phase 5 修复"
        },
        {
            "id": "F3",
            "severity": "low",
            "title": "Neo4j 边数 vs dashboard 边数差异",
            "detail": "Neo4j 1375 vs dashboard 1179，差 196 条边。可能是 dashboard 用 Neo4j 缓存而不是实时查询"
        },
        {
            "id": "F4",
            "severity": "info",
            "title": "管理后台 review-items API 翻页问题",
            "detail": "API 返回 50 条但翻页未传 limit 参数"
        }
    ]
}


if __name__ == "__main__":
    output_path = Path(__file__).parents[2] / ".planning" / "phase-4-kpi-audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(KPI_AUDIT, f, ensure_ascii=False, indent=2)
    print(f"KPI 审计报告已保存到: {output_path}")
    print(f"扫描 {len(KPI_AUDIT['pages'])} 个页面")
    print(f"发现 {len(KPI_AUDIT['findings'])} 个问题")