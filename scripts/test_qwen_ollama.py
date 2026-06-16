"""Test Qwen2.5-7B via Ollama endpoint.

Run: docker-compose -f docker-compose.dev.yml up -d ollama
Then: poetry run python scripts/test_qwen_ollama.py

Note: First pull of qwen2.5:7b (~4.5GB) will take time.
"""

import asyncio
import os
import sys

import httpx

# Try container DNS first, then localhost
QWEN_ENDPOINTS = [
    "http://ollama:11434",
    "http://localhost:11434",
    os.getenv("QWEN_MODEL_PATH", ""),
]


async def test_qwen_connection() -> str | None:
    """Test connection to Qwen2.5-7B via Ollama, return working endpoint."""
    for endpoint in QWEN_ENDPOINTS:
        if not endpoint:
            continue
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{endpoint}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    names = [m["name"] for m in models]
                    print(f"  Connected to {endpoint}")
                    print(f"  Available models: {names}")
                    # Check if qwen2.5 is loaded
                    qwen_models = [n for n in names if "qwen2.5" in n or "qwen" in n]
                    if qwen_models:
                        return endpoint
                    else:
                        print(f"  WARNING: qwen2.5 not found in Ollama. Pull with: ollama pull qwen2.5:7b")
                        return endpoint
                else:
                    print(f"  {endpoint}: status {resp.status_code}")
        except Exception as e:
            print(f"  {endpoint}: {e}")
    return None


async def test_qwen_chat(endpoint: str) -> dict:
    """Test a simple chat completion via Ollama."""
    prompt = "Extract skills from this JD in JSON: Senior Python developer with 5 years experience, skilled in FastAPI, PostgreSQL, Docker."
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{endpoint}/v1/chat/completions",
            json={
                "model": "qwen2.5:7b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 1024,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"success": True, "content": content[:300], "model": data["model"]}
        else:
            return {"success": False, "error": f"Status {resp.status_code}: {resp.text}"}


async def main():
    print("=" * 60)
    print("Qwen2.5-7B / Ollama Connection Test")
    print("=" * 60)

    print("\n[1/2] Testing connection...")
    endpoint = await test_qwen_connection()

    if not endpoint:
        print("\n  Qwen/Ollama not available.")
        print("\n  To set up:")
        print("    docker-compose -f docker-compose.dev.yml up -d ollama")
        print("    docker exec starmap-ollama ollama pull qwen2.5:7b")
        print("\n  Or use standalone:")
        print("    docker run -d --name ollama -p 11434:11434 ollama/ollama")
        print("    docker exec ollama ollama pull qwen2.5:7b")
        return

    print(f"\n[2/2] Testing chat completion at {endpoint}...")
    result = await test_qwen_chat(endpoint)

    if result["success"]:
        print(f"\n  Model: {result['model']}")
        print(f"  Response preview: {result['content']}...")
        print("\n  ✅ Qwen2.5-7B is working!")
    else:
        print(f"\n  ❌ Chat test failed: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
