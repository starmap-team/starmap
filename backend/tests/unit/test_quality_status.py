"""quality.py _status() 边界值单测 — 确保 pass/warn/fail 三态语义正确。

ponytail-audit MEDIUM: _status() 无边界值测试，阈值漂移时静默改变分类。
"""
from app.api.v1.quality import _status


class TestStatusBoundary:
    """_status() 三态边界值测试。"""

    def test_pass_at_threshold(self):
        """值恰好等于阈值 → pass。"""
        assert _status(0.90, 0.90) == "pass"

    def test_pass_above_threshold(self):
        """值超过阈值 → pass。"""
        assert _status(0.95, 0.90) == "pass"

    def test_warn_at_warn_boundary(self):
        """值恰好等于 threshold * 0.9 → warn。"""
        assert _status(0.81, 0.90) == "warn"

    def test_warn_just_above_warn_boundary(self):
        """值略高于 warn 边界 → warn。"""
        assert _status(0.82, 0.90) == "warn"

    def test_warn_just_below_threshold(self):
        """值略低于阈值但在 warn 区间 → warn。"""
        assert _status(0.89, 0.90) == "warn"

    def test_fail_below_warn_boundary(self):
        """值低于 threshold * 0.9 → fail。"""
        assert _status(0.80, 0.90) == "fail"

    def test_fail_well_below(self):
        """值远低于阈值 → fail。"""
        assert _status(0.50, 0.90) == "fail"

    def test_fail_zero(self):
        """值为 0 → fail。"""
        assert _status(0.0, 0.90) == "fail"

    def test_different_threshold(self):
        """不同阈值下的边界。"""
        # threshold=0.80, warn_boundary=0.72 (float: 0.7200000000000001)
        assert _status(0.80, 0.80) == "pass"
        assert _status(0.73, 0.80) == "warn"  # 略高于 warn 边界
        assert _status(0.71, 0.80) == "fail"  # 低于 warn 边界

    def test_float_precision(self):
        """浮点精度边界。"""
        # threshold=0.90, warn_boundary=0.81
        assert _status(0.8100001, 0.90) == "warn"
        assert _status(0.8099999, 0.90) == "fail"
