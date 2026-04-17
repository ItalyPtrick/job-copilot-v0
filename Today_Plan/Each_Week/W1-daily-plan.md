# W1 日计划概览（Doc 01：数据层）

每天 3-4 小时。学习内容对应 Doc 01 的"概念学习"章节，编码任务对应"分步实现方案"的 Step。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 01 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | ORM 概念、SQLAlchemy 2.0 基础（Doc 01 §1 "ORM 是什么"）；理解 `DeclarativeBase`、`Column` 类型映射 | **Step 1**：安装 `sqlalchemy[asyncio]`, `alembic`, `aiosqlite`, `redis` 并更新 `requirements.txt`；**Step 2**：创建 `app/database/connection.py`（engine + SessionLocal + Base + `get_db` 依赖注入） | `requirements.txt` 更新；`app/database/__init__.py` + `connection.py` 可导入不报错 |
| **D2** | SQLAlchemy Column 类型（String/Integer/JSON/DateTime）；理解 index 和 nullable 的作用 | **Step 3**：创建 `app/database/models/task_record.py`（TaskRecord 模型，含 task_type/payload/status/result/trace/created_at）；创建 `app/database/models/__init__.py` 统一导出 | 能 `from app.database.models.task_record import TaskRecord` 成功；`python -c "from app.database.connection import Base; print(Base.metadata.tables)"` 能看到 task_records 表 |
| **D3** | Alembic 迁移概念（Doc 01 §1 "数据库迁移"）；理解 `revision --autogenerate` 和 `upgrade/downgrade` 的关系 | **Step 4**：`alembic init alembic` → 修改 `alembic/env.py`（导入 Base + models）→ 修改 `alembic.ini`（SQLite URL）→ `alembic revision --autogenerate -m "initial tables"` → `alembic upgrade head` | `job_copilot.db` 文件生成；`alembic upgrade head` / `downgrade base` / `upgrade head` 三连成功；用 `sqlite3 job_copilot.db ".tables"` 能看到 task_records |
| **D4** | FastAPI 依赖注入（`Depends`）和生命周期事件（`lifespan`） | **Step 5**：修改 `app/orchestrators/job_copilot_orchestrator.py`，在 `execute_task` 完成后调用 `_save_task_record` 保存到数据库；**Step 7**：修改 `app/main.py`，添加 `lifespan` 事件（启动时 `create_all`） | 调用 `POST /task` 后，`sqlite3 job_copilot.db "SELECT * FROM task_records"` 能查到记录 |
| **D5** | 数据库单元测试模式（内存 SQLite fixture）；pytest fixture 的 `yield` 用法 | 编写 `tests/test_database.py`：① `db_session` fixture（内存 SQLite） ② `test_create_task_record` ③ `test_query_by_task_type` ④ `test_task_record_json_fields`（验证 JSON 字段存取） | `pytest tests/test_database.py -v` 全绿（≥3 个测试用例） |
| **D6** | Redis 概念（Doc 01 §1 "为什么需要 Redis"）；理解 TTL、key-value、JSON 序列化；本地安装/启动 Redis | **Step 6**：创建 `app/cache/__init__.py` + `redis_client.py`（`set_session` / `get_session` / `delete_session`）；编写 `tests/test_redis.py`（Mock Redis 测试 + 真实连接 smoke test） | `pytest tests/test_redis.py -v` 全绿；`redis-cli ping` 返回 PONG |
| **D7** | 复习本周所学：ORM→迁移→CRUD→缓存 完整链路；思考面试怎么讲数据层设计 | ① 创建 `app/database/crud/task_crud.py`（封装查询：`get_tasks_by_type`, `get_recent_tasks`） ② 端到端验证：启动服务→调用 /task→检查数据库记录→检查 Redis 可连接 ③ 补充 `knowledge.py`、`interview.py`、`resume.py` 三个模型骨架（为 W2-W4 预留） | CRUD 封装可用；3 个预留模型文件存在；能完整回答 Doc 01 §6 的 4 个面试问题 |
