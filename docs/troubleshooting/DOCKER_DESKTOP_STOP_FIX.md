# Docker Desktop 容器持久化问题解决方案

## 问题描述

在 Docker Desktop 中点击 Compose Stack 的 **Stop 按钮**（蓝色方块）后，容器从列表中消失，无法通过 **Start 按钮**重新启动。

## 根本原因

Docker Desktop 的 Stop 按钮执行的是 **`docker compose down`**，而不是 `docker compose stop`：

| 操作 | 实际执行命令 | 容器状态 | 能否 Start |
|------|-----------|---------|-----------|
| Docker Desktop ▶️ Start | `docker compose up -d` | 创建/启动 | - |
| Docker Desktop ⏹️ Stop | `docker compose down` | **删除容器** | ❌ 不能 |
| 命令行 `stop` | `docker compose stop` | 保留(Exited) | ✅ 能 |
| 命令行 `start` | `docker compose start` | 恢复运行 | ✅ 能 |

## 解决方案

### 方案 1：使用命令行操作（推荐）

```bash
cd C:/Users/LiShuai/Desktop/Agents/starmap

# 停止容器（保留容器，下次启动更快）
docker compose -f docker-compose.dev.yml stop

# 启动已停止的容器
docker compose -f docker-compose.dev.yml start
```

### 方案 2：使用 Docker Desktop 的容器级操作

1. **不要点击顶部的 Stop 按钮**
2. 展开 Compose Stack，看到各个容器
3. 点击单个容器的 **Stop 按钮**（⏹️ 小方块）
4. 这样只会停止单个容器，不会删除它
5. 之后可以点击单个容器的 **Start 按钮**（▶️）重新启动

### 方案 3：修改 docker-compose.dev.yml 添加保护

已在 `docker-compose.dev.yml` 中为所有服务添加：

```yaml
services:
  backend:
    # ...
    restart: unless-stopped  # 容器停止后不会自动重启，但保留容器
    stop_signal: SIGTERM
    stop_grace_period: 10s
```

### 方案 4：使用 Docker Desktop CLI 替代

```bash
# 安装 Docker Desktop CLI 扩展
# 使用命令行精确控制
docker compose -f docker-compose.dev.yml stop  # 停止
docker compose -f docker-compose.dev.yml start # 启动
```

## 最佳实践

### 开发环境推荐工作流

```bash
# 1. 首次启动（创建容器）
docker compose -f docker-compose.dev.yml up -d

# 2. 日常开发 - 停止（保留容器）
docker compose -f docker-compose.dev.yml stop

# 3. 日常开发 - 启动（使用已有容器）
docker compose -f docker-compose.dev.yml start

# 4. 完全重置（删除并重新创建）
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d

# 5. 完全清理（包括数据卷）
docker compose -f docker-compose.dev.yml down -v
```

### 关键区别

```bash
# ✅ 推荐：stop/start（保留容器，快速重启）
docker compose -f docker-compose.dev.yml stop
docker compose -f docker-compose.dev.yml start

# ⚠️ 慎用：down/up（删除容器，重新创建）
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d
```

## 数据持久化说明

即使容器被删除（`docker compose down`），数据也不会丢失：

| 数据类型 | 存储位置 | down 后 |
|---------|---------|---------|
| PostgreSQL 数据 | Docker Volume `postgres_data` | ✅ 保留 |
| Neo4j 数据 | Docker Volume `neo4j_data` | ✅ 保留 |
| Redis 数据 | Docker Volume `redis_data` | ✅ 保留 |
| ChromaDB 数据 | Docker Volume `chroma_data` | ✅ 保留 |
| Ollama 模型 | Docker Volume `ollama_data` | ✅ 保留 |
| 代码文件 | 宿主机挂载 | ✅ 保留 |

## 常见问题

### Q: 容器被删除后如何恢复？

**A**: 数据不会丢失，只需重新创建容器：

```bash
docker compose -f docker-compose.dev.yml up -d
```

### Q: 如何查看已停止的容器？

**A**: 

```bash
# 命令行
docker ps -a

# Docker Desktop
# 1. 关闭 "Only show running containers" 开关
# 2. 或查看 "Exited" 状态的容器
```

### Q: 为什么 Docker Desktop 的 Stop 按钮会删除容器？

**A**: 这是 Docker Desktop 的设计选择：
- **Stop 按钮** = `docker compose down`（清理资源）
- **Start 按钮** = `docker compose up -d`（创建新容器）

Docker Desktop 假设用户点击 Stop 后想要释放资源，而不是保留容器。

## 相关配置

### docker-compose.dev.yml 关键配置

```yaml
services:
  backend:
    container_name: starmap-backend
    restart: unless-stopped  # 服务崩溃时自动重启
    stop_signal: SIGTERM     # 优雅停止信号
    stop_grace_period: 10s  # 停止超时时间
```

### .env 环境变量

```bash
# 确保使用 Docker 模式
cp .env.docker .env
```

## 总结

| 场景 | 推荐命令 | 说明 |
|------|---------|------|
| 日常开发暂停 | `docker compose stop` | 保留容器，秒级启动 |
| 日常开发恢复 | `docker compose start` | 使用已有容器 |
| 完全重置 | `docker compose down && up -d` | 删除并重建 |
| 清理磁盘 | `docker compose down -v` | 删除容器+数据卷 |
| 查看状态 | `docker compose ps -a` | 查看所有容器 |

> **重要**: Docker Desktop 的 Stop 按钮会删除容器。请使用命令行 `docker compose stop` 来保留容器。
