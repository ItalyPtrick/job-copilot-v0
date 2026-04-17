# 数据层基础：数据库 + 缓存

本文档是所有功能模块的前置依赖。当前项目是纯内存运行，重启后所有数据丢失。本模块为项目引入持久化存储（SQLite/PostgreSQL）和缓存层（Redis）。

---

## 1. 概念学习

### 为什么需要数据库？

当前 `job-copilot-v0` 的问题：
- 所有任务结果用完即丢，没有历史记录
- 模拟面试的会话无法持久化
- 简历分析结果无法存储和查询
- 知识库的文档元数据没有地方放

interview-guide 用 PostgreSQL + JPA 管理所有业务数据。我们先用 SQLite（零配置），后续平滑切换到 PostgreSQL。

### ORM 是什么？为什么用 SQLAlchemy？

**ORM（Object-Relational Mapping）** 把数据库表映射为 Python 类，用 Python 代码操作数据库，而不是写原始 SQL。

```python
# 不用 ORM（原始 SQL）
cursor.execute("INSERT INTO resumes (filename, status) VALUES (?, ?)", (name, status))

# 用 SQLAlchemy ORM
resume = Resume(filename=name, status=status)
session.add(resume)
session.commit()
```

**为什么选 SQLAlchemy 2.0：**
- Python ORM 事实标准，社区最大
- 2.0 版本支持原生 async（`AsyncSession`）
- 与 FastAPI 集成方案成熟
- Alembic 数据库迁移工具是其官方配套

### 数据库迁移是什么？

数据库的 schema（表结构）会随着项目迭代而变化。Alembic 是 SQLAlchemy 的迁移工具，相当于数据库的"版本控制"：

```bash
# 生成迁移脚本（检测模型变更）
alembic revision --autogenerate -m "add resume table"

# 执行迁移（应用到数据库）
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

对标 interview-guide 的 JPA `ddl-auto: update`，但 Alembic 更精确可控。

### 为什么需要 Redis？

Redis 在本项目中承担两个角色：

| 角色 | 用途 | 对标 interview-guide |
|---|---|---|
| **会话缓存** | 模拟面试的多轮对话上下文（替代内存 dict） | Redis 替代 ConcurrentHashMap |
| **任务队列 Broker** | Celery 的消息中间件（简历分析、文档向量化） | Redis Stream |

**为什么不直接用内存 dict？**
- 服务重启后会话丢失
- 多 worker 进程之间无法共享内存
- Redis 支持 TTL 自动过期，内存 dict 不会自动清理

---

## 2. 技术选型

| 组件 | 选择 | 版本 | 备注 |
|---|---|---|---|
| ORM | SQLAlchemy | 2.0+ | 支持 async，与 FastAPI 深度集成 |
| 数据库（初期） | SQLite | 内置 | 零配置，单文件存储 |
| 数据库（进阶） | PostgreSQL | 14+ | 生产级，支持 pgvector |
| 迁移工具 | Alembic | 1.13+ | SQLAlchemy 官方配套 |
| 缓存 | Redis | 7+ | 会话缓存 + Celery broker |
| Python Redis 客户端 | redis-py | 5+ | 支持 async |

### 渐进式策略

```
Phase 1（本周）：SQLite + SQLAlchemy → 数据可持久化
Phase 2（接 RAG 模块时）：加 Redis → 会话缓存
Phase 3（接简历分析时）：Redis 作为 Celery broker → 异步任务
Phase 4（部署时）：切换到 PostgreSQL → 生产环境
```

---

## 3. 与现有代码的集成点

### 需要新增的文件

```
app/
├── database/
│   ├── __init__.py          # 导出 engine, SessionLocal, Base
│   ├── connection.py        # 数据库连接配置
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task_record.py   # 任务执行历史
│   │   ├── resume.py        # 简历记录
│   │   ├── interview.py     # 面试 session
│   │   └── knowledge.py     # 知识库文档
│   └── crud/
│       ├── __init__.py
│       └── task_crud.py     # 任务 CRUD 操作
├── cache/
│   ├── __init__.py
│   └── redis_client.py      # Redis 连接与操作封装
alembic/                      # 迁移目录（项目根目录）
├── versions/
├── env.py
└── alembic.ini
```

### 需要修改的现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 添加启动时数据库初始化、关闭时清理连接 |
| `app/orchestrators/job_copilot_orchestrator.py` | `execute_task` 完成后将结果写入数据库 |
| `requirements.txt` | 添加 `sqlalchemy`, `alembic`, `redis`, `aiosqlite` |
| `.env` | 添加 `DATABASE_URL`, `REDIS_URL` |

---

## 4. 分步实现方案

### Step 1：安装依赖

```bash
pip install sqlalchemy[asyncio] alembic aiosqlite redis
```

添加到 `requirements.txt`：
```
sqlalchemy[asyncio]>=2.0
alembic>=1.13
aiosqlite>=0.20
redis>=5.0
```

### Step 2：数据库连接配置

`app/database/connection.py` 核心逻辑：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./job_copilot.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

# FastAPI 依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Step 3：定义数据模型

以 `TaskRecord`（任务执行历史）为例：

```python
from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from app.database.connection import Base

