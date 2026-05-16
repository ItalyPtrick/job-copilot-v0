# job-copilot-v0

> **当前进度**：W1~W4 全部完成。W5 Docker 部署进行中（D1~D4 完成：Dockerfile + Compose + PostgreSQL 适配 + dev compose/运维命令）。详见 `Today_Plan/daily_progress.txt`。

---

## 项目做了什么

job-copilot-v0 是一个求职 AI 助手的后端骨架。它通过统一的任务入口接收请求，调用 LLM 完成三类求职任务，并在响应中附带完整的 trace 执行轨迹。

**支持的任务类型：**

| task_type | 功能 |
|---|---|
| `jd_analyze` | 解析职位描述，提炼硬性要求、核心技能、加分项 |
| `resume_optimize` | 针对目标 JD 优化简历条目的表达 |
| `self_intro_generate` | 根据简历内容和目标岗位生成自我介绍 |

**设计特点：**

- 统一任务入口：`POST /task`，由 orchestrator 负责分发
- 每次响应携带 `trace` 字段，记录各执行节点的状态与备注，便于调试
- RAG 能力通过独立的 `/kb/*` 路由提供：非流式返回 `answer + sources`，流式版本输出 SSE 文本事件
- `retriever_context` 字段已通过 `_build_retriever_context` 实现按需注入（payload 含 `use_rag` + `rag_collection` + `rag_question` 时触发）
- 已接入知识库接口：`/kb/upload`、`/kb/query`、`/kb/query/stream`、`/kb/collections`
- 知识库上传具备两层保护：完全重复按 `file_hash` 幂等短路（`reused: true`），高度相似文档返回 `confirmation_required` 并等待 `confirm_upload=true` 重试
- 模拟面试的 Session 当前已基于 Redis 管理：会话数据包含 `config` / `status` / `messages` / `questions_asked` / `current_question_index` / `current_main_question` / `current_follow_up_count` / `covered_topics` / `recent_performance` / `evaluation_report`，默认 TTL 为 2 小时
- 模拟面试已提供 `/interview/start`、`/interview/answer`、`/interview/evaluate` 三个 API 端点；`/interview/answer` 通过自适应追问 planner 决定追问/下一题/完成，并根据回答表现动态调节难度
- 日程模块已提供 `POST /schedule/parse-invite`，把面试邀请文本解析为公司、岗位、开始/结束时间、会议链接、面试官和备注
- 简历模块已提供 5 个 API 端点：`/resume/upload`（上传 + 触发异步分析）、`/resume/{id}/status`（轮询状态）、`/resume/{id}/report`（获取结构化结果）、`/resume/{id}/export`（下载 PDF 报告）、`/resume/list`（历史记录分页）；分析任务解析文本后按 content_hash 去重（W2-D5 模式），通过 Celery 异步执行
- `app/skills/python_backend.md` 已作为首个面试方向 Skill 文件落地，用来约束考察范围、难度分布和参考知识库 collection
- 模拟面试出题引擎已支持从 Skill Markdown 构建蓝图，按目标难度 rubric、已问题目和已覆盖考点生成结构化题目，并提供追问生成函数
- 模拟面试评估引擎已实现按主问题轮次评分（区分主问题、追问和回答），通过 `_extract_interview_turns` 归组、`evaluate_batch` 分批 LLM 评估、`generate_report` 汇总报告；消息结构通过 `InterviewMessageMetadata` 契约统一
- 任务执行结果自动持久化到关系数据库（本地默认 SQLite，Compose 使用 PostgreSQL），知识库上传记录写入 `knowledge_documents` 表；向量数据持久化到 `data/chroma/`
- SQLite 本地开发可由 `lifespan` 自动建表；PostgreSQL 环境使用 Alembic 迁移（`alembic upgrade head`）

---

## 技术栈与环境

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| LLM | OpenAI SDK |
| ORM | SQLAlchemy 2.0 |
| 数据库（开发） | SQLite |
| 数据库（部署） | PostgreSQL 16 |
| 缓存 + Broker | Redis 7 |
| 数据库迁移 | Alembic |
| 数据校验 | Pydantic v2 |
| 异步任务 | Celery + Redis |
| PDF 生成 | ReportLab |
| 容器化 | Docker + Docker Compose |
| 测试 | pytest |
| Python | 3.11（conda 环境 `job-copilot-v0`） |

