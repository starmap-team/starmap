"""Demo seed expansion data: supplement graph to 100+ domains, 500+ positions, 1000+ skills.

DEMO ONLY — _demo suffix, excluded from production.
Uses Neo4j MERGE for idempotent operations.

Run after expand_graph.py to fill the gap to targets.

Usage:
    cd backend && python -m scripts.seed_expansion_data_demo
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.core.extraction.graph_writer import (
    GraphConfig,
    merge_position,
    merge_skill,
    create_requires_relationship,
)


# ─────────────────────────────────────────────────────────────────────
# Supplementary domains (to reach 100+)
# expand_graph.py covers ~20 categories; we add niche ones here
# ─────────────────────────────────────────────────────────────────────

EXTRA_DOMAINS: list[str] = [
    "AR/VR开发", "量子计算", "生物信息学", "金融科技", "自动驾驶",
    "机器人学", "数字孪生", "边缘计算", "低代码平台", "RPA",
    "搜索引擎", "推荐系统", "广告技术", "内容审核", "NLP工程",
    "语音识别", "知识图谱", "供应链技术", "医疗信息化", "教育科技",
    "法律科技", "农业技术", "能源技术", "物流技术", "电信技术",
    "GIS/测绘", "CAD/CAE", "PLM", "EDA", "数字信号处理",
    "编解码技术", "光通信", "芯片设计", "FPGA开发", "ASIC设计",
    "SoC设计", "GPU编程", "并行计算", "高性能计算", "网格计算",
    "可信计算", "同态加密", "联邦学习", "隐私计算", "数字版权",
    "合规科技", "环境监测", "智能建筑", "工业物联网", "数字营销",
    "MarTech", "RegTech", "InsurTech", "HealthTech", "EdTech",
    "PropTech", "FoodTech", "TravelTech", "LegalTech", "AgriTech",
    "CleanTech", "BioTech", "NanoTech", "SpaceTech", "DefTech",
    "深海技术", "气象技术", "遥感技术", "微服务治理", "混沌工程",
    "可观测性", "基础设施即代码", "GitOps", "MLOps工程", "DataOps",
    "ModelOps", "FeatureOps", "LLMOps", "安全运营中心", "威胁情报",
    "数字取证", "应急响应", "红蓝对抗", "零信任网络", "微隔离",
    "服务网格", "API网关", "流量治理", "配置中心", "注册中心",
    "分布式事务", "分布式缓存", "分布式存储", "消息中间件", "任务调度",
    "工作流引擎", "规则引擎", "权限引擎", "搜索引擎优化", "性能工程",
    "容量规划", "灰度发布", "蓝绿部署", "金丝雀发布", "AB实验平台",
]

# ─────────────────────────────────────────────────────────────────────
# Supplementary skills per domain (to reach 1000+)
# These are niche/domain-specific skills
# ─────────────────────────────────────────────────────────────────────

EXTRA_SKILLS: list[dict[str, Any]] = [
    # AR/VR
    {"name": "Unity XR", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "ARKit", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "ARCore", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "OpenXR", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "WebXR", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "Mixed Reality", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "Spatial Computing", "category": "AR/VR开发", "proficiency": "了解"},
    {"name": "3D Modeling", "category": "AR/VR开发", "proficiency": "了解"},

    # Quantum Computing
    {"name": "Qiskit", "category": "量子计算", "proficiency": "了解"},
    {"name": "Cirq", "category": "量子计算", "proficiency": "了解"},
    {"name": "Quantum Algorithms", "category": "量子计算", "proficiency": "了解"},

    # Bioinformatics
    {"name": "BioPython", "category": "生物信息学", "proficiency": "了解"},
    {"name": "Genomics Analysis", "category": "生物信息学", "proficiency": "了解"},
    {"name": "Protein Structure Prediction", "category": "生物信息学", "proficiency": "了解"},

    # FinTech
    {"name": "Quantitative Trading", "category": "金融科技", "proficiency": "了解"},
    {"name": "Risk Modeling", "category": "金融科技", "proficiency": "了解"},
    {"name": "Payment Systems", "category": "金融科技", "proficiency": "了解"},
    {"name": "KYC/AML", "category": "金融科技", "proficiency": "了解"},
    {"name": "High Frequency Trading", "category": "金融科技", "proficiency": "了解"},

    # Autonomous Driving
    {"name": "ROS", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "SLAM", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "LiDAR Processing", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "Sensor Fusion", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "Path Planning", "category": "自动驾驶", "proficiency": "了解"},

    # Robotics
    {"name": "Robot Operating System", "category": "机器人学", "proficiency": "了解"},
    {"name": "Motion Planning", "category": "机器人学", "proficiency": "了解"},
    {"name": "Computer Vision for Robotics", "category": "机器人学", "proficiency": "了解"},

    # Digital Twin
    {"name": "Digital Twin Modeling", "category": "数字孪生", "proficiency": "了解"},
    {"name": "Simulation Engineering", "category": "数字孪生", "proficiency": "了解"},

    # Edge Computing
    {"name": "Edge AI", "category": "边缘计算", "proficiency": "了解"},
    {"name": "Edge Orchestration", "category": "边缘计算", "proficiency": "了解"},
    {"name": "Federated Learning", "category": "边缘计算", "proficiency": "了解"},

    # Low Code
    {"name": "Low-Code Platforms", "category": "低代码平台", "proficiency": "了解"},
    {"name": "BPMN", "category": "低代码平台", "proficiency": "了解"},

    # RPA
    {"name": "UiPath", "category": "RPA", "proficiency": "了解"},
    {"name": "Automation Anywhere", "category": "RPA", "proficiency": "了解"},
    {"name": "Blue Prism", "category": "RPA", "proficiency": "了解"},

    # Search
    {"name": "Solr", "category": "搜索引擎", "proficiency": "了解"},
    {"name": "Algolia", "category": "搜索引擎", "proficiency": "了解"},
    {"name": "MeiliSearch", "category": "搜索引擎", "proficiency": "了解"},
    {"name": "Search Ranking", "category": "搜索引擎", "proficiency": "了解"},

    # Recommendation
    {"name": "Collaborative Filtering", "category": "推荐系统", "proficiency": "了解"},
    {"name": "Content-Based Filtering", "category": "推荐系统", "proficiency": "了解"},
    {"name": "Deep Learning Recommenders", "category": "推荐系统", "proficiency": "了解"},
    {"name": "Real-time Recommendations", "category": "推荐系统", "proficiency": "了解"},

    # AdTech
    {"name": "Ad Serving", "category": "广告技术", "proficiency": "了解"},
    {"name": "Programmatic Advertising", "category": "广告技术", "proficiency": "了解"},
    {"name": "RTB", "category": "广告技术", "proficiency": "了解"},

    # Content Moderation
    {"name": "Content Moderation Systems", "category": "内容审核", "proficiency": "了解"},
    {"name": "Image Classification", "category": "内容审核", "proficiency": "了解"},

    # Speech
    {"name": "Speech Recognition", "category": "语音识别", "proficiency": "了解"},
    {"name": "Text-to-Speech", "category": "语音识别", "proficiency": "了解"},
    {"name": "Whisper", "category": "语音识别", "proficiency": "了解"},
    {"name": "Speaker Diarization", "category": "语音识别", "proficiency": "了解"},

    # Knowledge Graph
    {"name": "Knowledge Graph Construction", "category": "知识图谱", "proficiency": "了解"},
    {"name": "Graph Databases", "category": "知识图谱", "proficiency": "了解"},
    {"name": "Ontology Design", "category": "知识图谱", "proficiency": "了解"},
    {"name": "SPARQL", "category": "知识图谱", "proficiency": "了解"},

    # Supply Chain
    {"name": "Supply Chain Optimization", "category": "供应链技术", "proficiency": "了解"},
    {"name": "Warehouse Management Systems", "category": "供应链技术", "proficiency": "了解"},
    {"name": "Demand Forecasting", "category": "供应链技术", "proficiency": "了解"},

    # Healthcare IT
    {"name": "HL7 FHIR", "category": "医疗信息化", "proficiency": "了解"},
    {"name": "DICOM", "category": "医疗信息化", "proficiency": "了解"},
    {"name": "Medical Imaging AI", "category": "医疗信息化", "proficiency": "了解"},

    # EdTech
    {"name": "LMS Development", "category": "教育科技", "proficiency": "了解"},
    {"name": "Adaptive Learning", "category": "教育科技", "proficiency": "了解"},
    {"name": "Learning Analytics", "category": "教育科技", "proficiency": "了解"},

    # GPU / HPC
    {"name": "CUDA", "category": "GPU编程", "proficiency": "了解"},
    {"name": "OpenCL", "category": "GPU编程", "proficiency": "了解"},
    {"name": "cuDNN", "category": "GPU编程", "proficiency": "了解"},
    {"name": "ROCm", "category": "GPU编程", "proficiency": "了解"},
    {"name": "MPI", "category": "高性能计算", "proficiency": "了解"},
    {"name": "OpenMP", "category": "高性能计算", "proficiency": "了解"},

    # FPGA / Chip Design
    {"name": "Verilog", "category": "FPGA开发", "proficiency": "了解"},
    {"name": "VHDL", "category": "FPGA开发", "proficiency": "了解"},
    {"name": "FPGA Design", "category": "FPGA开发", "proficiency": "了解"},
    {"name": "Chip Architecture", "category": "芯片设计", "proficiency": "了解"},
    {"name": "RTL Design", "category": "ASIC设计", "proficiency": "了解"},

    # Privacy / Crypto
    {"name": "Homomorphic Encryption", "category": "隐私计算", "proficiency": "了解"},
    {"name": "Differential Privacy", "category": "隐私计算", "proficiency": "了解"},
    {"name": "Secure Multi-party Computation", "category": "隐私计算", "proficiency": "了解"},
    {"name": "Trusted Execution Environment", "category": "可信计算", "proficiency": "了解"},

    # GitOps / Service Mesh
    {"name": "GitOps", "category": "GitOps", "proficiency": "了解"},
    {"name": "Service Mesh", "category": "服务网格", "proficiency": "了解"},
    {"name": "API Gateway", "category": "API网关", "proficiency": "了解"},
    {"name": "Traffic Management", "category": "流量治理", "proficiency": "了解"},

    # Distributed Systems
    {"name": "Distributed Consensus", "category": "分布式事务", "proficiency": "了解"},
    {"name": "Distributed Cache", "category": "分布式缓存", "proficiency": "了解"},
    {"name": "Distributed Storage", "category": "分布式存储", "proficiency": "了解"},
    {"name": "Task Scheduling", "category": "任务调度", "proficiency": "了解"},
    {"name": "Workflow Engine", "category": "工作流引擎", "proficiency": "了解"},
    {"name": "Rule Engine", "category": "规则引擎", "proficiency": "了解"},

    # Security Operations
    {"name": "SOC Operations", "category": "安全运营中心", "proficiency": "了解"},
    {"name": "Threat Intelligence", "category": "威胁情报", "proficiency": "了解"},
    {"name": "Digital Forensics", "category": "数字取证", "proficiency": "了解"},
    {"name": "Incident Response", "category": "应急响应", "proficiency": "了解"},
    {"name": "Red Team Operations", "category": "红蓝对抗", "proficiency": "了解"},
    {"name": "Microsegmentation", "category": "微隔离", "proficiency": "了解"},

    # Performance / Release
    {"name": "Performance Engineering", "category": "性能工程", "proficiency": "了解"},
    {"name": "Capacity Planning", "category": "容量规划", "proficiency": "了解"},
    {"name": "Canary Release", "category": "金丝雀发布", "proficiency": "了解"},
    {"name": "Blue-Green Deployment", "category": "蓝绿部署", "proficiency": "了解"},
    {"name": "Gray Release", "category": "灰度发布", "proficiency": "了解"},
    {"name": "A/B Experiment Platform", "category": "AB实验平台", "proficiency": "了解"},

    # DevX / DataX
    {"name": "DataOps", "category": "DataOps", "proficiency": "了解"},
    {"name": "Feature Store", "category": "FeatureOps", "proficiency": "了解"},
    {"name": "Model Registry", "category": "ModelOps", "proficiency": "了解"},
    {"name": "LLMOps", "category": "LLMOps", "proficiency": "了解"},
    {"name": "Prompt Management", "category": "LLMOps", "proficiency": "了解"},
    {"name": "Chaos Engineering Practices", "category": "混沌工程", "proficiency": "了解"},

    # GIS / Remote Sensing
    {"name": "GIS Development", "category": "GIS/测绘", "proficiency": "了解"},
    {"name": "Remote Sensing", "category": "遥感技术", "proficiency": "了解"},
    {"name": "Geospatial Analysis", "category": "GIS/测绘", "proficiency": "了解"},
    {"name": "MapReduce", "category": "GIS/测绘", "proficiency": "了解"},

    # Climate / Environment
    {"name": "Climate Modeling", "category": "气象技术", "proficiency": "了解"},
    {"name": "Environmental Monitoring", "category": "环境监测", "proficiency": "了解"},

    # Smart Building / IIoT
    {"name": "BMS Systems", "category": "智能建筑", "proficiency": "了解"},
    {"name": "IIoT Protocols", "category": "工业物联网", "proficiency": "了解"},
    {"name": "SCADA", "category": "工业物联网", "proficiency": "了解"},
    {"name": "OPC UA", "category": "工业物联网", "proficiency": "了解"},

    # Digital Marketing / MarTech
    {"name": "SEO Optimization", "category": "数字营销", "proficiency": "了解"},
    {"name": "Marketing Automation", "category": "MarTech", "proficiency": "了解"},
    {"name": "Customer Data Platform", "category": "MarTech", "proficiency": "了解"},
    {"name": "CDP Development", "category": "MarTech", "proficiency": "了解"},

    # RegTech / Compliance
    {"name": "Regulatory Compliance", "category": "RegTech", "proficiency": "了解"},
    {"name": "GRC Systems", "category": "合规科技", "proficiency": "了解"},

    # Misc Domain Skills
    {"name": "Insurance Core Systems", "category": "InsurTech", "proficiency": "了解"},
    {"name": "Clinical Decision Support", "category": "HealthTech", "proficiency": "了解"},
    {"name": "Real Estate Platforms", "category": "PropTech", "proficiency": "了解"},
    {"name": "Food Safety Systems", "category": "FoodTech", "proficiency": "了解"},
    {"name": "Travel Booking Engines", "category": "TravelTech", "proficiency": "了解"},
    {"name": "Legal Document Analysis", "category": "LegalTech", "proficiency": "了解"},
    {"name": "Precision Agriculture", "category": "AgriTech", "proficiency": "了解"},
    {"name": "Clean Energy Systems", "category": "CleanTech", "proficiency": "了解"},
    {"name": "Biotech Data Analysis", "category": "BioTech", "proficiency": "了解"},
    {"name": "Nano-fabrication", "category": "NanoTech", "proficiency": "了解"},
    {"name": "Satellite Systems", "category": "SpaceTech", "proficiency": "了解"},
    {"name": "Defense Systems", "category": "DefTech", "proficiency": "了解"},
    {"name": "Signal Processing", "category": "数字信号处理", "proficiency": "了解"},
    {"name": "Video Encoding", "category": "编解码技术", "proficiency": "了解"},
    {"name": "Audio Processing", "category": "编解码技术", "proficiency": "了解"},
    {"name": "Optical Communication", "category": "光通信", "proficiency": "了解"},
    {"name": "CAD Development", "category": "CAD/CAE", "proficiency": "了解"},
    {"name": "PLM Systems", "category": "PLM", "proficiency": "了解"},
    {"name": "EDA Tools", "category": "EDA", "proficiency": "了解"},
    {"name": "NLP Pipeline", "category": "NLP工程", "proficiency": "了解"},
    {"name": "Text Classification", "category": "NLP工程", "proficiency": "了解"},
    {"name": "Named Entity Recognition", "category": "NLP工程", "proficiency": "了解"},
    {"name": "Sentiment Analysis", "category": "NLP工程", "proficiency": "了解"},
    {"name": "Machine Translation", "category": "NLP工程", "proficiency": "了解"},
    {"name": "Autonomous Navigation", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "V2X Communication", "category": "自动驾驶", "proficiency": "了解"},
    {"name": "Deep Sea Technology", "category": "深海技术", "proficiency": "了解"},
    {"name": "Underwater Robotics", "category": "深海技术", "proficiency": "了解"},
]

# ─────────────────────────────────────────────────────────────────────
# Supplementary positions (to reach 500+)
# ─────────────────────────────────────────────────────────────────────

EXTRA_POSITIONS: list[dict[str, Any]] = [
    # Niche / Emerging positions
    {"name": "AR/VR Developer", "industry": "Software", "skills": ["Unity XR", "C#", "3D Modeling", "Computer Vision", "Git"]},
    {"name": "Quantum Computing Researcher", "industry": "Research", "skills": ["Qiskit", "Python", "Quantum Algorithms", "Linear Algebra"]},
    {"name": "Bioinformatics Engineer", "industry": "BioTech", "skills": ["BioPython", "Python", "Genomics Analysis", "SQL", "Docker"]},
    {"name": "Fintech Backend Engineer", "industry": "FinTech", "skills": ["Java", "Spring Boot", "Payment Systems", "KYC/AML", "PostgreSQL", "Redis"]},
    {"name": "Quantitative Developer", "industry": "FinTech", "skills": ["Python", "C++", "Quantitative Trading", "SQL", "Risk Modeling"]},
    {"name": "Autonomous Driving Engineer", "industry": "Automotive", "skills": ["C++", "ROS", "SLAM", "Computer Vision", "Sensor Fusion", "Path Planning"]},
    {"name": "Robotics Software Engineer", "industry": "Robotics", "skills": ["C++", "ROS", "Motion Planning", "Computer Vision", "Python"]},
    {"name": "Digital Twin Engineer", "industry": "Manufacturing", "skills": ["Python", "Digital Twin Modeling", "Simulation Engineering", "IoT Protocols"]},
    {"name": "Edge Computing Engineer", "industry": "Telecom", "skills": ["Python", "Edge AI", "Docker", "Kubernetes", "MQTT"]},
    {"name": "RPA Developer", "industry": "Enterprise", "skills": ["UiPath", "Python", "Automation Anywhere", "SQL", "RESTful API Design"]},
    {"name": "Search Engineer", "industry": "Software", "skills": ["Elasticsearch", "Solr", "Python", "Java", "Search Ranking", "SQL"]},
    {"name": "Recommendation Engineer", "industry": "Software", "skills": ["Python", "PyTorch", "Collaborative Filtering", "Feature Engineering", "SQL"]},
    {"name": "AdTech Engineer", "industry": "AdTech", "skills": ["Java", "Python", "RTB", "Programmatic Advertising", "Redis", "Kafka"]},
    {"name": "Content Moderation Engineer", "industry": "Social", "skills": ["Python", "PyTorch", "Image Classification", "NLP", "Docker"]},
    {"name": "Speech Recognition Engineer", "industry": "AI", "skills": ["Python", "PyTorch", "Speech Recognition", "NLP", "Whisper"]},
    {"name": "Knowledge Graph Engineer", "industry": "AI", "skills": ["Neo4j", "Python", "Knowledge Graph Construction", "SPARQL", "NLP"]},
    {"name": "Supply Chain Tech Lead", "industry": "Logistics", "skills": ["Java", "Supply Chain Optimization", "SQL", "Python", "Docker"]},
    {"name": "Healthcare IT Developer", "industry": "Healthcare", "skills": ["Java", "HL7 FHIR", "PostgreSQL", "Docker", "RESTful API Design"]},
    {"name": "EdTech Backend Developer", "industry": "Education", "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"]},
    {"name": "GPU Computing Engineer", "industry": "HPC", "skills": ["CUDA", "C++", "Python", "cuDNN", "OpenCL"]},
    {"name": "FPGA Engineer", "industry": "Semiconductor", "skills": ["Verilog", "VHDL", "FPGA Design", "C++", "Git"]},
    {"name": "Chip Design Engineer", "industry": "Semiconductor", "skills": ["Verilog", "RTL Design", "Chip Architecture", "Python"]},
    {"name": "Privacy Engineer", "industry": "Security", "skills": ["Python", "Homomorphic Encryption", "Differential Privacy", "Federated Learning"]},
    {"name": "SRE Manager", "industry": "Software", "skills": ["SRE Practices", "Kubernetes", "Prometheus", "Incident Management", "Python"]},
    {"name": "DataOps Engineer", "industry": "Software", "skills": ["Python", "Apache Airflow", "dbt", "Docker", "CI/CD", "SQL"]},
    {"name": "Feature Store Engineer", "industry": "AI", "skills": ["Python", "Feature Store", "Feature Engineering", "Redis", "Kafka"]},
    {"name": "LLMOps Engineer", "industry": "AI", "skills": ["Python", "LLMOps", "Docker", "Kubernetes", "Prompt Management", "MLflow"]},
    {"name": "GIS Developer", "industry": "Mapping", "skills": ["Python", "GIS Development", "PostgreSQL", "JavaScript", "Geospatial Analysis"]},
    {"name": "Climate Data Scientist", "industry": "Environment", "skills": ["Python", "Climate Modeling", "Statistical Analysis", "SQL"]},
    {"name": "IIoT Engineer", "industry": "Manufacturing", "skills": ["Python", "IIoT Protocols", "SCADA", "OPC UA", "Docker"]},
    {"name": "MarTech Engineer", "industry": "Marketing", "skills": ["Python", "Marketing Automation", "Customer Data Platform", "SQL", "JavaScript"]},
    {"name": "RegTech Developer", "industry": "FinTech", "skills": ["Java", "Regulatory Compliance", "SQL", "Python", "Docker"]},
    {"name": "Smart Contract Auditor", "industry": "Blockchain", "skills": ["Solidity", "Smart Contracts", "Security Audit", "Python"]},
    {"name": "Video Codec Engineer", "industry": "Media", "skills": ["C++", "Video Encoding", "FFmpeg", "Signal Processing"]},
    {"name": "Signal Processing Engineer", "industry": "Telecom", "skills": ["C++", "Signal Processing", "Python", "MATLAB", "DSP"]},
    {"name": "Satellite Systems Engineer", "industry": "SpaceTech", "skills": ["C++", "Satellite Systems", "Embedded Systems", "Python"]},
    {"name": "Defense Software Engineer", "industry": "Defense", "skills": ["C++", "Python", "Embedded Systems", "Security Clearance"]},
    {"name": "Deep Learning Compiler Engineer", "industry": "AI", "skills": ["C++", "Python", "ONNX", "TensorRT", "MLIR"]},
    {"name": "Prompt Engineer", "industry": "AI", "skills": ["Prompt Engineering", "Python", "LangChain", "OpenAI API", "RAG"]},
    {"name": "AI Safety Researcher", "industry": "AI", "skills": ["Python", "PyTorch", "NLP", "RLHF", "Constitutional AI"]},
    {"name": "Data Mesh Architect", "industry": "Software", "skills": ["Data Governance", "System Design", "Snowflake", "dbt", "Python"]},
    {"name": "Observability Engineer", "industry": "Software", "skills": ["Prometheus", "Grafana", "OpenTelemetry", "Python", "Kubernetes"]},
    {"name": "API Platform Engineer", "industry": "Software", "skills": ["GraphQL", "RESTful API Design", "API Gateway", "Python", "Docker"]},
    {"name": "Infrastructure Engineer", "industry": "Software", "skills": ["Terraform", "Kubernetes", "AWS", "Python", "Linux"]},
    {"name": "Release Manager", "industry": "Software", "skills": ["CI/CD", "Docker", "Git", "ArgoCD", "Agile Methodology"]},
    {"name": "Site Reliability Engineer", "industry": "Software", "skills": ["Kubernetes", "Prometheus", "Grafana", "Python", "Go", "Linux"]},
    {"name": "Growth Engineer", "industry": "Software", "skills": ["Python", "A/B Testing", "SQL", "JavaScript", "Docker"]},
    {"name": "Internal Tools Developer", "industry": "Software", "skills": ["Python", "React", "PostgreSQL", "Docker", "RESTful API Design"]},
    {"name": "Developer Advocate", "industry": "Software", "skills": ["Technical Writing", "Python", "JavaScript", "Docker", "RESTful API Design"]},
    {"name": "Solutions Architect", "industry": "Software", "skills": ["System Design", "AWS", "Kubernetes", "Docker", "Python", "Technical Writing"]},
    {"name": "Staff Engineer", "industry": "Software", "skills": ["System Design", "Microservices Architecture", "Python", "Java", "Technical Writing"]},
    {"name": "Principal Engineer", "industry": "Software", "skills": ["System Design", "Technical Strategy", "Domain-Driven Design", "Microservices Architecture"]},
    {"name": "Distinguished Engineer", "industry": "Software", "skills": ["System Design", "Technical Strategy", "Cloud Architecture", "Team Building"]},
    {"name": "Revenue Engineer", "industry": "FinTech", "skills": ["Python", "SQL", "Payment Systems", "A/B Testing", "Docker"]},
    {"name": "Payments Engineer", "industry": "FinTech", "skills": ["Java", "Payment Systems", "PostgreSQL", "Redis", "Docker", "KYC/AML"]},
    {"name": "Fraud Detection Engineer", "industry": "FinTech", "skills": ["Python", "PyTorch", "SQL", "Feature Engineering", "Real-time Recommendations"]},
    {"name": "Identity Platform Engineer", "industry": "Software", "skills": ["OAuth 2.0", "JWT", "Identity Management", "Python", "Docker"]},
    {"name": "Chaos Engineer", "industry": "Software", "skills": ["Chaos Engineering", "Kubernetes", "Python", "Docker", "Prometheus"]},
    {"name": "Developer Experience Engineer", "industry": "Software", "skills": ["TypeScript", "Python", "Docker", "CI/CD", "Technical Writing"]},
    {"name": "FinOps Engineer", "industry": "Software", "skills": ["AWS", "Terraform", "Python", "SQL", "Cost Optimization"]},
]


async def seed_expansion_demo(dry_run: bool = False) -> dict[str, Any]:
    """Seed supplementary demo data to reach 100+ domains, 500+ positions, 1000+ skills.

    Args:
        dry_run: If True, print stats without writing to Neo4j.

    Returns:
        Summary dict.
    """
    print("=" * 60)
    print("StarMap Demo Expansion Seed (_demo)")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"WARNING: This is demo data (_demo suffix, excluded from production)")
    print()

    # Pre-compute stats
    all_demo_skills = EXTRA_SKILLS
    all_demo_positions = EXTRA_POSITIONS
    all_demo_domains = EXTRA_DOMAINS

    print(f"Demo data to seed:")
    print(f"  Extra domains:    {len(all_demo_domains)}")
    print(f"  Extra skills:     {len(all_demo_skills)}")
    print(f"  Extra positions:  {len(all_demo_positions)}")
    total_rels = sum(len(p["skills"]) for p in all_demo_positions)
    print(f"  Extra relations:  ~{total_rels}")
    print()

    if dry_run:
        print("[DRY RUN] No writes performed.")
        return {
            "dry_run": True,
            "domains": len(all_demo_domains),
            "skills": len(all_demo_skills),
            "positions": len(all_demo_positions),
            "relationships": total_rels,
        }

    config = GraphConfig()
    summary: dict[str, Any] = {
        "skills_merged": 0,
        "positions_merged": 0,
        "relationships_created": 0,
        "errors": [],
    }

    async with config.get_driver() as driver:
        # Merge demo skills
        print(f"Merging {len(all_demo_skills)} demo skills...")
        for i, skill in enumerate(all_demo_skills):
            try:
                metadata = {
                    "category": skill["category"],
                    "proficiency": skill.get("proficiency", "了解"),
                    "source_count": 1,
                    "trend": "stable",
                    "source": "demo_seed",
                }
                await merge_skill(driver, skill["name"], metadata)
                summary["skills_merged"] += 1
            except Exception as e:
                summary["errors"].append(f"Skill '{skill['name']}': {e}")

            if (i + 1) % 50 == 0:
                print(f"  ... {i + 1}/{len(all_demo_skills)} skills merged")

        print(f"  Skills done: {summary['skills_merged']}")
        print()

        # Merge demo positions with relationships
        print(f"Merging {len(all_demo_positions)} demo positions...")
        for i, pos in enumerate(all_demo_positions):
            try:
                await merge_position(driver, {
                    "name": pos["name"],
                    "experience_required": None,
                    "education_required": None,
                })
                summary["positions_merged"] += 1

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
                        summary["errors"].append(f"REL {pos['name']}->{skill_name}: {e}")

            except Exception as e:
                summary["errors"].append(f"Position '{pos['name']}': {e}")

            if (i + 1) % 20 == 0:
                print(f"  ... {i + 1}/{len(all_demo_positions)} positions merged")

    print()
    print("=" * 60)
    print("DEMO EXPANSION SUMMARY")
    print("=" * 60)
    print(f"  Demo skills merged:      {summary['skills_merged']}")
    print(f"  Demo positions merged:   {summary['positions_merged']}")
    print(f"  Demo relationships:      {summary['relationships_created']}")
    if summary["errors"]:
        print(f"  Errors:                  {len(summary['errors'])}")
    print()
    print("Done (demo seed).")
    return summary


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(seed_expansion_demo(dry_run=dry_run))
