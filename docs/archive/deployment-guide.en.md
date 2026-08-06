# StarMap — Production Deployment Guide

**Version:** v3.0 · **Sprint:** 4.3 · **Date:** 2026-06-30

---

## 1. Overview

StarMap is an IT talent capability graph system (人才能力星云导航系统) built with FastAPI + Vue 3 + Neo4j + PostgreSQL. This guide covers production deployment using Docker Compose.

### System Architecture

| Service | Technology | Internal Port | External Port | Purpose |
|---------|-----------|---------------|---------------|---------|
| Backend API | FastAPI + Uvicorn | 8000 | 8000 | REST API (14 routers) |
| Celery Worker | Celery + Redis | — | — | Async task processing |
| Frontend | Vue 3 + Nginx | 80 | 80 | Static SPA serving |
| Neo4j | Neo4j 5 Community | 7687 | — | Graph database |
| PostgreSQL | PostgreSQL 16 | 5432 | — | Relational database |
| Redis | Redis 7 Alpine | 6379 | — | Cache / message queue |
| ChromaDB | ChromaDB | 8000 | — | Vector database |
| Ollama | Ollama + Qwen2.5-7B | 11434 | — | Local LLM inference |

---

## 2. Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 50 GB SSD |
| Network | Stable internet | — |

### Software Requirements