---

## 安装步骤

**1. 克隆项目**

```bash
git clone <repo_url>
cd job-copilot-v0
```

**2. 创建并激活 conda 环境**

```bash
conda create -n job-copilot-v0 python=3.11
conda activate job-copilot-v0
```

**3. 安装依赖**

```bash
pip install -r requirements.txt
```

**4. 初始化数据库**

```bash
alembic upgrade head
```

执行后项目根目录会生成 `job_copilot.db`（SQLite 数据库文件）。

**5. 配置环境变量**

在项目根目录创建 `.env` 文件（不要提交到 Git）：

```
# chat
OPENAI_API_KEY=your_chat_api_key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# embeddings
OPENAI_EMBEDDING_API_KEY=your_embedding_api_key
OPENAI_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_EMBEDDING_MODEL=text-embedding-v4

DATABASE_URL=sqlite:///./job_copilot.db
REDIS_URL=redis://localhost:6379/0
```

说明：当前项目支持聊天模型和向量模型分开配置。若使用阿里云百炼兼容 embeddings 接口，`app/modules/knowledge_base/vector_store.py` 中已将 `check_embedding_ctx_length` 设为 `False`，以适配字符串输入。

---

## 配置完怎么用

**启动后端**

```bash
conda activate job-copilot-v0
cd <project-root>
uvicorn app.main:app --reload
```

启动成功后：
- 根路径 `http://127.0.0.1:8000/` 返回 `"The server is running"`
- 交互式文档：`http://127.0.0.1:8000/docs`
- `/docs` 中可见知识库接口：`/kb/upload`、`/kb/query`、`/kb/query/stream`、`/kb/collections`
- `/docs` 中可见模拟面试接口：`/interview/start`、`/interview/answer`、`/interview/evaluate`
- `/docs` 中可见日程接口：`/schedule/parse-invite`
- `/docs` 中可见简历接口：`/resume/upload`、`/resume/{id}/status`、`/resume/{id}/report`、`/resume/{id}/export`、`/resume/list`

**Docker 部署（W5-D2，可选）**

当前 Compose 启动 4 个服务：API、Worker、PostgreSQL、Redis。应用使用 PostgreSQL，数据持久化在 `pg_data` 卷。

> 运行前确保项目根目录有 `.env` 文件，包含 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 等必需变量（参考上方环境变量表）。Compose 通过 `env_file` 注入容器。`DATABASE_URL` 和 `REDIS_URL` 由 Compose 环境变量覆盖，`.env` 中的本地值不影响容器内连接。

> **数据卷说明**：`pg_data`、`redis_data`、`upload_data`、`resume_data`、`chroma_data` 分别持久化 PostgreSQL、Redis、知识库上传文件、简历文件和向量库。`down -v` 会清除所有卷数据；普通 `down` 不丢数据。

> **端口说明**：API 暴露 `8000`，PostgreSQL 暴露 `5432`；Redis 仅限容器间通信，未暴露到宿主机。

> **Worker 说明**：容器内使用 Linux 默认 prefork pool；本地 Windows 开发需改用 `--pool=solo`（见"启动方式"段落）。

```bash
# 构建并启动全部服务
docker compose up -d --build

# 首次运行：执行数据库迁移
docker compose exec api alembic upgrade head

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f api
docker compose logs -f worker

# 验证 Redis
docker compose exec redis redis-cli ping

# 停止服务
docker compose down

# 停止并清除卷数据
docker compose down -v
```

**Docker 开发模式（W5-D4）**

开发时只需启动 PostgreSQL + Redis，API 和 Worker 在本地运行，代码改动即时生效、无需 rebuild。

> `.env` 中的 `DATABASE_URL` 和 `REDIS_URL` 需指向 `localhost`（默认已是）：

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/job_copilot
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
```

```bash
# 启动基础设施
docker compose -f docker-compose.dev.yml up -d

