# -*- coding: utf-8 -*-
"""
StarMap 质量仪表盘生成器

每天由 R7 姜文彬 运行，生成准确率报告并通报。
也用于每日集成时验证"演示就绪"。

用法：
  python scripts/quality_report.py --golden data/golden/ --output reports/
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def compute_f1(precision, recall):
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _load_jsonl(filepath):
    """Load a JSONL file, return list of dicts. Returns empty list if file missing."""
    path = Path(filepath)
    if not path.exists():
        return []
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def _normalize_name(name):
    """Normalize a skill/field name for comparison."""
    import re
    return re.sub(r"[^a-z0-9+#.]", "", str(name).strip().lower())


def _compute_f1(golden_set, system_set):
    """Compute precision, recall, and F1 between two sets."""
    if not golden_set and not system_set:
        return 1.0, 1.0, 1.0
    if not golden_set or not system_set:
        return 0.0, 0.0, 0.0
    tp = len(golden_set & system_set)
    precision = tp / len(system_set)
    recall = tp / len(golden_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _extract_skill_names(skills):
    """Extract name strings from a list of skill entries (str or dict)."""
    names = []
    for s in skills:
        if isinstance(s, dict):
            name = str(s.get("name", ""))
        else:
            name = str(s)
        if name.strip():
            names.append(_normalize_name(name))
    return set(names)


def evaluate_jd_extraction(golden_file, system_file):
    """评估 JD 解析准确率（按字段加权）。

    字段权重: position_name 0.10 / required_skills 0.30 / preferred_skills 0.15
             experience_required 0.10 / education_required 0.10 / industry 0.05
             responsibilities 0.10 / description 0.05 / knowledge_areas 0.05
    """
    golden_data = _load_jsonl(golden_file)
    system_data = _load_jsonl(system_file)
    system_map = {s.get("id", s.get("position_name", "")): s for s in system_data}

    if not golden_data:
        return {
            "metric": "JD解析准确率",
            "target": ">=90%",
            "current": 0.0,
            "status": "fail",
            "detail": "Golden set not found or empty",
        }

    WEIGHTS = {
        "position_name": 0.10,
        "required_skills": 0.30,
        "preferred_skills": 0.15,
        "experience_required": 0.10,
        "education_required": 0.10,
        "industry": 0.05,
        "responsibilities": 0.10,
        "description": 0.05,
        "knowledge_areas": 0.05,
    }

    total_weighted_score = 0.0
    total_weight = 0.0
    sample_count = 0

    for golden in golden_data:
        sid = golden.get("id", golden.get("position_name", ""))
        system = system_map.get(sid, {})
        sample_count += 1

        # Position name: exact match (normalized)
        gn = _normalize_name(golden.get("position_name", ""))
        sn = _normalize_name(system.get("position_name", ""))
        pos_score = 1.0 if gn == sn else (0.5 if gn in sn or sn in gn else 0.0)
        total_weighted_score += pos_score * WEIGHTS["position_name"]

        # Required skills: F1 on skill names
        g_req_set = _extract_skill_names(golden.get("required_skills", []))
        s_req_set = _extract_skill_names(system.get("required_skills", []))
        _, _, f1_req = _compute_f1(g_req_set, s_req_set)
        total_weighted_score += f1_req * WEIGHTS["required_skills"]

        # Preferred skills: F1
        g_pref_set = _extract_skill_names(golden.get("preferred_skills", []))
        s_pref_set = _extract_skill_names(system.get("preferred_skills", []))
        _, _, f1_pref = _compute_f1(g_pref_set, s_pref_set)
        total_weighted_score += f1_pref * WEIGHTS["preferred_skills"]

        # Experience: within ±1 year
        g_exp = golden.get("experience_required")
        s_exp = system.get("experience_required")
        if g_exp is not None and s_exp is not None:
            exp_score = 1.0 if abs(float(g_exp) - float(s_exp)) <= 1 else 0.0
        elif g_exp is None and s_exp is None:
            exp_score = 1.0
        else:
            exp_score = 0.5
        total_weighted_score += exp_score * WEIGHTS["experience_required"]

        # Education
        g_edu = _normalize_name(golden.get("education_required", ""))
        s_edu = _normalize_name(system.get("education_required", ""))
        edu_score = 1.0 if g_edu == s_edu else (0.5 if g_edu in s_edu or s_edu in g_edu else 0.0)
        total_weighted_score += edu_score * WEIGHTS["education_required"]

        # Industry
        g_ind = _normalize_name(golden.get("industry", ""))
        s_ind = _normalize_name(system.get("industry", ""))
        ind_score = 1.0 if g_ind == s_ind else 0.0
        total_weighted_score += ind_score * WEIGHTS["industry"]

        # Responsibilities: F1 on description overlap
        g_resp = set(_normalize_name(r) for r in golden.get("responsibilities", []) if r)
        s_resp = set(_normalize_name(r) for r in system.get("responsibilities", []) if r)
        _, _, f1_resp = _compute_f1(g_resp, s_resp)
        total_weighted_score += f1_resp * WEIGHTS["responsibilities"]

        # Description
        g_desc = _normalize_name(golden.get("description", ""))
        s_desc = _normalize_name(system.get("description", ""))
        desc_score = 1.0 if g_desc == s_desc else (0.5 if g_desc in s_desc or s_desc in g_desc else 0.0)
        total_weighted_score += desc_score * WEIGHTS["description"]

        # Knowledge areas
        g_ka = set(_normalize_name(k) for k in golden.get("knowledge_areas", []) if k)
        s_ka = set(_normalize_name(k) for k in system.get("knowledge_areas", []) if k)
        _, _, f1_ka = _compute_f1(g_ka, s_ka)
        total_weighted_score += f1_ka * WEIGHTS["knowledge_areas"]

        total_weight += sum(WEIGHTS.values())

    avg_score = round(total_weighted_score / total_weight, 4) if total_weight > 0 else 0.0
    passed = avg_score >= 0.90

    return {
        "metric": "JD解析准确率",
        "target": ">=90%",
        "current": f"{avg_score:.2%}",
        "status": "pass" if passed else "fail",
        "detail": f"基于 {sample_count} 个样本加权评估，综合得分 {avg_score:.2%}",
    }


def evaluate_resume_extraction(golden_file, system_file):
    """评估简历提取准确率（技能集 F1）。

    对比 golden 和 system 的 required_skills + preferred_skills 的 F1 值。
    """
    golden_data = _load_jsonl(golden_file)
    system_data = _load_jsonl(system_file)
    system_map = {s.get("id", s.get("candidate_name", "")): s for s in system_data}

    if not golden_data:
        return {
            "metric": "简历提取准确率",
            "target": ">=90%",
            "current": 0.0,
            "status": "fail",
            "detail": "Golden set not found or empty",
        }

    all_f1_scores = []
    sample_count = 0

    for golden in golden_data:
        sid = golden.get("id", golden.get("candidate_name", ""))
        system = system_map.get(sid, {})
        sample_count += 1

        # Combine required + preferred skills (or just "skills" field)
        if "skills" in golden:
            g_skills = golden.get("skills", [])
        else:
            g_skills = golden.get("required_skills", []) + golden.get("preferred_skills", [])

        if "skills" in system:
            s_skills = system.get("skills", [])
        else:
            s_skills = system.get("required_skills", []) + system.get("preferred_skills", [])

        g_set = _extract_skill_names(g_skills)
        s_set = _extract_skill_names(s_skills)
        _, _, f1 = _compute_f1(g_set, s_set)
        all_f1_scores.append(f1)

    avg_f1 = round(sum(all_f1_scores) / len(all_f1_scores), 4) if all_f1_scores else 0.0
    passed = avg_f1 >= 0.90

    return {
        "metric": "简历提取准确率",
        "target": ">=90%",
        "current": f"{avg_f1:.2%}",
        "status": "pass" if passed else "fail",
        "detail": f"基于 {sample_count} 个样本技能集 F1 评估，平均 F1={avg_f1:.2%}",
    }


def evaluate_matching(golden_file, system_file):
    """评估人岗匹配准确率（阈值二元判定）。

    对比 golden 和 system 的 match_score 以及 skill_gap_detail，
    计算 match_score 的均方根误差 (RMSE) 和方向一致性 (match/no-match)。
    """
    golden_data = _load_jsonl(golden_file)
    system_data = _load_jsonl(system_file)
    system_map = {s.get("match_id", s.get("id", "")): s for s in system_data}

    if not golden_data:
        return {
            "metric": "人岗匹配准确率",
            "target": ">=90%",
            "current": 0.0,
            "status": "fail",
            "detail": "Golden set not found or empty",
        }

    threshold = 0.6  # match/no-match boundary
    correct = 0
    total = 0
    score_errors = []

    for golden in golden_data:
        gid = golden.get("match_id", golden.get("id", ""))
        system = system_map.get(gid, {})
        total += 1

        # Match score comparison
        g_score = golden.get("match_score", 0.0)
        s_score = system.get("match_score", 0.0)

        # Binary decision: above threshold = match
        g_match = g_score >= threshold
        s_match = s_score >= threshold

        if g_match == s_match:
            correct += 1

        score_errors.append(abs(g_score - s_score))

    accuracy = round(correct / total, 4) if total > 0 else 0.0
    avg_score_error = round(sum(score_errors) / len(score_errors), 4) if score_errors else 0.0
    passed = accuracy >= 0.90

    return {
        "metric": "人岗匹配准确率",
        "target": ">=90%",
        "current": f"{accuracy:.2%}",
        "status": "pass" if passed else "fail",
        "detail": f"基于 {total} 个样本二元判定，准确率 {accuracy:.2%}，平均分数误差 {avg_score_error:.4f}",
    }


def check_warning_level(results):
    """根据准确率返回预警级别（D8 决策）。

    Args:
        results: List of metric dicts with 'status' and 'current' fields.

    Returns:
        "green" / "yellow" / "orange" / "red"
    """
    if not results:
        return "green"

    # Extract percentage values from 'current' field (e.g., "92.50%")
    percentages = []
    for r in results:
        cur = r.get("current")
        if cur and isinstance(cur, str) and cur.endswith("%"):
            try:
                pct = float(cur.strip("%"))
                percentages.append(pct)
            except (ValueError, TypeError):
                pass

    if not percentages:
        return "green"

    min_pct = min(percentages)
    if min_pct < 75:
        return "red"
    if min_pct < 80:
        return "orange"
    if min_pct < 85:
        return "yellow"
    return "green"


def main():
    parser = argparse.ArgumentParser(description="StarMap 质量报告生成")
    parser.add_argument("--golden", default="data/golden/", help="Golden Set 目录")
    parser.add_argument("--system", default="data/output/", help="系统输出目录")
    parser.add_argument("--output", default="reports/", help="报告输出目录")
    parser.add_argument("--ci", action="store_true", help="CI 模式：输出 git HEAD + 三方准确率，fail 时 exit 1")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": datetime.now().isoformat(),
        "golden_dir": args.golden,
        "system_dir": args.system,
        "metrics": [
            evaluate_jd_extraction(
                Path(args.golden) / "jd_golden.jsonl",
                Path(args.system) / "jd_output.jsonl"
            ),
            evaluate_resume_extraction(
                Path(args.golden) / "resume_golden.jsonl",
                Path(args.system) / "resume_output.jsonl"
            ),
            evaluate_matching(
                Path(args.golden) / "match_golden.jsonl",
                Path(args.system) / "match_output.jsonl"
            ),
        ],
        "warning_level": check_warning_level([]),
    }

    # CI mode: add git HEAD
    if args.ci:
        try:
            git_head = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
        except Exception:
            git_head = "unknown"
        report["git_head"] = git_head

    # JSON 报告
    json_path = output_dir / "quality_report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # CI mode: also write CI-specific JSON
    if args.ci:
        ci_json_path = output_dir / "quality_report_ci.json"
        ci_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown 报告
    md_lines = [
        f"# StarMap 质量报告",
        f"",
        f"生成时间：{report['generated_at']}",
    ]
    if args.ci and report.get("git_head"):
        md_lines.append(f"> CI Run: {report['git_head']}")
    md_lines.extend([
        f"",
        f"| 指标 | 目标 | 当前 | 状态 |",
        f"|------|------|------|------|",
    ])
    for m in report["metrics"]:
        current = m["current"] if m["current"] is not None else "-"
        status_icon = {"pending": "⬜", "pass": "✅", "fail": "❌"}.get(m["status"], "⬜")
        md_lines.append(f"| {m['metric']} | {m['target']} | {current} | {status_icon} |")

    md_lines.append(f"")
    md_lines.append(f"**预警级别**：{report['warning_level']}")
    md_path = output_dir / "quality_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"质量报告已生成：")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    if args.ci:
        print(f"  CI JSON: {output_dir / 'quality_report_ci.json'}")
    print()
    for line in md_lines:
        safe = line.replace("✅", "[PASS]").replace("❌", "[FAIL]").replace("⬜", "[?]")
        try:
            print(safe)
        except UnicodeEncodeError:
            print(safe.encode("ascii", errors="replace").decode("ascii", errors="replace"))

    # CI mode: exit 1 if any metric failed
    if args.ci:
        any_failed = any(m["status"] == "fail" for m in report["metrics"])
        sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
