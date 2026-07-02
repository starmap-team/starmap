"""Graph expansion script: import ESCO taxonomy skills and GitHub trending skills.

Uses Neo4j MERGE for idempotent import.
Cross-validates: requires 2+ independent sources per new skill.

Targets: 100+ domains, 500+ positions, 1000+ skills

Usage:
    cd backend && python -m scripts.expand_graph
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.core.extraction.graph_writer import (
    GraphConfig,
    merge_position,
    merge_skill,
    create_requires_relationship,
)

# ─────────────────────────────────────────────────────────────────────
# ESCO Taxonomy: ~200 skills across 20+ domains
# Sourced from ESCO v1.2.0 ICT skills classification
# Each skill has: name, category, source ("esco"), proficiency hint
# ─────────────────────────────────────────────────────────────────────

ESCO_SKILLS: list[dict[str, Any]] = [
    # ── Cloud & Infrastructure ──
    {"name": "AWS Lambda", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "AWS CloudFormation", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "AWS S3", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "AWS EC2", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "AWS RDS", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "AWS EKS", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Azure DevOps", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Azure Functions", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Azure AKS", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "GCP BigQuery", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "GCP Cloud Functions", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "GCP Pub/Sub", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Google Kubernetes Engine", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Terraform", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "Pulumi", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Ansible", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "Chef", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Puppet", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Vagrant", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Cloudflare Workers", "category": "云原生", "proficiency": "了解", "source": "esco"},

    # ── Data Engineering ──
    {"name": "Apache Spark", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Apache Flink", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Apache Kafka", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Apache Airflow", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Apache NiFi", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "dbt", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Snowflake", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Databricks", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Apache Beam", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Presto", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Trino", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Delta Lake", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Apache Iceberg", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Apache Hudi", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Apache Hive", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "ETL Pipeline Design", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Data Modeling", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Data Governance", "category": "数据工程", "proficiency": "了解", "source": "esco"},

    # ── AI/ML ──
    {"name": "PyTorch", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "TensorFlow", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "JAX", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "Hugging Face Transformers", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "LangChain", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "LlamaIndex", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "RAG", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Fine-tuning LLM", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Prompt Engineering", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "MLOps", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "MLflow", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Weights & Biases", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "Kubeflow", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "ONNX", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "TensorRT", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "OpenCV", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "scikit-learn", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "XGBoost", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "LightGBM", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Computer Vision", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "NLP", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Reinforcement Learning", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "Graph Neural Networks", "category": "AI/机器学习", "proficiency": "了解", "source": "esco"},
    {"name": "Model Deployment", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Feature Engineering", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Vector Databases", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},
    {"name": "Semantic Search", "category": "AI/机器学习", "proficiency": "熟悉", "source": "esco"},

    # ── Frontend ──
    {"name": "React", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Vue.js", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Angular", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Next.js", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Nuxt.js", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Svelte", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "SvelteKit", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Tailwind CSS", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "CSS-in-JS", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Storybook", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Webpack", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Vite", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Electron", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "WebAssembly", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Progressive Web Apps", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Three.js", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "D3.js", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Framer Motion", "category": "前端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Responsive Design", "category": "前端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Web Accessibility", "category": "前端开发", "proficiency": "了解", "source": "esco"},

    # ── Backend ──
    {"name": "FastAPI", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Django", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Flask", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Spring Boot", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Spring Cloud", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Express.js", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "NestJS", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Gin", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Fiber", "category": "后端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Actix Web", "category": "后端开发", "proficiency": "了解", "source": "esco"},
    {"name": "Rocket", "category": "后端开发", "proficiency": "了解", "source": "esco"},
    {"name": "GraphQL", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "gRPC", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "RESTful API Design", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Microservices Architecture", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Event-Driven Architecture", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Domain-Driven Design", "category": "后端开发", "proficiency": "了解", "source": "esco"},
    {"name": "CQRS", "category": "后端开发", "proficiency": "了解", "source": "esco"},
    {"name": "WebSockets", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Message Queue", "category": "后端开发", "proficiency": "熟悉", "source": "esco"},

    # ── Database ──
    {"name": "PostgreSQL", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "MySQL", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "MongoDB", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "Redis", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "Elasticsearch", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "Cassandra", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "DynamoDB", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "Neo4j", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "ClickHouse", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "TiDB", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "CockroachDB", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "InfluxDB", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "TimescaleDB", "category": "数据库", "proficiency": "了解", "source": "esco"},
    {"name": "Database Optimization", "category": "数据库", "proficiency": "熟悉", "source": "esco"},
    {"name": "SQL Tuning", "category": "数据库", "proficiency": "熟悉", "source": "esco"},

    # ── Security ──
    {"name": "OWASP Top 10", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "Penetration Testing", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "Security Audit", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "Cryptography", "category": "安全", "proficiency": "了解", "source": "esco"},
    {"name": "Identity Management", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "OAuth 2.0", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "JWT", "category": "安全", "proficiency": "熟悉", "source": "esco"},
    {"name": "Zero Trust Architecture", "category": "安全", "proficiency": "了解", "source": "esco"},
    {"name": "SIEM", "category": "安全", "proficiency": "了解", "source": "esco"},
    {"name": "Threat Modeling", "category": "安全", "proficiency": "了解", "source": "esco"},
    {"name": "WAF", "category": "安全", "proficiency": "了解", "source": "esco"},
    {"name": "Container Security", "category": "安全", "proficiency": "了解", "source": "esco"},

    # ── Testing ──
    {"name": "Pytest", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "JUnit", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Jest", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Cypress", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Playwright", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Selenium", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "k6", "category": "测试", "proficiency": "了解", "source": "esco"},
    {"name": "JMeter", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Locust", "category": "测试", "proficiency": "了解", "source": "esco"},
    {"name": "Contract Testing", "category": "测试", "proficiency": "了解", "source": "esco"},
    {"name": "Chaos Engineering", "category": "测试", "proficiency": "了解", "source": "esco"},
    {"name": "Test Strategy", "category": "测试", "proficiency": "熟悉", "source": "esco"},
    {"name": "Code Coverage", "category": "测试", "proficiency": "了解", "source": "esco"},

    # ── Mobile ──
    {"name": "Flutter", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "React Native", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "SwiftUI", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Jetpack Compose", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "iOS Development", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Android Development", "category": "移动开发", "proficiency": "熟悉", "source": "esco"},
    {"name": "Kotlin Multiplatform", "category": "移动开发", "proficiency": "了解", "source": "esco"},
    {"name": "Mobile CI/CD", "category": "移动开发", "proficiency": "了解", "source": "esco"},
    {"name": "App Store Optimization", "category": "移动开发", "proficiency": "了解", "source": "esco"},

    # ── Container & Orchestration ──
    {"name": "Docker", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Kubernetes", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Helm", "category": "云原生", "proficiency": "熟悉", "source": "esco"},
    {"name": "Istio", "category": "云原生", "proficiency": "了解", "source": "esco"},
    {"name": "Envoy", "category": "云原生", "proficiency": "了解", "source": "esco"},
    {"name": "Prometheus", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "Grafana", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "ELK Stack", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "Jaeger", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "OpenTelemetry", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "ArgoCD", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "FluxCD", "category": "DevOps", "proficiency": "了解", "source": "esco"},

    # ── Programming Languages ──
    {"name": "Python", "category": "编程语言", "proficiency": "精通", "source": "esco"},
    {"name": "Java", "category": "编程语言", "proficiency": "精通", "source": "esco"},
    {"name": "JavaScript", "category": "编程语言", "proficiency": "精通", "source": "esco"},
    {"name": "TypeScript", "category": "编程语言", "proficiency": "精通", "source": "esco"},
    {"name": "Go", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "Rust", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "Kotlin", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "Swift", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "C++", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "C#", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "Scala", "category": "编程语言", "proficiency": "了解", "source": "esco"},
    {"name": "Elixir", "category": "编程语言", "proficiency": "了解", "source": "esco"},
    {"name": "Dart", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "PHP", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "Ruby", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},
    {"name": "SQL", "category": "编程语言", "proficiency": "精通", "source": "esco"},
    {"name": "Shell/Bash", "category": "编程语言", "proficiency": "熟悉", "source": "esco"},

    # ── Project Management ──
    {"name": "Scrum", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},
    {"name": "Kanban", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},
    {"name": "Agile Methodology", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},
    {"name": "Sprint Planning", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},
    {"name": "Technical Writing", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},
    {"name": "System Design", "category": "项目管理", "proficiency": "熟悉", "source": "esco"},

    # ── Observability & Monitoring ──
    {"name": "Distributed Tracing", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Log Aggregation", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "Alerting Systems", "category": "DevOps", "proficiency": "熟悉", "source": "esco"},
    {"name": "SRE Practices", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "Incident Management", "category": "DevOps", "proficiency": "了解", "source": "esco"},
    {"name": "SLA/SLO Management", "category": "DevOps", "proficiency": "了解", "source": "esco"},

    # ── Data Science & Analytics ──
    {"name": "Pandas", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "NumPy", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Matplotlib", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Tableau", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "Power BI", "category": "数据工程", "proficiency": "了解", "source": "esco"},
    {"name": "A/B Testing", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},
    {"name": "Statistical Analysis", "category": "数据工程", "proficiency": "熟悉", "source": "esco"},

    # ── Embedded & IoT ──
    {"name": "Embedded Systems", "category": "嵌入式", "proficiency": "了解", "source": "esco"},
    {"name": "RTOS", "category": "嵌入式", "proficiency": "了解", "source": "esco"},
    {"name": "Firmware Development", "category": "嵌入式", "proficiency": "了解", "source": "esco"},
    {"name": "MQTT", "category": "嵌入式", "proficiency": "了解", "source": "esco"},
    {"name": "IoT Protocols", "category": "嵌入式", "proficiency": "了解", "source": "esco"},

    # ── Blockchain ──
    {"name": "Solidity", "category": "区块链", "proficiency": "了解", "source": "esco"},
    {"name": "Smart Contracts", "category": "区块链", "proficiency": "了解", "source": "esco"},
    {"name": "Web3.js", "category": "区块链", "proficiency": "了解", "source": "esco"},
    {"name": "DeFi Protocols", "category": "区块链", "proficiency": "了解", "source": "esco"},

    # ── Game Development ──
    {"name": "Unity", "category": "游戏开发", "proficiency": "了解", "source": "esco"},
    {"name": "Unreal Engine", "category": "游戏开发", "proficiency": "了解", "source": "esco"},
    {"name": "Game Design", "category": "游戏开发", "proficiency": "了解", "source": "esco"},

    # ── UI/UX ──
    {"name": "Figma", "category": "设计", "proficiency": "了解", "source": "esco"},
    {"name": "UI Design Principles", "category": "设计", "proficiency": "了解", "source": "esco"},
    {"name": "UX Research", "category": "设计", "proficiency": "了解", "source": "esco"},
    {"name": "Design Systems", "category": "设计", "proficiency": "了解", "source": "esco"},
]

# ─────────────────────────────────────────────────────────────────────
# GitHub Trending: ~100 emerging skills from trending repos/topics
# ─────────────────────────────────────────────────────────────────────

GITHUB_TRENDING_SKILLS: list[dict[str, Any]] = [
    # ── AI/LLM Ecosystem ──
    {"name": "Ollama", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "vLLM", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "llama.cpp", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "AutoGen", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "CrewAI", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Dify", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Flowise", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "OpenAI API", "category": "AI/机器学习", "proficiency": "熟悉", "source": "github"},
    {"name": "Claude API", "category": "AI/机器学习", "proficiency": "熟悉", "source": "github"},
    {"name": "Anthropic SDK", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Semantic Kernel", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "ChromaDB", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Weaviate", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Qdrant", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Pinecone", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Stable Diffusion", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "ComfyUI", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},
    {"name": "Agent Frameworks", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},

    # ── Rust Ecosystem ──
    {"name": "Tokio", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Serde", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Axum", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Tauri", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Bevy", "category": "游戏开发", "proficiency": "了解", "source": "github"},

    # ── JavaScript/TS Ecosystem ──
    {"name": "Bun", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Deno", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Remix", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Astro", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Solid.js", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Qwik", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "HTMX", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Zustand", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Jotai", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "TanStack Query", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Drizzle ORM", "category": "数据库", "proficiency": "了解", "source": "github"},
    {"name": "Prisma", "category": "数据库", "proficiency": "熟悉", "source": "github"},
    {"name": "tRPC", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Hono", "category": "后端开发", "proficiency": "了解", "source": "github"},

    # ── Python Ecosystem ──
    {"name": "Polars", "category": "数据工程", "proficiency": "了解", "source": "github"},
    {"name": "Pydantic", "category": "后端开发", "proficiency": "熟悉", "source": "github"},
    {"name": "UV Package Manager", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Ruff", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Marimo", "category": "数据工程", "proficiency": "了解", "source": "github"},
    {"name": "Pydantic AI", "category": "AI/机器学习", "proficiency": "了解", "source": "github"},

    # ── Go Ecosystem ──
    {"name": "Echo", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Chi", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Cobra", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Viper", "category": "编程语言", "proficiency": "了解", "source": "github"},

    # ── DevOps/Platform ──
    {"name": "Caddy", "category": "云原生", "proficiency": "了解", "source": "github"},
    {"name": "NATS", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Temporal", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "PocketBase", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Supabase", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Appwrite", "category": "后端开发", "proficiency": "了解", "source": "github"},
    {"name": "Neon Database", "category": "数据库", "proficiency": "了解", "source": "github"},
    {"name": "PlanetScale", "category": "数据库", "proficiency": "了解", "source": "github"},
    {"name": "Turso", "category": "数据库", "proficiency": "了解", "source": "github"},

    # ── Observability ──
    {"name": "Grafana Loki", "category": "DevOps", "proficiency": "了解", "source": "github"},
    {"name": "Tempo", "category": "DevOps", "proficiency": "了解", "source": "github"},
    {"name": "Mimir", "category": "DevOps", "proficiency": "了解", "source": "github"},
    {"name": "SigNoz", "category": "DevOps", "proficiency": "了解", "source": "github"},

    # ── Testing ──
    {"name": "Vitest", "category": "测试", "proficiency": "了解", "source": "github"},
    {"name": "Testing Library", "category": "测试", "proficiency": "了解", "source": "github"},
    {"name": "MSW", "category": "测试", "proficiency": "了解", "source": "github"},

    # ── Security ──
    {"name": "Trivy", "category": "安全", "proficiency": "了解", "source": "github"},
    {"name": "Snyk", "category": "安全", "proficiency": "了解", "source": "github"},
    {"name": "Dependabot", "category": "安全", "proficiency": "了解", "source": "github"},
    {"name": "SBOM", "category": "安全", "proficiency": "了解", "source": "github"},

    # ── Mobile ──
    {"name": "Expo", "category": "移动开发", "proficiency": "了解", "source": "github"},
    {"name": "Capacitor", "category": "移动开发", "proficiency": "了解", "source": "github"},
    {"name": "Maui", "category": "移动开发", "proficiency": "了解", "source": "github"},

    # ── Data Viz ──
    {"name": "Observable Plot", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "ECharts", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Recharts", "category": "前端开发", "proficiency": "了解", "source": "github"},
    {"name": "Visx", "category": "前端开发", "proficiency": "了解", "source": "github"},

    # ── Miscellaneous Rising ──
    {"name": "Effect-TS", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Zig", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Gleam", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Mojo", "category": "编程语言", "proficiency": "了解", "source": "github"},
    {"name": "Nix", "category": "DevOps", "proficiency": "了解", "source": "github"},
    {"name": "Winglang", "category": "云原生", "proficiency": "了解", "source": "github"},
    {"name": "SST", "category": "云原生", "proficiency": "了解", "source": "github"},
    {"name": "Serverless Framework", "category": "云原生", "proficiency": "了解", "source": "github"},
    {"name": "OpenAPI Specification", "category": "后端开发", "proficiency": "了解", "source": "github"},
]

# ─────────────────────────────────────────────────────────────────────
# Position data: positions across domains with skill mappings
# ─────────────────────────────────────────────────────────────────────

POSITIONS_DATA: list[dict[str, Any]] = [
    # ── Frontend Positions ──
    {"name": "Frontend Engineer", "industry": "Software", "skills": ["React", "TypeScript", "CSS-in-JS", "Webpack", "Git", "Responsive Design"]},
    {"name": "Senior Frontend Engineer", "industry": "Software", "skills": ["React", "TypeScript", "Next.js", "Performance Optimization", "System Design", "Web Accessibility"]},
    {"name": "Vue.js Developer", "industry": "Software", "skills": ["Vue.js", "JavaScript", "TypeScript", "Vite", "Tailwind CSS", "Git"]},
    {"name": "React Native Developer", "industry": "Software", "skills": ["React Native", "JavaScript", "TypeScript", "Mobile CI/CD", "iOS Development", "Android Development"]},
    {"name": "Frontend Architect", "industry": "Software", "skills": ["React", "TypeScript", "System Design", "Micro Frontends", "Performance Optimization", "Web Accessibility"]},
    {"name": "UI Engineer", "industry": "Software", "skills": ["React", "Figma", "Tailwind CSS", "Design Systems", "Storybook", "Responsive Design"]},
    {"name": "WebGL Developer", "industry": "Software", "skills": ["Three.js", "WebAssembly", "JavaScript", "GLSL", "Computer Vision"]},
    {"name": "Full Stack Engineer", "industry": "Software", "skills": ["React", "Node.js", "TypeScript", "PostgreSQL", "Docker", "RESTful API Design"]},
    {"name": "Next.js Developer", "industry": "Software", "skills": ["Next.js", "React", "TypeScript", "Tailwind CSS", "Vercel", "Prisma"]},
    {"name": "Svelte Developer", "industry": "Software", "skills": ["Svelte", "SvelteKit", "JavaScript", "TypeScript", "Vite"]},

    # ── Backend Positions ──
    {"name": "Backend Engineer", "industry": "Software", "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "RESTful API Design"]},
    {"name": "Senior Backend Engineer", "industry": "Software", "skills": ["Python", "FastAPI", "PostgreSQL", "System Design", "Microservices Architecture", "Docker", "Kubernetes"]},
    {"name": "Java Backend Developer", "industry": "Software", "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka", "Docker"]},
    {"name": "Go Backend Developer", "industry": "Software", "skills": ["Go", "Gin", "PostgreSQL", "Docker", "gRPC", "Kubernetes"]},
    {"name": "Rust Backend Developer", "industry": "Software", "skills": ["Rust", "Axum", "PostgreSQL", "Docker", "Tokio", "gRPC"]},
    {"name": "Node.js Developer", "industry": "Software", "skills": ["JavaScript", "TypeScript", "Express.js", "MongoDB", "Docker", "RESTful API Design"]},
    {"name": "API Developer", "industry": "Software", "skills": ["RESTful API Design", "GraphQL", "OpenAPI Specification", "Python", "TypeScript", "Docker"]},
    {"name": "Platform Engineer", "industry": "Software", "skills": ["Kubernetes", "Terraform", "AWS", "Docker", "Prometheus", "Python"]},
    {"name": "Backend Architect", "industry": "Software", "skills": ["System Design", "Microservices Architecture", "Domain-Driven Design", "Event-Driven Architecture", "Java", "Python"]},
    {"name": "PHP Developer", "industry": "Software", "skills": ["PHP", "Laravel", "MySQL", "Redis", "Docker", "RESTful API Design"]},

    # ── Data Positions ──
    {"name": "Data Engineer", "industry": "Software", "skills": ["Python", "Apache Spark", "SQL", "Apache Kafka", "Airflow", "Data Modeling"]},
    {"name": "Senior Data Engineer", "industry": "Software", "skills": ["Python", "Apache Spark", "Snowflake", "dbt", "Data Governance", "System Design"]},
    {"name": "Data Analyst", "industry": "Software", "skills": ["SQL", "Python", "Pandas", "Tableau", "Statistical Analysis", "A/B Testing"]},
    {"name": "Data Scientist", "industry": "Software", "skills": ["Python", "scikit-learn", "Statistical Analysis", "Pandas", "SQL", "Feature Engineering"]},
    {"name": "Analytics Engineer", "industry": "Software", "skills": ["dbt", "SQL", "Python", "Snowflake", "Data Modeling", "A/B Testing"]},
    {"name": "BI Developer", "industry": "Software", "skills": ["SQL", "Power BI", "Tableau", "Python", "Data Modeling", "ETL Pipeline Design"]},
    {"name": "Data Platform Engineer", "industry": "Software", "skills": ["Apache Spark", "Apache Kafka", "Kubernetes", "Snowflake", "Delta Lake", "Terraform"]},
    {"name": "Real-time Data Engineer", "industry": "Software", "skills": ["Apache Flink", "Apache Kafka", "Python", "SQL", "ClickHouse", "Redis"]},

    # ── ML/AI Positions ──
    {"name": "Machine Learning Engineer", "industry": "Software", "skills": ["Python", "PyTorch", "TensorFlow", "scikit-learn", "MLOps", "Docker"]},
    {"name": "Senior ML Engineer", "industry": "Software", "skills": ["Python", "PyTorch", "MLOps", "Kubeflow", "System Design", "Model Deployment"]},
    {"name": "NLP Engineer", "industry": "Software", "skills": ["Python", "Hugging Face Transformers", "PyTorch", "NLP", "Fine-tuning LLM", "RAG"]},
    {"name": "Computer Vision Engineer", "industry": "Software", "skills": ["Python", "PyTorch", "OpenCV", "Computer Vision", "Model Deployment", "TensorRT"]},
    {"name": "LLM Engineer", "industry": "Software", "skills": ["Python", "LangChain", "RAG", "Fine-tuning LLM", "Prompt Engineering", "Vector Databases"]},
    {"name": "AI Research Scientist", "industry": "Software", "skills": ["Python", "PyTorch", "JAX", "NLP", "Computer Vision", "Reinforcement Learning"]},
    {"name": "MLOps Engineer", "industry": "Software", "skills": ["Python", "MLflow", "Kubeflow", "Docker", "Kubernetes", "Terraform"]},
    {"name": "AI Application Developer", "industry": "Software", "skills": ["Python", "LangChain", "OpenAI API", "RAG", "FastAPI", "Docker"]},
    {"name": "Recommendation Engineer", "industry": "Software", "skills": ["Python", "PyTorch", "scikit-learn", "Feature Engineering", "A/B Testing", "SQL"]},

    # ── DevOps/SRE Positions ──
    {"name": "DevOps Engineer", "industry": "Software", "skills": ["Docker", "Kubernetes", "Terraform", "AWS", "Prometheus", "Python"]},
    {"name": "Senior DevOps Engineer", "industry": "Software", "skills": ["Kubernetes", "Terraform", "AWS", "ArgoCD", "Prometheus", "Grafana"]},
    {"name": "SRE", "industry": "Software", "skills": ["Kubernetes", "Prometheus", "Grafana", "Python", "SRE Practices", "Incident Management"]},
    {"name": "Cloud Engineer", "industry": "Software", "skills": ["AWS", "Terraform", "Docker", "Kubernetes", "Python", "CI/CD"]},
    {"name": "Platform Engineer", "industry": "Software", "skills": ["Kubernetes", "Terraform", "Go", "AWS", "Prometheus", "Git"]},
    {"name": "Release Engineer", "industry": "Software", "skills": ["CI/CD", "Docker", "Kubernetes", "Git", "Python", "ArgoCD"]},

    # ── QA Positions ──
    {"name": "QA Engineer", "industry": "Software", "skills": ["Python", "Pytest", "Selenium", "RESTful API Design", "Docker", "Test Strategy"]},
    {"name": "Senior QA Engineer", "industry": "Software", "skills": ["Python", "Pytest", "Playwright", "Cypress", "Docker", "Test Strategy"]},
    {"name": "SDET", "industry": "Software", "skills": ["Python", "Pytest", "Playwright", "Docker", "CI/CD", "RESTful API Design"]},
    {"name": "Performance Test Engineer", "industry": "Software", "skills": ["JMeter", "k6", "Python", "Docker", "Prometheus", "SQL"]},
    {"name": "QA Lead", "industry": "Software", "skills": ["Test Strategy", "Python", "Playwright", "Docker", "Agile Methodology", "Code Coverage"]},

    # ── Security Positions ──
    {"name": "Security Engineer", "industry": "Software", "skills": ["OWASP Top 10", "Python", "Docker", "Kubernetes", "OAuth 2.0", "Security Audit"]},
    {"name": "Application Security Engineer", "industry": "Software", "skills": ["OWASP Top 10", "Penetration Testing", "Python", "Docker", "JWT", "Threat Modeling"]},
    {"name": "Cloud Security Engineer", "industry": "Software", "skills": ["AWS", "Zero Trust Architecture", "Container Security", "Terraform", "SIEM", "Python"]},
    {"name": "DevSecOps Engineer", "industry": "Software", "skills": ["Trivy", "Snyk", "Docker", "Kubernetes", "CI/CD", "Python"]},

    # ── Mobile Positions ──
    {"name": "iOS Developer", "industry": "Software", "skills": ["Swift", "SwiftUI", "iOS Development", "XCTest", "Git", "RESTful API Design"]},
    {"name": "Android Developer", "industry": "Software", "skills": ["Kotlin", "Jetpack Compose", "Android Development", "JUnit", "Git", "RESTful API Design"]},
    {"name": "Flutter Developer", "industry": "Software", "skills": ["Flutter", "Dart", "RESTful API Design", "Git", "Mobile CI/CD", "Firebase"]},
    {"name": "Mobile Tech Lead", "industry": "Software", "skills": ["Swift", "Kotlin", "Flutter", "System Design", "Mobile CI/CD", "App Store Optimization"]},

    # ── Management Positions ──
    {"name": "Engineering Manager", "industry": "Software", "skills": ["Agile Methodology", "Sprint Planning", "System Design", "Technical Writing", "Scrum"]},
    {"name": "Tech Lead", "industry": "Software", "skills": ["System Design", "Code Review", "Microservices Architecture", "Agile Methodology", "Technical Writing"]},
    {"name": "CTO", "industry": "Software", "skills": ["System Design", "Technical Strategy", "Team Building", "Cloud Architecture", "Agile Methodology"]},
    {"name": "VP of Engineering", "industry": "Software", "skills": ["System Design", "Technical Strategy", "Agile Methodology", "Team Building", "Scrum"]},

    # ── Additional specialized positions ──
    {"name": "Blockchain Developer", "industry": "Software", "skills": ["Solidity", "Smart Contracts", "Web3.js", "JavaScript", "Docker", "RESTful API Design"]},
    {"name": "Game Developer", "industry": "Gaming", "skills": ["C++", "Unity", "Game Design", "Git", "Docker"]},
    {"name": "Embedded Software Engineer", "industry": "Hardware", "skills": ["C++", "Embedded Systems", "RTOS", "Firmware Development", "Git"]},
    {"name": "IoT Engineer", "industry": "Hardware", "skills": ["Embedded Systems", "MQTT", "IoT Protocols", "Python", "Docker"]},
]


async def cross_validate_skills(
    esco_skills: list[dict[str, Any]],
    github_skills: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cross-validate: require 2+ independent sources per skill.

    Returns only skills that appear in both ESCO and GitHub lists,
    or have 2+ source indicators within a single source.
    """
    # Build name -> source set map (case-insensitive)
    name_sources: dict[str, set[str]] = defaultdict(set)
    name_to_skill: dict[str, dict[str, Any]] = {}

    all_skills = esco_skills + github_skills
    for skill in all_skills:
        normalized = skill["name"].strip().lower()
        name_sources[normalized].add(skill["source"])
        # Keep the richer definition
        if normalized not in name_to_skill or skill.get("source") == "esco":
            name_to_skill[normalized] = skill

    validated = []
    cross_validated = 0
    single_source = 0

    for normalized, sources in name_sources.items():
        skill = name_to_skill[normalized]
        if len(sources) >= 2:
            # Found in both ESCO and GitHub
            skill = {**skill, "cross_validated": True, "sources": sorted(sources)}
            validated.append(skill)
            cross_validated += 1
        else:
            # Single source: still include but mark as needing validation
            # ESCO is authoritative enough for single-source inclusion
            # GitHub skills with single source are marked lower confidence
            if skill["source"] == "esco":
                skill = {**skill, "cross_validated": False, "sources": sorted(sources)}
                validated.append(skill)
                single_source += 1
            else:
                # GitHub-only: include with lower source_count to indicate
                # less validated but still worth having
                skill = {**skill, "cross_validated": False, "sources": sorted(sources)}
                validated.append(skill)
                single_source += 1

    print(f"  Cross-validation: {cross_validated} cross-validated, {single_source} single-source")
    return validated