# 本地启动 API（热重载）
uvicorn app.main:app --reload

# 本地启动 Worker（Windows 用 --pool=solo）
celery -A celery_app worker --loglevel=info --pool=solo

# 停止基础设施
docker compose -f docker-compose.dev.yml down

# 停止并清除数据
docker compose -f docker-compose.dev.yml down -v
```

**运维命令速查**

| 场景 | 命令 |
|---|---|
| 构建镜像 | `docker compose build` |
| 启动全部服务 | `docker compose up -d` |
| 仅启动基础设施 | `docker compose -f docker-compose.dev.yml up -d` |
| 查看运行状态 | `docker compose ps` |
| 查看 API 日志 | `docker compose logs -f api` |
| 查看 Worker 日志 | `docker compose logs -f worker` |
| 进入 API 容器 | `docker compose exec api bash` |
| 容器内跑测试 | `docker compose exec api pytest tests/ -v` |
| 容器内迁移 | `docker compose exec api alembic upgrade head` |
| 容器内 psql | `docker compose exec postgres psql -U postgres -d job_copilot` |
| 容器内 redis-cli | `docker compose exec redis redis-cli` |
| 停止服务 | `docker compose down` |
| 停止并清除数据 | `docker compose down -v` |

---

### 请求示例

所有任务统一通过 `POST /task` 提交。

**请求体格式**

```json
{
  "task_type": "<任务类型>",
  "payload": { ... }
}
```

**响应格式**

```json
{
  "status": "success" | "error",
  "task_type": "<原始任务类型>",
  "result": { ... } | null,
  "error": { "error_type": "...", "error_message": "..." } | null,
  "retriever_context": null,
  "trace": [
    { "node_name": "...", "status": "...", "remark": "..." }
  ]
}
```

HTTP 状态码：成功 `200`，失败 `400`。

**示例 1：JD 分析**

```json
{
  "task_type": "jd_analyze",
  "payload": {
    "jd_text": "Python开发实习生\n岗位职责：\n1. 协助搭建大模型应用原型，参与Prompt设计\n2. 使用Python开发自动化流程\n任职要求：\n1. 熟悉Python基础语法\n2. 了解Git版本控制",
    "target_role": "Python开发实习生"
  }
}
```

**示例 2：简历优化**

```json
{
  "task_type": "resume_optimize",
  "payload": {
    "resume_item": "负责公司后端开发工作，完成了一些功能模块，和团队一起推进项目。",
    "target_jd_keywords": ["FastAPI", "Python", "RESTful API"],
    "role_summary": "Python后端开发工程师"
  }
}
```

**示例 3：自我介绍生成**

```json
{
  "task_type": "self_intro_generate",
  "payload": {
    "tone": "formal",
    "resume_item": "使用 FastAPI 独立开发求职助手后端，支持结构化输出与 trace 轨迹记录。",
    "target_jd_keywords": ["FastAPI", "Python", "RESTful API"],
    "role_summary": "Python后端开发工程师"
  }
}
```

> `tone` 可选值：`formal`（正式）/ `conversational`（对话式）

**模拟面试接口**

模拟面试通过独立的 `/interview/*` 路由提供，不走 `/task` 统一入口。

1. 开始面试：`POST /interview/start`，返回 `session_id` + 第一道题
2. 提交回答：`POST /interview/answer`，planner 自动决定追问/下一题/完成
3. 获取评估：`POST /interview/evaluate`（面试完成后调用），返回评分报告

```json
// POST /interview/start
{ "skill": "python_backend", "total_questions": 5, "follow_up_count": 1 }

// POST /interview/answer
{ "session_id": "<从 start 获取>", "answer": "候选人回答内容" }

// POST /interview/evaluate
{ "session_id": "<从 start 获取>" }
```

**日程接口**

`POST /schedule/parse-invite` 解析面试邀请文本，返回 `company`、`position`、`start_time`、`end_time`、`meeting_link`、`interviewer`、`notes`。

```json
{ "text": "示例科技 Python 后端面试，时间 2026-05-10 14:00-16:00，链接 https://meeting.tencent.com/dm/abc。" }
```

**简历分析接口**

简历分析通过 `/resume/*` 路由提供，采用异步处理：上传后立即返回 `resume_id`，后台 Celery Worker 执行解析→去重→LLM 分析，前端轮询状态获取结果。

功能：
- 支持 PDF / DOCX / TXT 三种格式
- 内容哈希去重：相同简历 + 相同目标岗位直接复用已有分析结果
- 分析结果可导出为 PDF 报告（中文排版）

端点：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/resume/upload` | 上传简历，触发异步分析（返回 `resume_id`） |
| GET | `/resume/{id}/status` | 查询分析状态（pending / analyzing / completed / failed） |
| GET | `/resume/{id}/report` | 获取结构化分析报告（需 completed） |
| GET | `/resume/{id}/export` | 下载 PDF 报告（需 completed） |
| GET | `/resume/list` | 历史记录分页列表 |

启动方式（需额外启动 Celery Worker）：

```bash
# 终端 1：FastAPI
uvicorn app.main:app --reload

# 终端 2：Celery Worker
celery -A celery_app worker --loglevel=info --pool=solo
```

---

## 其他注意事项

**新增任务类型**

1. 在 `app/orchestrators/job_copilot_orchestrator.py` 的 `VALID_TASK_TYPES` 中添加新类型名称
2. 在 `app/prompts/` 下创建对应的 `<task_type>.md` prompt 文件

**运行测试**

```bash
pytest tests/ -v
```

面试出题引擎定向测试：`pytest tests/test_question_engine.py -v`
面试评估引擎定向测试：`pytest tests/test_interview_evaluation.py -v`
面试 Planner 定向测试：`pytest tests/test_interview_planner.py -v`
面试路由定向测试：`pytest tests/test_interview_router.py -v`
简历模块定向测试：`pytest tests/test_resume_parser.py tests/test_resume_analyzer.py tests/test_resume_tasks.py tests/test_resume_api.py tests/test_report_export.py tests/test_resume_e2e.py -v --basetemp=.pytest_tmp`

**知识库接口最小手工验收**

- `/kb/upload`：以“响应 + `knowledge_documents` 记录 + `data/uploads/` 落盘文件”三点交叉验证成功，不只看 Swagger UI 单一展示；同文件二次上传应返回 `reused: true` 且不重复 embedding；高度相似文档第一次应返回 `status: confirmation_required`，携带 `confirm_upload=true` 重试后再成功入库；并发冲突仍返回 409
- `/kb/query`：返回 `answer + sources`
- `/kb/query/stream`：返回 `event: message` 与 `event: done`
- `/kb/collections`：能读到当前 Chroma collection 与 count

**验证数据库迁移**

```bash
alembic upgrade head && alembic downgrade base && alembic upgrade head
```

**目录结构**

```
job-copilot-v0/
├── app/
│   ├── main.py                          # FastAPI 入口 + lifespan（SQLite 自动建表，PG 由 Alembic 管理）
│   ├── orchestrators/
│   │   └── job_copilot_orchestrator.py  # 任务主流程 + trace + 持久化
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── interview/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py               # W3-D1 模拟面试基础模型
│   │   │   ├── session_manager.py       # W3-D2 Redis Session 管理
│   │   │   ├── question_engine.py       # W3-D3 Skill 蓝图解析、结构化出题和追问生成
│   │   │   ├── evaluation.py            # W3-D4 评估引擎：轮次提取、分批评估、汇总报告
│   │   │   ├── interview_planner.py     # W3-D5 自适应追问决策（纯函数）
│   │   │   └── router.py                # W3-D5 面试路由：/interview/start、/interview/answer、/interview/evaluate
│   │   ├── knowledge_base/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py          # W2-D1 向量库封装
│   │   │   ├── document_loader.py       # W2-D2 文档加载与分块
│   │   │   ├── near_duplicate.py        # W2-D6 近重复文本提取 / SimHash / 候选查找
│   │   │   └── rag_chain.py             # W2-D3 RAG 问答链
│   │   ├── resume/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py                # W4-D1 简历解析：PDF/DOCX/TXT 策略分派
│   │   │   ├── analyzer.py              # W4-D2 LLM 结构化分析
│   │   │   ├── tasks.py                 # W4-D3 Celery 异步任务（analyze_resume_task）
│   │   │   ├── service.py               # W4-D3 CRUD 服务层（create/get/update）
│   │   │   ├── report_export.py         # W4-D4 PDF 报告生成（ReportLab + 中文字体）
│   │   │   └── router.py                # W4-D5 FastAPI 路由（upload/status/report/export/list）
│   │   └── schedule/
│   │       ├── __init__.py
│   │       ├── invite_parser.py         # W3-D6 面试邀请解析：规则引擎 + AI 补充 + 合并策略
│   │       └── router.py                # W3-D6 日程路由：/schedule/parse-invite
│   ├── cache/
│   │   └── redis_client.py              # Redis 客户端封装
│   ├── database/
│   │   ├── __init__.py                  # 导出 engine, SessionLocal, Base, get_db
│   │   ├── connection.py                # 数据库连接配置
│   │   ├── crud/
│   │   │   ├── __init__.py
│   │   │   └── task_crud.py             # 任务记录查询封装
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── task_record.py           # 任务执行历史模型
│   │       ├── knowledge.py             # W2 RAG 知识库模型（含幂等唯一约束）
│   │       ├── interview.py             # W3 占位模型（id + created_at，字段待 W3 补）
│   │       └── resume.py                # W4 简历分析模型（filename/content_hash/status/target_role/analysis_result/raw_text）
│   ├── skills/
│   │   └── python_backend.md            # W3-D2 面试方向 Skill 定义
│   ├── services/
│   │   ├── llm_service.py               # LLM 调用封装
│   │   └── prompt_service.py            # 从 prompts/ 加载 Markdown
│   ├── prompts/
│   │   ├── jd_analyze.md
│   │   ├── resume_optimize.md
│   │   └── self_intro_generate.md
│   ├── tools/                            # Tool Calling 工具注册
│   └── types/
│       ├── task_result.py               # TaskResult / ErrorDetail
│       ├── trace_event.py               # TraceEvent / TraceNodeNames / TraceStatus
│       └── retriever_context.py         # RetrieverContext（RAG 预留）
├── alembic/                              # 数据库迁移脚本
│   ├── env.py
│   └── versions/
├── alembic.ini                           # Alembic 配置
├── data/                                # 运行期数据目录（如 Chroma 持久化、上传文件）
├── job_copilot.db                        # SQLite 数据库（.gitignore）
├── docs/                                # 学习资料、开发记录与设计决策文档
├── evaluation/                          # 验收测试文档
├── tests/                               # pytest
├── scripts/                             # 辅助脚本（工具调试等）
├── ui/                                  # 前端（待重构）
├── schemas/                             # JSON Schema
├── Today_Plan/                          # 学习与开发计划
│   ├── Overall_Plan/                    # 6 周总计划
│   ├── Each_Week/                       # 每周概览表格
│   ├── W1/ W2/ W3/                      # 每日执行文件（D1.md ~ D7.md）
│   └── daily_progress.txt               # 当前进度指针
├── Dockerfile                           # W5 容器镜像构建
├── docker-compose.yml                   # W5 生产编排（api/worker/postgres/redis）
├── docker-compose.dev.yml               # W5 开发编排（仅 postgres/redis）
├── .dockerignore                        # 构建上下文排除规则
├── .env                                 # API Key + DATABASE_URL（不提交 Git）
└── README.md
```

**数据层说明**

- 每次 `POST /task` 请求的结果自动持久化到 `task_records` 表
- SQLite 本地开发可由 lifespan 自动建表；PostgreSQL 环境使用 Alembic 迁移
- 数据库连接字符串通过 `DATABASE_URL` 环境变量配置，默认 `sqlite:///./job_copilot.db`

**安全提示**

- `.env` 已写入 `.gitignore`，确认不要手动 `git add .env`
- `job_copilot.db` 已写入 `.gitignore`
- API Key 不要硬编码进任何源文件
