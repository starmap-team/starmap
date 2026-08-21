"""Phase 27 import stage in-batch dedup tests.

import_.run() 涉及 DB + Celery + SSE,完整集成需要 docker;
本测试聚焦 dedup 算法本身的正确性,直接复制 import_.py 中
_extract_one 的核心逻辑(同步版本)并验证 4 项不变量。
"""
from __future__ import annotations

import hashlib


def _make_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _build_extractor(call_counter: dict) -> callable:
    """模拟 import_._extract_one 的 dedup 行为。"""
    cached: dict[str, dict] = {}

    def extract(text: str) -> dict:
        h = _make_hash(text)
        if h in cached:
            reused = dict(cached[h])
            reused.setdefault("warnings", []).append(
                "in-batch dedup: same content as a prior JD in this batch",
            )
            return reused
        call_counter["n"] += 1
        result = {
            "status": "completed",
            "data": {"required_skills": [{"name": "Python"}]},
            "warnings": [],
        }
        cached[h] = result
        return result

    return extract


def test_same_content_triggers_llm_once() -> None:
    counter = {"n": 0}
    extract = _build_extractor(counter)

    extract("JD A")
    extract("JD A")
    extract("JD A")

    assert counter["n"] == 1, "同 hash 三次调用,LLM 应仅跑 1 次"


def test_dedup_warning_present_on_reused() -> None:
    counter = {"n": 0}
    extract = _build_extractor(counter)

    extract("JD A")
    reused = extract("JD A")

    assert any("in-batch dedup" in w for w in reused["warnings"])


def test_no_dedup_warning_on_first_call() -> None:
    counter = {"n": 0}
    extract = _build_extractor(counter)

    first = extract("JD A")

    assert not any("in-batch dedup" in w for w in first["warnings"])


def test_different_content_each_calls_llm() -> None:
    counter = {"n": 0}
    extract = _build_extractor(counter)

    extract("JD A")
    extract("JD B")
    extract("JD C")

    assert counter["n"] == 3


def test_failed_result_not_cached() -> None:
    """失败的抽取结果不缓存:同 hash 后续仍能重试。"""
    cached: dict[str, dict] = {}
    call_count = {"n": 0}

    def extract_with_failure(text: str) -> dict:
        h = _make_hash(text)
        if h in cached:
            return dict(cached[h])
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"status": "failed", "error": "LLM timeout", "warnings": []}
        result = {"status": "completed", "data": {"required_skills": []}, "warnings": []}
        cached[h] = result
        return result

    r1 = extract_with_failure("same content")
    r2 = extract_with_failure("same content")
    r3 = extract_with_failure("same content")

    assert r1["status"] == "failed"
    assert r2["status"] == "completed"
    assert r3["status"] == "completed"
    assert call_count["n"] == 2, "失败不缓存 → 重试成功 → 第三次命中缓存"


def test_hash_distinguishes_different_content() -> None:
    """hash 必须对微小差异敏感,否则误命中会导致错误抽取结果被复用。"""
    a = _make_hash("Senior Python Developer, 5 years experience")
    b = _make_hash("Senior Python Developer, 6 years experience")
    assert a != b
