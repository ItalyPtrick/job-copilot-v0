# 部署需求文档

> 目标读者：执行此文档的 AI Agent。
> 性质：需求与约定，不是执行手册。实现方式由你决定。

---

## 1. 目标

将 job-copilot-v0 完整部署到一台阿里云 ECS 服务器上，包括：
- 后端 4 个容器（API、Worker、PostgreSQL、Redis）
- 前端静态文件（React 构建产物，Nginx 托管）
- Nginx 反向代理（前端静态 + 后端 API）

部署完成后，面试官通过 `http://公网IP` 即可访问完整的前端演示。

---

## 2. 服务器环境

| 配置项 | 值 |
|---|---|
| 云厂商 | 阿里云 |
| 地域 | 华南1（深圳） |
| 实例规格 | ecs.e-c1m1.large，2 vCPU，2 GiB |
| 操作系统 | Ubuntu 26.04 64 位（安全加固） |
| 系统盘 | ESSD Entry 40 GiB |
| 公网带宽 | 5 Mbps（按使用流量，220GB/月免费） |
| 登录用户 | `ecs-user`（非 root，sudo 提权） |
| 公网 IP | 有（具体地址在阿里云控制台查看） |

### 2.1 安全组要求

部署前必须确认以下入方向规则已开放：

| 协议 | 端口 | 来源 | 用途 |
|---|---|---|---|
| TCP | 22 | 0.0.0.0/0 | SSH 远程登录 |
| TCP | 80 | 0.0.0.0/0 | HTTP 访问（前端 + 后端 API） |
| TCP | 443 | 0.0.0.0/0 | HTTPS（当前未启用，预留） |
| ICMP | - | 0.0.0.0/0 | ping 测试 |

RDP(3389) 不需要，Ubuntu 用 SSH 即可。如果安全组中存在 RDP 规则，建议删除以减少攻击面。

### 2.2 资源预算

| 组件 | 预估内存 | 预估磁盘 |
|---|---|---|
| Ubuntu 系统 | 300~500 MB | ~5 GB |
| Docker Engine | 50~100 MB | ~500 MB |
| Node.js (构建用) | 运行时 ~100 MB | ~200 MB |
| Nginx | ~10 MB | ~10 MB |
| PostgreSQL 容器 | 100~200 MB | ~300 MB（镜像）+ 数据 |
| Redis 容器 | 50~100 MB | ~50 MB（镜像）+ 数据 |
| FastAPI 容器 | 100~200 MB | ~500 MB（镜像） |
| Celery Worker 容器 | 100~200 MB | 共用 FastAPI 镜像 |
| 前端构建产物 | 0 | ~5 MB |
| **合计** | **~1.3 GB / 2 GB** | **~7 GB / 40 GB** |

内存余量约 700MB，磁盘余量约 33GB。对 demo 项目充足。

---

## 3. 软件依赖

服务器需要安装以下软件：

| 软件 | 用途 | 安装方式 |
|---|---|---|
| Docker Engine | 运行后端容器 | apt 安装 |
| Docker Compose | 编排多容器 | apt 安装（插件模式） |
| Git | 拉取代码 | apt 安装 |
| Node.js + npm | 构建前端 | apt 或 NodeSource 安装（LTS 版本） |
| Nginx | 托管前端 + 反代后端 | apt 安装 |

**注意：** 使用 Docker Engine（Linux 原生），不要安装 Docker Desktop（那是桌面环境用的）。

### 3.1 交付物

Agent 执行本文档后应产出：

| 文件 | 位置 | 说明 |
|------|------|------|
| 部署操作手册 | `ui/docs/DEPLOY_GUIDE.md` | 分步操作指南，用户 SSH 到服务器后照着执行 |
| Nginx 配置文件 | `deploy/nginx/job-copilot.conf` | 可直接复制到服务器 `/etc/nginx/sites-available/` |
| .env 模板 | `.env.example`（如不存在则创建） | 列出所有需要填写的变量，值留空或用占位符 |

不需要产出部署脚本。后续如果需要自动化再补充。

---

## 4. 部署流程概要

### 4.1 首次部署

**项目路径：** `/home/ecs-user/job-copilot-v0`（以下所有路径基于此）

