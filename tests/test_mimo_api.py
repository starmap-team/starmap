"""验证 MiMo API 接入是否可用。

最小端到端测试：config 加载 → LLM 调用 → JSON 解析。
从项目根目录运行：python tests/test_mimo_api.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 切到项目根目录，让 config.py 能读到 .env
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "backend"))

# 在 chdir 之后导入 config，确保 .env 路径正确
from app.config import settings  # noqa: E402
from app.core.extraction.llm_client import (  # noqa: E402
    LLMClient,
    call_mimo_llm,
    call_llm_with_fallback,
)


async def test_mimo_direct():
    """直接调用 call_mimo_llm，验证认证+端点+模型。"""
    print("=" * 60)
    print("[Test 1] 直接调用 call_mimo_llm")
    print(f"  端点: {settings.mimo_api_base}")
    print(f"  模型: {settings.mimo_model}")
    print(f"  Key: {'已配置' if settings.mimo_api_key else '未配置'}")
    if not settings.mimo_api_key:
        print("  SKIP: MIMO_API_KEY 未配置")
        return False

    result = await call_mimo_llm("只回复两个字：通过")
    content = result.get("content", "")
    print(f"  响应: {content}")
    assert content, "MiMo 返回空 content"
    print("  ✅ PASS\n")
    return True


async def test_llm_fallback():
    """通过 call_llm_with_fallback 调用，验证 MiMo 作为首选通道。"""
    print("=" * 60)
    print("[Test 2] call_llm_with_fallback 通道优先级")
    result = await call_llm_with_fallback(
        '只回复JSON: {"status":"ok"}'
    )
    content = result.get("content", "")
    model = result.get("model", "unknown")
    print(f"  使用模型: {model}")
    print(f"  响应: {content[:100]}")
    assert content, "fallback 返回空 content"
    print("  ✅ PASS\n")
    return True


async def test_llm_client_extract():
    """通过 LLMClient.extract_from_jd 调用真实 JD 抽取。"""
    print("=" * 60)
    print("[Test 3] LLMClient.extract_from_jd 真实 JD 抽取")
    jd = (
        "招聘高级前端工程师，要求精通React和TypeScript，3年以上Web开发经验，"
        "熟悉Webpack构建工具，了解Next.js和GraphQL加分，本科及以上学历。"
    )
    client = LLMClient()
    result = await client.extract_from_jd(jd)
    print(f"  抽取结果: {result}")
    assert isinstance(result, dict), f"期望 dict，得到 {type(result)}"
    print("  ✅ PASS\n")
    return True


async def main():
    print("\n🔍 MiMo API 接入验证\n")
    print(f"项目根目录: {ROOT}")
    print(f"当前工作目录: {Path.cwd()}")
    print()

    results = []
    results.append(await test_mimo_direct())
    results.append(await test_llm_fallback())
    results.append(await test_llm_client_extract())

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\n结果: {passed}/{total} 通过")
    if passed == total:
        print("🎉 MiMo 接入验证全部通过！可以开始真实评估。")
    else:
        print("⚠️ 有测试失败，请检查配置。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
