# job-copilot-v0

> **当前进度**：W1 数据层 + W2 知识库全部完成（含 `/kb/*` 4 个接口、上传幂等、近重复确认、Orchestrator RAG 注入、Alembic 迁移）。W3-D1 ~ W3-D3 已完成：已创建 `app/modules/interview/`、`app/modules/schedule/` 包结构，落地模拟面试基础 schema、Redis Session 管理、`app/skills/python_backend.md` Skill 定义，并实现 Skill 蓝图化出题引擎（`load_skill` / `build_skill_blueprint` / `generate_question` / `generate_follow_up`）；W3-D3 定向测试 12 passed，session + question 回归 31 passed, 1 skipped，下一步进入 W3-D4 评估引擎。

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
- 模拟面试的 Session 当前已基于 Redis 管理：会话数据包含 `config` / `status` / `messages` / `questions_asked` / `current_question_index`，默认 TTL 为 2 小时
- `app/skills/python_backend.md` 已作为首个面试方向 Skill 文件落地，用来约束考察范围、难度分布和参考知识库 collection
- 模拟面试出题引擎已支持从 Skill Markdown 构建蓝图，按目标难度 rubric、已问题目和已覆盖考点生成结构化题目，并提供追问生成函数
- 任务执行结果自动持久化到 SQLite（`task_records` 表），知识库上传记录写入 `knowledge_documents` 表；向量数据持久化到 `data/chroma/`
- FastAPI `lifespan` 事件当前仍会自动建表；为避免本地库结构落后，项目推荐在初始化与升级时显式执行 `alembic upgrade head`

---

## 技术栈与环境

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| 前端 | Streamlit |
| LLM | OpenAI SDK |
| ORM | SQLAlchemy 2.0 |
| 数据库（开发） | SQLite |
| 缓存 | Redis |
| 数据库迁移 | Alembic |
| 数据校验 | Pydantic v2 |
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
- `/docs` 中可见知识库相关接口：`/kb/upload`、`/kb/query`、`/kb/query/stream`、`/kb/collections`

**启动前端（可选）**

```bash
streamlit run ui/minimal_app.py
```

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
│   ├── main.py                          # FastAPI 入口 + lifespan 自动建表
│   ├── orchestrators/
│   │   └── job_copilot_orchestrator.py  # 任务主流程 + trace + 持久化
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── interview/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py               # W3-D1 模拟面试基础模型
│   │   │   ├── session_manager.py       # W3-D2 Redis Session 管理
│   │   │   └── question_engine.py       # W3-D3 Skill 蓝图解析、结构化出题和追问生成
│   │   ├── knowledge_base/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py          # W2-D1 向量库封装
│   │   │   ├── document_loader.py       # W2-D2 文档加载与分块
│   │   │   ├── near_duplicate.py        # W2-D6 近重复文本提取 / SimHash / 候选查找
│   │   │   └── rag_chain.py             # W2-D3 RAG 问答链
│   │   └── schedule/
│   │       └── __init__.py              # W3-D1 预留包结构，D6 补实现
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
│   │       └── resume.py                # W4 占位模型（id + created_at，字段待 W4 补）
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
├── ui/                                  # Streamlit 前端
├── schemas/                             # JSON Schema
├── Today_Plan/                          # 学习与开发计划
│   ├── Overall_Plan/                    # 6 周总计划
│   ├── Each_Week/                       # 每周概览表格
│   ├── W1/ W2/ W3/                      # 每日执行文件（D1.md ~ D7.md）
│   └── daily_progress.txt               # 当前进度指针
├── .env                                 # API Key + DATABASE_URL（不提交 Git）
└── README.md
```

**数据层说明**

- 每次 `POST /task` 请求的结果自动持久化到 `task_records` 表
- 开发环境：`lifespan` 自动建表；生产环境：使用 `alembic upgrade head`
- 数据库连接字符串通过 `DATABASE_URL` 环境变量配置，默认 `sqlite:///./job_copilot.db`

**安全提示**

- `.env` 已写入 `.gitignore`，确认不要手动 `git add .env`
- `job_copilot.db` 已写入 `.gitignore`
- API Key 不要硬编码进任何源文件