```
1. SSH 登录服务器（ecs-user）
2. 安装软件依赖（Docker、Git、Node.js LTS、Nginx）
3. 将 ecs-user 加入 docker 组（免 sudo 执行 docker 命令）
4. 配置 2GB swap 文件（防止 npm build 时 OOM，2GB 内存机器必须配）
5. git clone 项目仓库到 /home/ecs-user/job-copilot-v0
6. 在项目根目录创建 .env 文件（从 .env.example 复制，手动填入 API Key）
7. docker compose up -d --build（启动后端 4 个容器）
8. 等待 PostgreSQL 就绪（docker compose exec api python -c "import time; time.sleep(5)"，或用 pg_isready 探测）
9. docker compose exec api alembic upgrade head（数据库迁移）
10. cd ui && npm install && npm run build（构建前端）
11. 配置 Nginx（复制 deploy/nginx/job-copilot.conf 到 /etc/nginx/sites-available/，创建软链到 sites-enabled）
12. sudo nginx -t && sudo systemctl reload nginx
13. 验证：浏览器访问 http://公网IP
```

**关于 swap：** 2 vCPU / 2 GiB 机器上，`npm install` + `npm run build` 峰值内存可能超过可用余量。配置 2GB swap 可防止 OOM killer 杀进程。swap 配置是一次性操作，后续更新不需要重复。

### 4.2 日常更新

```
1. cd /home/ecs-user/job-copilot-v0
2. git pull（拉取最新代码）
3. docker compose up -d --build（重建并重启后端容器）
4. docker compose exec api alembic upgrade head（如有 schema 变更）
5. cd ui && npm install && npm run build（重新构建前端）
6. 无需重启 Nginx（静态文件更新后自动生效）
```

**注意：** 步骤 4 即使没有新迁移也可安全执行（alembic 会检测到已是最新版本并跳过）。养成每次更新都跑一次的习惯，避免遗漏。

---

## 5. Nginx 配置需求

Nginx 承担两个职责：

### 5.1 前端静态文件托管

- 根目录指向 `ui/dist/`（Vite 构建产物）
- `try_files` 回退到 `index.html`（SPA 路由支持）
- 静态资源设置缓存头（JS/CSS 缓存，HTML 不缓存）

### 5.2 后端 API 反向代理

- 路径：`/api/` 前缀的所有请求
- 转发目标：`http://127.0.0.1:8000`
- Strip prefix：`/api/task` → `/task`
- 超时设置：部分 API 调用 LLM 耗时较长，proxy_read_timeout 建议 120s

**SSE 流式端点特殊处理：**

知识库查询 `/api/kb/query/stream` 使用 SSE，Nginx 默认会缓冲响应导致流式输出变成一次性吐出。需要对该路径（或所有 `/api/` 路径）加以下配置：

```nginx
proxy_buffering off;
proxy_cache off;
proxy_set_header X-Accel-Buffering no;
```

建议直接对整个 `/api/` location 关闭缓冲（后端 API 响应体都不大，关闭缓冲无性能影响）。

### 5.3 端口分配

| 端口 | 服务 | 对外暴露 |
|---|---|---|
| 80 | Nginx | ✅ 是（公网访问入口） |
| 8000 | FastAPI（后端 API） | ❌ 否（仅 Nginx 内部反代访问） |
| 5432 | PostgreSQL | ❌ 否（仅容器间通信） |
| 6379 | Redis | ❌ 否（仅容器间通信） |

后端 API 不直接暴露到公网，所有请求必须经过 Nginx。

---

## 6. .env 文件

服务器上需要在项目根目录创建 `.env` 文件。**这是手动步骤**——Agent 只负责确保 `.env.example` 模板存在且变量列表完整，用户自行复制并填入实际值。

```
# 从模板创建：
cp .env.example .env
# 然后用编辑器填入实际 API Key
nano .env
```

模板内容（`.env.example`）：
```
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
OPENAI_EMBEDDING_API_KEY=
OPENAI_EMBEDDING_BASE_URL=
OPENAI_EMBEDDING_MODEL=
```

注意：
- `DATABASE_URL` 和 `REDIS_URL` 由 `docker-compose.yml` 中的环境变量覆盖，`.env` 中的本地值不影响容器内连接
- `.env` 文件不要提交到 Git（已在 `.gitignore` 中）
- API Key 不要硬编码到任何源文件

---

## 7. Docker Compose 配置要求

### 7.1 Agent 职责

