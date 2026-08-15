"""ALIGN-08 §14.5 落地：bootstrap 95% CI（§14.5）正确性 + 守卫。

纯 stdlib 实现；CI 含 lower/upper/mean/n/n_resamples 五字段；
样本数 < 2 返回 None（避免单样本假 CI）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 evaluation/ 加入 import 路径以直接 import judge_eval
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_EVAL = _ROOT / "evaluation"
_BACKEND = _ROOT / "backend"
for p in (_EVAL, _BACKEND):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from judge_eval import ExtractionMetrics, bootstrap_ci_95  # noqa: E402


def test_basic_range_and_structure() -> None:
    """正常 100 个 F1 值应得到合理的 95% CI。"""
    # 模拟 JD 抽取 F1 大致分布（中心 0.93，噪声 ±0.03）
    values = [0.93 + (i % 7 - 3) * 0.01 for i in range(100)]
    ci = bootstrap_ci_95(values, n_resamples=1000, seed=42)
    assert ci is not None, "100 个样本应能计算 CI"
    for key in ("lower", "upper", "mean", "n", "n_resamples"):
        assert key in ci, f"CI 缺字段 {key}"
    assert ci["n"] == 100
    assert ci["n_resamples"] == 1000
    assert ci["lower"] <= ci["mean"] <= ci["upper"], "lower <= mean <= upper"
    assert ci["upper"] - ci["lower"] < 0.1, f"CI 宽度异常 {ci}"
    assert 0.85 <= ci["mean"] <= 0.99, f"均值偏离中心: {ci}"


def test_seed_reproducible() -> None:
    """同 seed → 同结果（评审可复现，§14.5 关键）。"""
    values = [0.5, 0.7, 0.9, 0.6, 0.8, 0.4, 0.75, 0.85, 0.55, 0.65]
    a = bootstrap_ci_95(values, n_resamples=500, seed=42)
    b = bootstrap_ci_95(values, n_resamples=500, seed=42)
    assert a == b, "同 seed 必须可复现"


def test_empty_returns_none() -> None:
    """空列表 → None；单样本不能形成 CI。"""
    assert bootstrap_ci_95([]) is None
    assert bootstrap_ci_95([0.5]) is None


def test_filters_nan_and_none() -> None:
    """过滤 None / NaN。"""
    values = [0.5, 0.6, None, 0.7, float("nan"), 0.8]
    ci = bootstrap_ci_95(values, n_resamples=200, seed=1)
    assert ci is not None
    assert ci["n"] == 4, "应过滤 None/NaN 仅算有效样本"
    assert 0.5 <= ci["mean"] <= 0.8


def test_almost_zero_variance() -> None:
    """全相等值 → lower == upper == mean。"""
    values = [0.9] * 50
    ci = bootstrap_ci_95(values, n_resamples=100, seed=7)
    assert ci is not None
    assert ci["lower"] == ci["upper"] == ci["mean"] == 0.9


def test_extraction_metrics_ci_95_field() -> None:
    """ExtractionMetrics.ci_95 字段可承载 None 与 dict；不影响序列化。"""
    m = ExtractionMetrics()
    assert m.ci_95 is None
    m.ci_95 = {
        "f1": {"lower": 0.9, "upper": 0.96, "mean": 0.93, "n": 50, "n_resamples": 1000},
    }
    dumped = m.model_dump_json()
    assert "ci_95" in dumped
    # JSON 输出精度跟随原始 float（0.9 直接渲染为 0.9）
    assert "\"lower\":0.9" in dumped
    assert "\"mean\":0.93" in dumped
    assert "\"upper\":0.96" in dumped
