"""Pipeline 错误信息友好化 — 把技术异常翻译为普通用户可读的中文说明。

2026-08-21 (debug 修复): 用户反馈错误信息看不懂（orphaned by watchdog、
'builtin_function_or_method' object is not subscriptable 等英文技术术语）。
本模块在 API 序列化时把 errors/error_log 翻译为「中文可读 + 保留技术原文」，
前端展示中文摘要，原文作为可展开的技术详情。

设计:
- humanize_error(err) -> str: 单条错误翻译（匹配失败返回原文，不丢失信息）
- humanize_errors(errs) -> list[str]: 批量翻译
- humanize_error_log(text) -> str: run 级 error_log 翻译
"""
from __future__ import annotations

import re

# ── run 级 error_log 翻译 ──

_ERROR_LOG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"orphaned by watchdog", re.I),
     "运行超时被系统自动终止（可能因单阶段执行超过 30 分钟）"),
    (re.compile(r"cancelled by user", re.I),
     "已由用户手动取消"),
    (re.compile(r"Auto-cleaned: stuck running for (\d+) min", re.I),
     "运行卡住超过 {1} 分钟被系统自动清理（可能是服务重启导致）"),
    (re.compile(r"zombie run auto-failed", re.I),
     "运行进程丢失被系统自动标记失败（可能是服务重启导致）"),
    (re.compile(r"Failed stages: (\[.*?\])", re.I),
     "以下阶段执行失败: {1}"),
]


def humanize_error_log(text: str | None) -> str:
    """Run 级 error_log 翻译；无法匹配时原样返回。"""
    if not text:
        return ""
    for pattern, template in _ERROR_LOG_PATTERNS:
        m = pattern.search(text)
        if m:
            return _fill(template, m)
    return text


# ── stage errors 翻译 ──

# (pattern, 中文模板) —— {1} {2} 为捕获组填充
_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # LLM / 抽取类
    (re.compile(r"LLM (?:connection|timeout|response) error", re.I),
     "AI 模型调用失败（网络或服务异常）"),
    (re.compile(r"LLM blocked", re.I),
     "AI 模型调用被资源限制拦截（成本上限或全局开关）"),
    (re.compile(r"Fallback LLM transport failed", re.I),
     "备用 AI 模型也无法连接"),
    (re.compile(r"extraction failed", re.I),
     "岗位信息抽取失败"),
    (re.compile(r"Failed to parse LLM JSON response", re.I),
     "AI 返回内容无法解析"),
    (re.compile(r"JSON parse error", re.I),
     "数据解析失败"),
    # 数据库类
    (re.compile(r"column ([\w.]+) does not exist", re.I),
     "数据库字段缺失: {1}（可能需要更新数据库结构）"),
    (re.compile(r"StringDataRightTruncation", re.I),
     "数据内容超出字段长度限制"),
    (re.compile(r"asyncpg\.|psycopg\.|sqlalchemy.*Error", re.I),
     "数据库操作失败"),
    (re.compile(r"duplicate key", re.I),
     "数据重复（已存在相同记录）"),
    # 爬虫类（crawl failed 放最后兜底 —— 具体内部错误优先匹配）
    (re.compile(r"timed? ?out", re.I),
     "请求超时"),
    (re.compile(r"connection (?:refused|failed|error)", re.I),
     "网络连接失败"),
    (re.compile(r"HTTP (\d{3})", re.I),
     "目标网站返回错误状态码 {1}"),
    (re.compile(r"403|429|forbidden|rate limit", re.I),
     "被目标网站限制访问（频率过高或需要登录）"),
    # 进程/状态类
    (re.compile(r"stage orphaned by watchdog", re.I),
     "阶段因运行超时被系统终止"),
    # 内部程序错误（具体优先于笼统的 crawl failed）
    (re.compile(r"builtin_function_or_method.*not subscriptable", re.I),
     "内部程序错误（函数调用写法有误）"),
    (re.compile(r"unsupported operand type", re.I),
     "内部程序错误（数据类型不匹配）"),
    (re.compile(r"coroutine was expected", re.I),
     "内部程序错误（异步调用写法有误）"),
    (re.compile(r"cannot access local variable", re.I),
     "内部程序错误（变量未初始化）"),
    (re.compile(r"triples_merged", re.I),
     "图谱数据写入异常"),
    (re.compile(r"Unknown stage", re.I),
     "未知的流水线阶段"),
    (re.compile(r"crawl failed", re.I),
     "采集失败"),
]


def humanize_error(err: str) -> str:
    """单条错误翻译；匹配失败返回原文（保证信息不丢失）。"""
    if not err:
        return err
    for pattern, template in _ERROR_PATTERNS:
        m = pattern.search(err)
        if m:
            return _fill(template, m)
    return err


def humanize_errors(errs: list[str]) -> list[str]:
    """批量翻译，保持顺序。"""
    return [humanize_error(e) for e in errs]


def _fill(template: str, m: re.Match[str]) -> str:
    """把模板里的 {1} {2} 替换为捕获组。"""
    result = template
    for i in range(1, len(m.groups()) + 1):
        result = result.replace(f"{{{i}}}", m.group(i) or "")
    return result


__all__ = ["humanize_error", "humanize_errors", "humanize_error_log"]
