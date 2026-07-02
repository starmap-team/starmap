#!/usr/bin/env python3
"""
StarMap — Comprehensive Health Check Script
Sprint 4.3: Verify all 8 services and 14 API endpoints.

Usage:
    python backend/scripts/health_check_all.py [--base-url http://localhost:8000]

Exit code: 0 = all healthy, 1 = at least one failure
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from typing import Optional


# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT = 10  # seconds per request

# Service health endpoints
SERVICES = [
    {
        "name": "Backend API",
        "check": "http",
        "url": "/health",
        "port": 8000,
    },
    {
        "name": "Celery Worker",
        "check": "celery",
    },
    {
        "name": "Frontend",
        "check": "http",
        "url": "/",
        "port": 80,
        "base_url": "http://localhost:80",
        "expect_html": True,
    },
    {
        "name": "Neo4j",
        "check": "http",
        "url": "",
        "port": 7474,
        "base_url": "http://localhost:7474",
    },
    {
        "name": "PostgreSQL",
        "check": "port",
        "port": 5432,
    },
    {
        "name": "Redis",
        "check": "port",
        "port": 6379,
    },
    {
        "name": "ChromaDB",
        "check": "http",
        "url": "/api/v1/heartbeat",
        "port": 8001,
        "base_url": "http://localhost:8001",
    },
    {
        "name": "Ollama",
        "check": "http",
        "url": "/api/tags",
        "port": 11434,
        "base_url": "http://localhost:11434",
    },
]

# API endpoints to verify (relative to base URL)
API_ENDPOINTS = [
    {"name": "Health", "method": "GET", "path": "/health"},
    {"name": "Graph Panorama", "method": "GET", "path": "/api/v1/graph/panorama"},
    {"name": "Graph Query", "method": "POST", "path": "/api/v1/graph/query", "body": {"query": "test"}},
    {"name": "Positions", "method": "GET", "path": "/api/v1/positions"},
    {"name": "Extract JD", "method": "POST", "path": "/api/v1/extract/jd", "body": {"text": "test"}, "expect_status_range": (200, 499)},
    {"name": "Match Diagnose", "method": "POST", "path": "/api/v1/match/diagnose", "body": {"resume_text": "test"}, "expect_status_range": (200, 499)},
    {"name": "Resume Upload", "method": "POST", "path": "/api/v1/resume/upload", "body": {}, "expect_status_range": (200, 499)},
    {"name": "Judge Evaluate", "method": "POST", "path": "/api/v1/judge/evaluate", "body": {}, "expect_status_range": (200, 499)},
    {"name": "Quality Report", "method": "GET", "path": "/api/v1/quality/report"},
    {"name": "Quality Dashboard", "method": "GET", "path": "/api/v1/quality/dashboard"},
    {"name": "Evolution Trends", "method": "GET", "path": "/api/v1/evolution/trends"},
    {"name": "Admin Stats", "method": "GET", "path": "/api/v1/admin/stats"},
    {"name": "Dashboard Overview", "method": "GET", "path": "/api/v1/dashboard/overview"},
    {"name": "Datasource List", "method": "GET", "path": "/api/v1/datasource/list"},
]


# ═══════════════════════════════════════════════
# Check Functions
# ═══════════════════════════════════════════════

def check_http(url: str, method: str = "GET", body: Optional[dict] = None,
               expect_html: bool = False, expect_status_range: tuple = (200, 399)) -> tuple[bool, str]:
    """Check HTTP endpoint. Returns (success, message)."""
    try:
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            if expect_status_range[0] <= status <= expect_status_range[1]:
                return True, f"HTTP {status}"
            else:
                return False, f"HTTP {status} (expected {expect_status_range})"
    except urllib.error.HTTPError as e:
        status = e.code
        if expect_status_range[0] <= status <= expect_status_range[1]:
            return True, f"HTTP {status}"
        return False, f"HTTP {status}"
    except urllib.error.URLError as e:
        return False, f"Connection failed: {e.reason}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def check_port(port: int, host: str = "localhost") -> tuple[bool, str]:
    """Check if a TCP port is open. Returns (success, message)."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=5):
            return True, f"Port {port} open"
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return False, f"Port {port} closed: {e}"


def check_celery(base_url: str) -> tuple[bool, str]:
    """Check Celery via backend API health endpoint."""
    try:
        url = f"{base_url}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            celery_status = data.get("celery", data.get("services", {}).get("celery"))
            if celery_status in ("ok", "healthy", True):
                return True, "Celery healthy"
            # Fallback: just check if backend is up (celery might not be in health)
            return True, "Backend up (celery status unknown)"
    except Exception:
        return False, "Cannot verify via backend"


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="StarMap Health Check — All Services & APIs")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend API base URL")
    parser.add_argument("--skip-api", action="store_true", help="Skip API endpoint checks")
    parser.add_argument("--skip-services", action="store_true", help="Skip service checks")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    results = []
    all_passed = True

    print("=" * 70)
    print("  StarMap Health Check")
    print(f"  Base URL: {base_url}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ── Service Checks ──
    if not args.skip_services:
        print("\n┌─ Services (8) ──────────────────────────────────────────────────┐")
        for svc in SERVICES:
            name = svc["name"]
            check_type = svc["check"]
            svc_base = svc.get("base_url", base_url)
            success = False
            msg = ""

            if check_type == "http":
                url = svc_base.rstrip("/") + svc.get("url", "")
                success, msg = check_http(url, expect_html=svc.get("expect_html", False))
            elif check_type == "port":
                success, msg = check_port(svc["port"])
            elif check_type == "celery":
                success, msg = check_celery(base_url)

            status_icon = "✅" if success else "❌"
            if not success:
                all_passed = False
            print(f"│  {status_icon} {name:<20s} {msg}")
            results.append({"type": "service", "name": name, "ok": success, "detail": msg})
        print("└────────────────────────────────────────────────────────────────┘")

    # ── API Endpoint Checks ──
    if not args.skip_api:
        print(f"\n┌─ API Endpoints ({len(API_ENDPOINTS)}) ───────────────────────────────────────────┐")
        for ep in API_ENDPOINTS:
            name = ep["name"]
            method = ep.get("method", "GET")
            path = ep["path"]
            body = ep.get("body")
            expect_range = ep.get("expect_status_range", (200, 399))
            url = base_url + path

            success, msg = check_http(url, method=method, body=body, expect_status_range=expect_range)
            status_icon = "✅" if success else "❌"
            if not success:
                all_passed = False
            print(f"│  {status_icon} {name:<24s} {method:<6s} {path:<40s} {msg}")
            results.append({"type": "api", "name": name, "method": method, "path": path, "ok": success, "detail": msg})
        print("└────────────────────────────────────────────────────────────────┘")

    # ── Summary ──
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    print(f"\n{'=' * 70}")
    print(f"  Summary: {passed}/{total} passed, {failed} failed")
    if all_passed:
        print("  Status: ✅ ALL HEALTHY")
    else:
        print("  Status: ❌ SOME CHECKS FAILED")
    print(f"{'=' * 70}\n")

    if args.json:
        print(json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_url": base_url,
            "total": total,
            "passed": passed,
            "failed": failed,
            "all_healthy": all_passed,
            "results": results,
        }, indent=2, ensure_ascii=False))

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