- **Docker** ≥ 24.0 ([Install Docker](https://docs.docker.com/engine/install/))
- **Docker Compose** ≥ 2.20 (included with Docker Desktop)
- **Git** ≥ 2.0

Verify installation:

```bash
docker --version       # Docker version 24.x+
docker compose version # Docker Compose version 2.x+
git --version          # git version 2.x+
```

---

## 3. Quick Start

### 3.1 Clone Repository

```bash
git clone https://github.com/your-org/starmap.git
cd starmap
```

### 3.2 Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit with your settings
nano .env
```

**Required environment variables:**

```env
# Database passwords
POSTGRES_PASSWORD=your_secure_password
NEO4J_PASSWORD=your_secure_password

# LLM API Keys (at least one required for extraction)
DEEPSEEK_API_KEY=your_key
MIMO_API_KEY=your_key
XUNFEI_API_KEY=your_key

# Optional: External model API
OPENAI_API_KEY=your_key
```

### 3.3 Build and Start

```bash
# Build all images and start in detached mode
docker compose -f docker-compose.prod.yml up -d --build

# Watch startup logs
docker compose -f docker-compose.prod.yml logs -f
```

### 3.4 Verify Deployment

```bash
# Run comprehensive health check
python backend/scripts/health_check_all.py --base-url http://localhost:8000

# Or check individual services
curl http://localhost:8000/health
curl http://localhost:80/        # Frontend
```

### 3.5 Access the Application

- **Frontend:** http://localhost:80
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

---

## 4. Configuration

### 4.1 Docker Compose Resource Limits

Each service has CPU and memory limits configured in `docker-compose.prod.yml`. Adjust based on your hardware:

```yaml
# Example: Increase backend workers
backend:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 8
  deploy:
    resources:
      limits:
        cpus: "4.0"
        memory: 4G
```

### 4.2 Neo4j Memory Tuning

For large graphs (>100K nodes), increase Neo4j heap:

```yaml
neo4j:
  environment:
    - NEO4J_server_memory_heap_max__size=2G
    - NEO4J_server_memory_pagecache_size=1G
```

### 4.3 Ollama Model Selection

Default model is `qwen2.5:7b`. To use a different model:

```bash
# Pull alternative model
docker compose -f docker-compose.prod.yml exec ollama ollama pull qwen2.5:14b

# Update OLLAMA_MODEL in .env
echo "OLLAMA_MODEL=qwen2.5:14b" >> .env
```

### 4.4 SSL / Reverse Proxy (Production)

For HTTPS, add an Nginx reverse proxy or use Caddy:

```nginx
server {
    listen 443 ssl;
    server_name starmap.your-domain.com;

    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    location / {
        proxy_pass http://localhost:80;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 5. Data Management

### 5.1 Data Persistence

All persistent data is stored in named Docker volumes:

| Volume | Service | Content |
|--------|---------|---------|
| `neo4j_data_prod` | Neo4j | Graph data |
| `postgres_data_prod` | PostgreSQL | Relational data |
| `redis_data_prod` | Redis | Cache + queues |
| `chroma_data_prod` | ChromaDB | Vector embeddings |
| `ollama_data_prod` | Ollama | LLM model weights |

### 5.2 Backup

```bash
# Backup PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U starmap starmap > backup_$(date +%Y%m%d).sql

# Backup Neo4j
docker compose -f docker-compose.prod.yml exec neo4j \
  neo4j-admin database dump --to-path=/backups/ neo4j

# Backup all volumes
for vol in neo4j_data_prod postgres_data_prod redis_data_prod chroma_data_prod ollama_data_prod; do
  docker run --rm -v ${vol}:/data -v $(pwd)/backups:/backup alpine \
    tar czf /backup/${vol}_$(date +%Y%m%d).tar.gz -C /data .
done
```

### 5.3 Restore

```bash
# Restore PostgreSQL
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U starmap starmap < backup_20260630.sql
```

---

## 6. Operations

### 6.1 View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail 100 backend
```

### 6.2 Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yml restart

# Restart single service
docker compose -f docker-compose.prod.yml restart backend
```

### 6.3 Update and Redeploy

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Run health check
python backend/scripts/health_check_all.py
```

### 6.4 Scale Workers

```bash
# Scale celery workers
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=3
```

---

## 7. Troubleshooting

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Backend returns 503 | Database not ready | Wait for health checks, or restart backend |
| Neo4j connection refused | Memory too low | Increase Neo4j memory limits |
| Ollama timeout | Model not downloaded | Wait for `ollama-pull` container to finish |
| Frontend blank page | API proxy misconfigured | Check `VITE_API_BASE_URL` build arg |
| Celery tasks stuck | Redis not reachable | Verify Redis health, restart celery-worker |
| Port 80 already in use | Another service bound | Stop conflicting service or change port |

### Debug Commands

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps

# Enter a container
docker compose -f docker-compose.prod.yml exec backend bash

# Check Neo4j directly
docker compose -f docker-compose.prod.yml exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD

# Check PostgreSQL directly
docker compose -f docker-compose.prod.yml exec postgres psql -U starmap starmap

# Check Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Resource usage
docker stats --no-stream
```

### Health Check Script

```bash
# Full health check (all 8 services + 14 API endpoints)
python backend/scripts/health_check_all.py --base-url http://localhost:8000

# Service-only check
python backend/scripts/health_check_all.py --skip-api

# API-only check
python backend/scripts/health_check_all.py --skip-services

# JSON output for CI
python backend/scripts/health_check_all.py --json
```

---

## 8. API Documentation

Once the backend is running, interactive API documentation is available at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

### API Router Summary

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| graph | /api/v1/graph | Panorama, query, position detail |
| position | /api/v1/positions | List, filter, paginate |
| extract | /api/v1/extract | JD extraction |
| match | /api/v1/match | Resume matching, diagnosis |
| resume | /api/v1/resume | Upload, parse |
| judge | /api/v1/judge | LLM evaluation |
| quality | /api/v1/quality | Quality report, dashboard |
| evolution | /api/v1/evolution | Trends, analysis |
| pipeline | /api/v1/pipeline | Pipeline status, runs |
| datasource | /api/v1/datasource | Source management |
| dashboard | /api/v1/dashboard | Real-time overview, SSE |
| admin | /api/v1/admin | Stats, review queue, prompts |
| loop | /api/v1/loop | Closed-loop demo |
| learning | /api/v1/learning | Learning center |

---

## 9. CI/CD Integration

### Quality Gate

```yaml
# .github/workflows/quality-gate.yml
name: Quality Gate
on: [push, pull_request]
jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Start services
        run: docker compose -f docker-compose.prod.yml up -d
      - name: Wait for services
        run: sleep 30
      - name: Health check
        run: python backend/scripts/health_check_all.py --json
      - name: E2E tests
        run: cd frontend && npx cypress run --spec e2e/quality-gate.cy.ts
```

---

**Document version:** v3.0 | **Last updated:** 2026-06-30