class TaskRecord(Base):
    __tablename__ = "task_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSON)
    status = Column(String(20), nullable=False)  # success / error
    result = Column(JSON)
    error_type = Column(String(100))
    error_message = Column(String(500))
    trace = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
```

### Step 4：初始化 Alembic

```bash
alembic init alembic
```

修改 `alembic/env.py`，让它自动检测 SQLAlchemy 模型：

```python
from app.database.connection import Base
from app.database.models import *  # 导入所有模型

target_metadata = Base.metadata
```

修改 `alembic.ini`：
```ini
sqlalchemy.url = sqlite:///./job_copilot.db
```

生成并执行第一次迁移：
```bash
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

### Step 5：在 Orchestrator 中保存任务记录

修改 `app/orchestrators/job_copilot_orchestrator.py`：

```python
from app.database.connection import SessionLocal
from app.database.models.task_record import TaskRecord

def execute_task(task_type: str, payload: dict) -> TaskResult:
    # ... 现有逻辑不变 ...

    # 在返回前保存记录
    result = TaskResult.from_success(...)
    _save_task_record(result, payload)
    return result

def _save_task_record(result: TaskResult, payload: dict):
    db = SessionLocal()
    try:
        record = TaskRecord(
            task_type=result.task_type,
            payload=payload,
            status=result.status,
            result=result.result if result.status == "success" else None,
            error_type=result.error.error_type if result.error else None,
            error_message=result.error.error_message if result.error else None,
            trace=[t.model_dump(mode="json") for t in (result.trace or [])],
        )
        db.add(record)
        db.commit()
    finally:
        db.close()
```

### Step 6：Redis 连接封装

`app/cache/redis_client.py`：

```python
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# 会话缓存操作
def set_session(session_id: str, data: dict, ttl: int = 3600):
    """缓存面试会话，默认 1 小时过期"""
    redis_client.setex(session_id, ttl, json.dumps(data, ensure_ascii=False))

def get_session(session_id: str) -> dict | None:
    """获取面试会话"""
    raw = redis_client.get(session_id)
    return json.loads(raw) if raw else None

def delete_session(session_id: str):
    """删除面试会话"""
    redis_client.delete(session_id)
```

### Step 7：FastAPI 生命周期事件

修改 `app/main.py`：

```python
from contextlib import asynccontextmanager
from app.database.connection import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表（开发环境用，生产环境用 Alembic）
    Base.metadata.create_all(bind=engine)
    yield
    # 关闭时清理（如需要）

app = FastAPI(lifespan=lifespan)
```

---

## 5. 测试方案

### 单元测试

```python
# tests/test_database.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database.models.task_record import TaskRecord

@pytest.fixture
def db_session():
    """使用内存 SQLite 做测试，每个测试用例独立"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_task_record(db_session):
    record = TaskRecord(
        task_type="jd_analyze",
        payload={"jd_text": "test"},
        status="success",
        result={"key": "value"},
    )
    db_session.add(record)
    db_session.commit()

    saved = db_session.query(TaskRecord).first()
    assert saved.task_type == "jd_analyze"
    assert saved.status == "success"
```

### Redis 测试

```python
# tests/test_redis.py
import pytest
from unittest.mock import patch, MagicMock

def test_set_and_get_session():
    """Mock Redis 测试会话缓存"""
    with patch("app.cache.redis_client.redis_client") as mock_redis:
        mock_redis.get.return_value = '{"question": "test"}'
        from app.cache.redis_client import get_session
        result = get_session("session_123")
        assert result == {"question": "test"}
```

### 验证命令

```bash
# 运行数据库相关测试
pytest tests/test_database.py -v

# 验证 Alembic 迁移
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

---

## 6. 面试要点

### 常见问题

**Q: 你为什么选 SQLAlchemy 而不是 Django ORM 或 Tortoise ORM？**
> SQLAlchemy 2.0 是 Python ORM 事实标准，社区最大，与 FastAPI 集成方案最成熟。Django ORM 绑定 Django 框架，Tortoise ORM 社区较小。SQLAlchemy 2.0 原生支持 async，性能上没有劣势。

**Q: 为什么先用 SQLite 后切 PostgreSQL？**
> 渐进式架构演进。SQLite 零配置，适合开发期快速迭代。SQLAlchemy 的抽象层让切换数据库只需改连接字符串。这也是工程实践中常见的策略——先跑通，再优化。

**Q: Redis 在你的项目中具体做了什么？**
> 两件事：(1) 模拟面试的多轮会话缓存，设置 TTL 自动过期，避免内存泄漏；(2) 作为 Celery 的 broker，异步处理简历分析和文档向量化这类耗时任务。

**Q: 你用 Alembic 做数据库迁移，能说说它和 JPA 的 ddl-auto 有什么区别吗？**
> JPA 的 `ddl-auto: update` 是自动检测实体变更并修改表结构，方便但不可控——可能出现意外的 ALTER TABLE。Alembic 生成显式的迁移脚本，每次变更都有代码记录、可审查、可回滚，更适合生产环境。

### 能讲出的亮点

- **渐进式架构**：SQLite → PostgreSQL，不过度设计
- **依赖注入**：FastAPI 的 `Depends(get_db)` 管理数据库生命周期
- **迁移管理**：Alembic 版本化数据库 schema，而非依赖自动同步
- **缓存策略**：Redis TTL 自动过期，避免内存泄漏
