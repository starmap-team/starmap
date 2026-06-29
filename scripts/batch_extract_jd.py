"""Batch JD extraction script for R1 (罗智峰) - Day 1 task.

This script simulates starting the 881 JD batch extraction using Celery tasks.
It reads sample JD data and processes them through the extraction pipeline.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.tasks.stage3_services import run_batch_extract_jd


# Sample JD data for batch extraction
SAMPLE_JDS = [
    {
        "title": "大模型应用工程师",
        "jd": "岗位：大模型应用工程师\n要求：精通Python、LangChain、RAG、Prompt Engineering、Fine-tuning、LLM；熟悉LlamaIndex、ChromaDB、OpenAI API、PyTorch；3年经验；硕士",
    },
    {
        "title": "高级后端工程师",
        "jd": "岗位：高级后端工程师\n要求：精通Python、FastAPI、PostgreSQL、Docker、Kubernetes；熟悉Redis、Celery；5年经验；本科",
    },
    {
        "title": "前端开发工程师",
        "jd": "岗位：前端开发工程师\n要求：精通JavaScript、TypeScript、Vue.js、HTML5、CSS3；熟悉React、Vite；3年经验；本科",
    },
    {
        "title": "数据工程师",
        "jd": "岗位：数据工程师\n要求：精通Python、SQL、Spark、Kafka；熟悉Flink、Airflow；3年经验；本科",
    },
    {
        "title": "DevOps工程师",
        "jd": "岗位：DevOps工程师\n要求：精通Docker、Kubernetes、Terraform、CI/CD、Prometheus；熟悉Ansible、Grafana；3年经验；本科",
    },
]


def run_batch_extraction_simulation():
    """Simulate batch extraction for R1's Day 1 task."""
    print("=== R1 (罗智峰) - Day 1 Task: 881 JD Batch Extraction ===")
    print(f"Processing {len(SAMPLE_JDS)} sample JDs...")
    
    results = []
    for i, jd_data in enumerate(SAMPLE_JDS, 1):
        print(f"\n--- Processing JD {i}/{len(SAMPLE_JDS)}: {jd_data['title']} ---")
        try:
            # Use the async function directly for simulation
            result = asyncio.run(run_batch_extract_jd(jd_data["jd"]))
            results.append(result)
            print(f"Status: {result.get('status', 'unknown')}")
            if result.get("position_name"):
                print(f"Position: {result['position_name']}")
            if result.get("required_skill_count"):
                print(f"Required skills: {result['required_skill_count']}")
            if result.get("preferred_skill_count"):
                print(f"Preferred skills: {result['preferred_skill_count']}")
            if result.get("graph"):
                print(f"Graph summary: {result['graph']}")
        except Exception as e:
            print(f"Error processing JD: {e}")
            results.append({"status": "error", "error": str(e)})
    
    # Summary
    print("\n=== Batch Extraction Summary ===")
    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "error")
    print(f"Total JDs processed: {len(results)}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {completed/len(results)*100:.1f}%")
    
    return results


if __name__ == "__main__":
    results = run_batch_extraction_simulation()
