# Docker 部署与运维

本模块将项目容器化，用 Docker Compose 一键启动所有服务（FastAPI + Celery Worker + Redis + PostgreSQL），方便面试演示和生产部署。

---

## 1. 概念学习

### 为什么需要 Docker？

| 问题 | Docker 解决方案 |
|---|---|
| "在我机器上能跑" | 容器包含完整运行环境，任何机器行为一致 |
| 依赖安装复杂（Redis、PG、Python 版本） | 一条命令启动所有服务 |
| 面试演示环境不稳定 | Docker Compose 一键启动，随时演示 |
| 多服务协调（API + Worker + DB） | Compose 定义服务依赖和网络 |

### Docker 核心概念

| 概念 | 说明 |
|---|---|
| **Image（镜像）** | 应用的只读模板，包含代码 + 依赖 + 运行环境 |
| **Container（容器）** | 镜像的运行实例 |
| **Dockerfile** | 构建镜像的脚本 |
| **Docker Compose** | 定义和运行多容器应用的工具 |
| **Volume（卷）** | 持久化数据存储，容器删除后数据不丢 |

### 本项目的服务架构

```
docker-compose.yml
├── api          # FastAPI 应用（主服务）
├── worker       # Celery Worker（异步任务处理）
├── redis        # Redis（缓存 + 消息队列）
├── postgres     # PostgreSQL（数据库）
└── volumes
    ├── pg_data      # 数据库持久化
    ├── redis_data   # Redis 持久化
    ├── chroma_data  # 向量数据库持久化
    └── upload_data  # 上传文件持久化
```

---

## 2. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| 容器运行时 | Docker + Docker Compose | 行业标准 |
| Python 基础镜像 | python:3.11-slim | 体积小，够用 |
| PostgreSQL | postgres:16-alpine | Alpine 版体积小 |
| Redis | redis:7-alpine | Alpine 版体积小 |

---

## 3. 与现有代码的集成点

### 新增文件

```
（项目根目录）
├── Dockerfile                  # 构建 FastAPI + Celery 镜像
├── docker-compose.yml          # 生产部署配置
├── docker-compose.dev.yml      # 开发环境配置（可选）
├── .dockerignore               # 排除不需要的文件
└── docker/
    └── postgres/
        └── init.sql            # 数据库初始化脚本（可选）
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `.env` | 添加 Docker 环境的数据库/Redis 连接地址 |
| `app/database/connection.py` | 确保 DATABASE_URL 从环境变量读取 |

---

## 4. 分步实现方案

### Step 1：Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（PyMuPDF 等需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 默认启动命令（API 服务）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2：.dockerignore

```
# .dockerignore
.git
.env
__pycache__
*.pyc
.pytest_cache
data/
*.db
.vscode
.idea
Today_Plan/
evaluation/
docs/
```

### Step 3：docker-compose.yml

```yaml
# docker-compose.yml
version: "3.8"

services:
  # FastAPI 应用
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/job_copilot
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - upload_data:/app/data/uploads
      - chroma_data:/app/data/chroma
    restart: unless-stopped

  # Celery Worker
  worker:
    build: .
    command: celery -A celery_app worker --loglevel=info --concurrency=2
    env_file: .env
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/job_copilot
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - upload_data:/app/data/uploads
      - chroma_data:/app/data/chroma
    restart: unless-stopped

  # PostgreSQL
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: job_copilot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  pg_data:
  redis_data:
  upload_data:
  chroma_data:
```

### Step 4：开发环境配置（可选）

```yaml
# docker-compose.dev.yml
# 只启动依赖服务，应用本地运行
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: job_copilot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pg_data_dev:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pg_data_dev:
```

### Step 5：常用运维命令

```bash
# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f api
docker compose logs -f worker

# 停止服务
docker compose down

# 停止并删除数据
docker compose down -v

# 重新构建镜像
docker compose build --no-cache

# 只启动依赖（开发环境）
docker compose -f docker-compose.dev.yml up -d

# 进入容器调试
docker compose exec api bash

# 在容器中执行 Alembic 迁移
docker compose exec api alembic upgrade head
```

---

## 5. 测试方案

```bash
# 1. 构建并启动
docker compose up -d --build

# 2. 检查服务状态
docker compose ps

# 3. 验证 API 可用
curl http://localhost:8000/
# 应返回 "The server is running"

# 4. 验证数据库连接
docker compose exec api python -c "
from app.database.connection import engine
print(engine.url)
"

# 5. 验证 Redis 连接
docker compose exec redis redis-cli ping
# 应返回 PONG

# 6. 运行测试（在容器内）
docker compose exec api pytest tests/ -v

# 7. 清理
docker compose down -v
```

---

## 6. 面试要点

### 常见问题

**Q: 你的项目是怎么部署的？**
> Docker Compose 一键部署。定义了 4 个服务：FastAPI API 服务、Celery Worker、PostgreSQL、Redis。服务之间通过 Docker 内部网络通信。数据通过 Docker Volume 持久化，容器重启不丢数据。

**Q: 为什么用 Docker 而不是直接部署？**
> 环境一致性——避免"我机器上能跑"的问题。一条命令启动所有依赖（数据库、Redis），不需要面试官手动安装。Compose 还定义了 healthcheck，确保服务启动顺序正确（先启动 PG 和 Redis，再启动 API）。

**Q: 你在 Docker 部署中遇到过什么问题？**
> (1) 服务启动顺序——API 依赖数据库，需要 healthcheck + depends_on 控制；(2) 数据持久化——忘记挂载 Volume 导致容器重启数据丢失；(3) 网络——容器内用服务名（如 `postgres`）而非 `localhost` 连接。

### 能讲出的亮点

- **一键启动**：`docker compose up -d` 启动完整环境
- **健康检查**：PostgreSQL 和 Redis 的 healthcheck 确保启动顺序
- **数据持久化**：Volume 挂载，容器重启数据不丢
- **开发/生产分离**：dev 配置只启动依赖，prod 配置包含所有服务
