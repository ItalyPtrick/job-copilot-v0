# W5 日计划概览（Doc 06：Docker 部署 + Streamlit 前端）

每天 3-4 小时。W5 将项目容器化（Docker Compose 一键启动 4 服务）并扩展 Streamlit 为多页面前端，实现面试可演示的完整形态。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 06 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | Docker 核心概念、镜像/容器/Compose 关系（Doc 06 §1 全部） | **Step 1**：编写 `Dockerfile`（python:3.11-slim + 系统依赖 + pip install + COPY） | `docker build -t job-copilot .` 成功；`docker run --rm job-copilot python -c "import app; print('OK')"` 输出 OK |
| **D2** | Docker Compose 多服务编排、healthcheck、depends_on（Doc 06 §1 "服务架构"） | **Step 2**：创建 `.dockerignore`；**Step 3**：编写 `docker-compose.yml`（api + worker + postgres + redis，含 healthcheck 和 volume） | `docker compose config` 无报错；`docker compose up -d` 后 postgres/redis healthy、api/worker running |
| **D3** | PostgreSQL 连接适配、SQLAlchemy 多数据库支持（Doc 06 §3 "修改现有文件"） | 修改 `connection.py` 支持 PostgreSQL URL + 安装 `psycopg2-binary` + Alembic 在容器内执行迁移 | `docker compose exec api alembic upgrade head` 成功；`docker compose exec api python -c "from app.database.connection import engine; print(engine.url)"` 显示 postgresql:// |
| **D4** | 开发/生产环境分离策略（Doc 06 §4 Step 4） | **Step 4**：创建 `docker-compose.dev.yml`（仅 PG + Redis）；**Step 5**：整理运维命令到 `Makefile` 或 README | `docker compose -f docker-compose.dev.yml up -d` 启动 PG + Redis；本地 `uvicorn` 连接容器内 PG 成功 |
| **D5** | Docker 测试策略（Doc 06 §5） | 容器内跑全量测试 + API 可达性验证 + 数据持久化验证（down → up 数据不丢） | `docker compose exec api pytest tests/ -v` 全绿；`curl http://localhost:8000/` 返回成功；Volume 持久化验证通过 |
| **D6** | Streamlit 多页面架构（pages/ 目录约定） | 扩展 `ui/` 为多页面：主页 + RAG 问答页 + 模拟面试页 + 简历分析页 | `streamlit run ui/app.py` 启动成功；3 个功能页面可访问且能调用后端 API |
| **D7** | Doc 06 §6 面试要点复习 | 端到端验证：`docker compose up -d` → curl 全部端点 → Streamlit 演示 → `docker compose down`；代码清理 + 设计决策记录 | 完整演示流程跑通；`pytest tests/ -v` 全绿；能讲出 Doc 06 §6 的 3 个问题 + 4 个亮点 |
