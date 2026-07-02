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

        # 18. Pipeline analyze (SSE) — 使用测试简历
        import pathlib
        resume_path = pathlib.Path(__file__).parent.parent / "backend" / "tests" / "fixtures" / "test_resume_backend.txt"
        if resume_path.exists():
            resume_bytes = resume_path.read_bytes()
            files = {"resume_file": ("test_resume.txt", resume_bytes, "text/plain")}
            r = await c.post("/api/v1/pipeline/analyze", files=files, timeout=120)
            checks.append(("Pipeline analyze SSE", r.status_code == 200, f"{r.status_code}"))
            # 验证 SSE 事件流包含 progress 和 result 事件
            body = r.text
            has_progress = "event: progress" in body
            has_result = "event: result" in body
            checks.append(("Pipeline SSE has progress events", has_progress, str(has_progress)))
            checks.append(("Pipeline SSE has result event", has_result, str(has_result)))
            # 验证 result 包含4个核心问题的答案
            if has_result:
                import re
                result_match = re.search(r'event: result\ndata: ({.*?})\n', body, re.DOTALL)
                if result_match:
                    result_data = json.loads(result_match.group(1))
                    has_skills = len(result_data.get("extracted_skills", [])) > 0
                    has_matches = len(result_data.get("top_matches", [])) > 0
                    has_recs = len(result_data.get("recommended_positions", [])) > 0
                    has_gaps = len(result_data.get("skill_gaps", [])) > 0
                    checks.append(("Pipeline result has skills", has_skills, str(has_skills)))
                    checks.append(("Pipeline result has matches", has_matches, str(has_matches)))
                    checks.append(("Pipeline result has recommendations", has_recs, str(has_recs)))
                    checks.append(("Pipeline result has gaps", has_gaps, str(has_gaps)))
        else:
            checks.append(("Pipeline analyze SSE", False, "test resume not found"))

        # 19. Pipeline export (JSON)
        if resume_path.exists():
            files = {"resume_file": ("test_resume.txt", resume_bytes, "text/plain")}
            r = await c.post("/api/v1/pipeline/export", files=files, timeout=120)
            checks.append(("Pipeline export JSON", r.status_code == 200, f"{r.status_code}"))
            if r.status_code == 200:
                export_data = r.json()
                checks.append(("Pipeline export has skills", len(export_data.get("extracted_skills", [])) > 0, str(len(export_data.get("extracted_skills", [])))))
                checks.append(("Pipeline export has matches", len(export_data.get("top_matches", [])) > 0, str(len(export_data.get("top_matches", [])))))

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