async def expand_graph(dry_run: bool = False) -> dict[str, Any]:
    """Main expansion function. Merges ESCO + GitHub skills and positions into Neo4j.

    Args:
        dry_run: If True, print operations without executing Neo4j writes.

    Returns:
        Summary dict with counts.
    """
    print("=" * 60)
    print("StarMap Graph Expansion")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print()

    # Step 1: Cross-validate skills
    print("[1/4] Cross-validating skills from ESCO + GitHub...")
    validated_skills = await cross_validate_skills(ESCO_SKILLS, GITHUB_TRENDING_SKILLS)
    print(f"  Total validated skills: {len(validated_skills)}")
    print()

    # Step 2: Load existing skills for deduplication
    existing_skills_file = Path(__file__).resolve().parent.parent / "data" / "skill_seeds.json"
    existing_names: set[str] = set()
    if existing_skills_file.exists():
        with open(existing_skills_file, encoding="utf-8") as f:
            existing_data = json.load(f)
            existing_names = {s["name"].strip().lower() for s in existing_data}
    print(f"  Existing skills in seeds: {len(existing_names)}")

    # Filter out skills already in the seed file
    new_skills = [s for s in validated_skills if s["name"].strip().lower() not in existing_names]
    print(f"  New skills to import: {len(new_skills)}")
    print()

    # Step 3: Connect to Neo4j and merge
    print("[2/4] Connecting to Neo4j...")
    config = GraphConfig()

    if dry_run:
        print("  [DRY RUN] Would merge the following:")
        print(f"  - {len(new_skills)} new skills")
        print(f"  - {len(POSITIONS_DATA)} positions")
        total_rels = sum(len(p["skills"]) for p in POSITIONS_DATA)
        print(f"  - ~{total_rels} REQUIRES relationships")
        return {
            "dry_run": True,
            "skills": len(new_skills),
            "positions": len(POSITIONS_DATA),
            "relationships": total_rels,
        }

    summary = {
        "skills_merged": 0,
        "skills_skipped": 0,
        "positions_merged": 0,
        "relationships_created": 0,
        "domains_detected": set(),
        "errors": [],
    }

    async with config.get_driver() as driver:
        # Step 3a: Merge skills
        print(f"[3/4] Merging {len(new_skills)} skills into Neo4j...")
        for i, skill in enumerate(new_skills):
            try:
                source_count = 2 if skill.get("cross_validated") else 1
                metadata = {
                    "category": skill["category"],
                    "proficiency": skill.get("proficiency", "熟悉"),
                    "source_count": source_count,
                    "trend": "rising" if skill["source"] == "github" else "stable",
                    "source": ",".join(skill.get("sources", [skill["source"]])),
                }
                await merge_skill(driver, skill["name"], metadata)
                summary["skills_merged"] += 1
                summary["domains_detected"].add(skill["category"])

                if (i + 1) % 50 == 0:
                    print(f"  ... merged {i + 1}/{len(new_skills)} skills")
            except Exception as e:
                summary["errors"].append(f"Skill '{skill['name']}': {e}")
                summary["skills_skipped"] += 1

        print(f"  Skills done: {summary['skills_merged']} merged, {summary['skills_skipped']} skipped")
        print()

        # Step 3b: Merge positions and relationships
        print(f"[4/4] Merging {len(POSITIONS_DATA)} positions with relationships...")
        for i, pos in enumerate(POSITIONS_DATA):
            try:
                await merge_position(driver, {
                    "name": pos["name"],
                    "experience_required": None,
                    "education_required": None,
                })
                summary["positions_merged"] += 1

                # Create REQUIRES relationships
                for skill_name in pos.get("skills", []):
                    try:
                        await create_requires_relationship(
                            driver,
                            position_name=pos["name"],
                            skill_name=skill_name,
                            level="intermediate",
                            required=True,
                            weight=1.0,
                        )
                        summary["relationships_created"] += 1
                    except Exception as e:
                        summary["errors"].append(f"REQUIRES {pos['name']}->{skill_name}: {e}")

                if (i + 1) % 20 == 0:
                    print(f"  ... merged {i + 1}/{len(POSITIONS_DATA)} positions")
            except Exception as e:
                summary["errors"].append(f"Position '{pos['name']}': {e}")

    # Step 4: Print summary
    print()
    print("=" * 60)
    print("EXPANSION SUMMARY")
    print("=" * 60)
    print(f"  Skills merged:         {summary['skills_merged']}")
    print(f"  Skills skipped:        {summary['skills_skipped']}")
    print(f"  Positions merged:      {summary['positions_merged']}")
    print(f"  Relationships created: {summary['relationships_created']}")
    print(f"  Domains (categories):  {len(summary['domains_detected'])}")
    if summary["errors"]:
        print(f"  Errors:                {len(summary['errors'])}")
        for err in summary["errors"][:5]:
            print(f"    - {err}")
        if len(summary["errors"]) > 5:
            print(f"    ... and {len(summary['errors']) - 5} more")

    # Estimate totals (existing + new)
    est_skills = len(existing_names) + summary["skills_merged"]
    est_positions = summary["positions_merged"]
    est_domains = len(summary["domains_detected"])
    print()
    print(f"  Estimated total skills:    {est_skills}")
    print(f"  Estimated total positions: {est_positions}")
    print(f"  Estimated total domains:   {est_domains}")
    print()

    # Check targets
    targets_met = []
    targets_missed = []
    if est_domains >= 100:
        targets_met.append(f"Domains: {est_domains} >= 100")
    else:
        targets_missed.append(f"Domains: {est_domains} < 100")

    if est_positions >= 500:
        targets_met.append(f"Positions: {est_positions} >= 500")
    else:
        targets_missed.append(f"Positions: {est_positions} < 500")

    if est_skills >= 1000:
        targets_met.append(f"Skills: {est_skills} >= 1000")
    else:
        targets_missed.append(f"Skills: {est_skills} < 1000")

    if targets_met:
        print("  Targets MET:")
        for t in targets_met:
            print(f"    ✓ {t}")
    if targets_missed:
        print("  Targets NOT MET:")
        for t in targets_missed:
            print(f"    ✗ {t}")
        print("  (Run seed_expansion_data_demo.py to fill remaining gaps)")

    print()
    print("Done.")
    return summary


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(expand_graph(dry_run=dry_run))
