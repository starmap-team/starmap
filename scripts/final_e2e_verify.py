import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=15) as c:
        checks = []
        
        # 1. Health
        r = await c.get("/health")
        checks.append(("Health", r.status_code == 200, f"{r.status_code}"))
        
        # 2. Graph panorama - must have real data
        r = await c.get("/api/v1/graph/panorama")
        data = r.json()
        nodes = len(data.get("nodes", []))
        edges = len(data.get("edges", []))
        checks.append(("Graph nodes >= 50", nodes >= 50, f"{nodes}"))
        checks.append(("Graph edges >= 30", edges >= 30, f"{edges}"))
        
        # 3. Graph query read
        r = await c.get("/api/v1/graph/query", params={"cypher": "MATCH (p:Position)-[:REQUIRES]->(s:Skill) RETURN p.name, s.name LIMIT 5"})
        checks.append(("Graph query (read)", r.status_code == 200, f"{r.status_code}"))
        
        # 4. Graph query write blocked
        r = await c.get("/api/v1/graph/query", params={"cypher": "CREATE (n:Test) RETURN n"})
        checks.append(("Graph write blocked", r.status_code == 400, f"{r.status_code}"))
        
        # 5. Quality report
        r = await c.get("/api/v1/quality/report")
        checks.append(("Quality report", r.status_code == 200, f"{r.status_code}"))
        
        # 6. Quality dashboard
        r = await c.get("/api/v1/quality/dashboard")
        checks.append(("Quality dashboard", r.status_code == 200, f"{r.status_code}"))
        
        # 7. Evolution trends
        r = await c.get("/api/v1/evolution/trends")
        checks.append(("Evolution trends", r.status_code == 200, f"{r.status_code}"))
        
        # 8. Admin stats
        r = await c.get("/api/v1/admin/stats")
        checks.append(("Admin stats", r.status_code == 200, f"{r.status_code}"))
        
        # 9. Admin review queue
        r = await c.get("/api/v1/admin/review-queue")
        checks.append(("Admin review queue", r.status_code == 200, f"{r.status_code}"))
        
        # 10. Admin prompts
        r = await c.get("/api/v1/admin/prompts")
        checks.append(("Admin prompts", r.status_code == 200, f"{r.status_code}"))
        
        # 11. Positions
        r = await c.get("/api/v1/positions")
        checks.append(("Positions list", r.status_code == 200, f"{r.status_code}"))
        
        # 12. Extract JD (422 without body)
        r = await c.post("/api/v1/extract/jd")
        checks.append(("Extract JD validation", r.status_code == 422, f"{r.status_code}"))
        
        # 13. Match diagnose (422 without body)
        r = await c.post("/api/v1/match/diagnose")
        checks.append(("Match diagnose validation", r.status_code == 422, f"{r.status_code}"))
        
        # 14. Resume upload (422 without file)
        r = await c.post("/api/v1/resume/upload")
        checks.append(("Resume upload validation", r.status_code == 422, f"{r.status_code}"))
        
        # 15. Seed reset
        r = await c.post("/api/v1/admin/seed/reset")
        checks.append(("Seed reset", r.status_code == 200, f"{r.status_code}"))
        
        # 16. Judge evaluate (422 without body)
        r = await c.post("/api/v1/judge/evaluate")
        checks.append(("Judge evaluate validation", r.status_code == 422, f"{r.status_code}"))
        
        # 17. Evolution analyze
        r = await c.post("/api/v1/evolution/analyze")
        checks.append(("Evolution analyze", r.status_code == 200, f"{r.status_code}"))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\n=== StarMap E2E Verification ===")
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {detail}")
    print(f"\nResult: {passed}/{total} passed")
    if passed == total:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")

if __name__ == "__main__":
    asyncio.run(main())