项目已有 `docker-compose.yml`（生产）和 `docker-compose.dev.yml`（开发），服务器部署使用前者。

**Agent 需要检查 `docker-compose.yml` 并确保满足以下要求，不满足则修改：**

| 检查项 | 要求 |
|--------|------|
| restart 策略 | 所有 4 个容器设置 `restart: unless-stopped` |
| 端口映射 | api 容器映射 `127.0.0.1:8000:8000`（仅本地，不暴露公网） |
| PG/Redis 端口 | 不映射到宿主机（仅容器间通信） |
| Volume 持久化 | PG 数据、Redis 数据、上传文件、简历文件、向量库均有 named volume |
| 健康检查 | PostgreSQL 容器有 healthcheck，api 容器 depends_on 使用 condition: service_healthy |

### 7.2 服务架构

```
┌─────────────────────────────────────────┐
│            Docker Network                │
│                                          │
│  ┌──────────┐  ┌──────────┐             │
│  │  api:8000 │  │  worker  │             │
│  └────┬─────┘  └────┬─────┘             │
│       │              │                    │
│  ┌────▼─────┐  ┌────▼─────┐             │
│  │ postgres  │  │  redis   │             │
│  │  :5432    │  │  :6379   │             │
│  └──────────┘  └──────────┘             │
└─────────────────────────────────────────┘
```

### 7.3 Volume 持久化

5 个 Volume 分别持久化：PG 数据、Redis 数据、上传文件、简历文件、向量库。`docker compose down -v` 会清除所有卷数据，普通 `down` 不丢数据。

### 7.4 健康检查

PostgreSQL 容器应配置 healthcheck（`pg_isready`），api 和 worker 容器通过 `depends_on` + `condition: service_healthy` 等待 PG 就绪后再启动。这样可以避免 §4.1 中手动等待的问题。

如果现有 docker-compose.yml 没有 healthcheck 配置，Agent 需要补充。

---

## 8. 前端构建

前端代码在 `ui/` 目录（React + Vite 项目），服务器上需要构建：

```
cd ui
npm install
npm run build
```

构建产物在 `ui/dist/`，由 Nginx 托管。

**Node.js 只在构建时需要**，运行时不需要。但为了日常更新方便，建议保留在服务器上不卸载。

---

## 9. 部署验证

部署完成后，通过以下方式验证：

| 验证项 | 方法 | 预期结果 |
|---|---|---|
| Nginx 运行 | `sudo systemctl status nginx` | active (running) |
| 后端容器运行 | `docker compose ps` | 4 个容器均为 Up 状态 |
| 健康检查 | `curl http://localhost:8000/health` | 返回数据库 + Redis 状态 |
| 前端可访问 | 浏览器 `http://公网IP` | Landing Page 正常显示 |
| API 可达 | 浏览器 `http://公网IP/api/docs` | FastAPI Swagger 文档 |
| 功能验证 | 前端页面操作各功能 | JD 分析、模拟面试等功能可用 |

---

## 10. ICP 备案（独立流程，不影响部署）

当前通过公网 IP 直接访问，无需备案。如果后续需要绑定域名（如 `ihtw.online`），需完成 ICP 备案：

**所需材料：**
- 身份证正反面照片
- 手机号（接收验证码）
- 域名证书（从域名注册商后台下载）
- 人脸核验（阿里云 APP 或支付宝扫码）

**流程：**
1. 阿里云控制台 → ICP 备案 → 填写信息 → 上传材料
2. 阿里云初审（1~2 个工作日，会电话确认）
3. 工信部审核（5~15 个工作日）
4. 通过后在域名 DNS 中添加 A 记录指向 ECS 公网 IP
5. Nginx 配置中添加 server_name 指向域名

**注意：** 备案通过后需在 Nginx 中配置域名，并建议启用 HTTPS（Let's Encrypt 免费证书）。

---

## 11. 不需要做的事

- 不需要 CI/CD 流水线（手动 git pull + build）
- 不需要 Docker 镜像仓库（本地 build）
- 不需要 HTTPS（IP 访问阶段，备案后再启用）
- 不需要监控告警系统（demo 项目）
- 不需要日志聚合（`docker compose logs` 够用）
- 不需要自动备份（demo 数据不重要）
- 不需要 Kubernetes 或容器编排（单机 Docker Compose）
- 不需要 CDN（单服务器，访问量低）
