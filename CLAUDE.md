# job-copilot-v0

基于 Python + FastAPI + LLM 的求职 AI 助手后端。

当前阶段：W1 数据层 + W2 知识库全部完成。upload 接口实现两阶段 commit（`uploading` → `completed`），`(collection_name, file_hash)` 唯一约束兜底幂等判重和并发竞争，重复上传返回 `reused: true` 并跳过 embedding；同 collection 命中近重复时返回 HTTP 200 + `status=confirmation_required`，前端带 `confirm_upload=true` 重试后继续上传，并在 `completed` 时写入 `similarity_fingerprint`。Orchestrator 已通过 `_build_retriever_context` 实现 RAG 上下文按需注入。W3-D1 ~ W3-D3 已完成：已创建 `app/modules/interview/`、`app/modules/schedule/` 包结构，落地模拟面试基础 schema、Redis Session 管理、Skill 定义和 Skill 蓝图化出题引擎；W3-D3 定向测试 12 passed，session + question 回归 31 passed, 1 skipped；下一步进入 W3-D4 评估引擎 `evaluation.py`。项目总览与常规使用说明以 `README.md` 为准。

---

## 环境约束

conda 环境：`job-copilot-v0`，Python 3.11。

环境变量（`.env`，已 gitignore）：

| 变量 | 用途 |
|---|---|
| `OPENAI_API_KEY` | 聊天模型 API 密钥 |
| `OPENAI_BASE_URL` | 聊天模型 API 地址（可选，用于代理/兼容端点） |
| `OPENAI_MODEL` | 聊天模型名称 |
| `OPENAI_EMBEDDING_API_KEY` | 向量模型 API 密钥 |
| `OPENAI_EMBEDDING_BASE_URL` | 向量模型 API 地址（兼容 OpenAI embeddings） |
| `OPENAI_EMBEDDING_MODEL` | 向量模型名称 |
| `DATABASE_URL` | 数据库连接串，默认 `sqlite:///./job_copilot.db` |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6379/0` |

补充说明：
- 聊天模型读取 `OPENAI_*`，embedding 读取 `OPENAI_EMBEDDING_*`。
- 聊天与 embedding 可以分别走不同的 OpenAI 兼容端点。
- 若 embeddings 使用阿里云百炼兼容接口，`OpenAIEmbeddings` 需设置 `check_embedding_ctx_length=False`，避免 LangChain 默认预切分导致兼容接口入参不匹配。
- 百炼 embedding API 单批上限 10 条，`OpenAIEmbeddings` 需同时设置 `chunk_size=10`，避免批量写入时超限报 400。
- 当前仓库实际接入的 embedding 模型是 `text-embedding-v4`。
- RAG 问答链已落到 `app/modules/knowledge_base/rag_chain.py`，使用 LCEL 组合 `prompt | llm | parser`；流式版本当前仅输出文本，`sources` 由非流式返回。

---

## Daily Plan Mentor

消息包含 `/daily-plan-mentor` 或“开始/继续今天的学习”时，读取 `.claude/skills/daily_plan_mentor.md` 执行。

---

## 自动提醒规则

当一天的计划全部完成后，主动提醒用户：

1. "是否要帮你更新 `Today_Plan/daily_progress.txt`？"
2. "是否检查 `README.md` 和 `CLAUDE.md` 需不需要更新？"
3. "是否检查今天形成的设计决策是否已同步到 `docs/design-decisions.md`？"

---

## 文档维护提醒

- 中文 Markdown 文件避免用终端追加、重定向或脚本直接拼接内容。
- 优先使用编辑器直接修改，并确保保存为 UTF-8 编码。

## 常用命令

```bash
uvicorn app.main:app --reload
pytest tests/ -v
alembic upgrade head
```

## 关键入口

- FastAPI 入口：`app/main.py`
- 任务 Orchestrator：`app/orchestrators/job_copilot_orchestrator.py`（`POST /task` 主流程 + trace + 持久化）
- 模拟面试 Schema：`app/modules/interview/schemas.py`（W3-D1 基础数据模型，`InterviewQuestion` 已包含 `difficulty_reason` / `assessment_focus`）
- 面试 Session 管理：`app/modules/interview/session_manager.py`（W3-D2 已完成的 Redis Session CRUD）
- 面试 Skill 定义：`app/skills/python_backend.md`（W3-D2 首个面试方向配置）
- 面试出题引擎：`app/modules/interview/question_engine.py`（W3-D3 Skill 蓝图解析、结构化出题、追问生成）
- 知识库路由：`app/modules/knowledge_base/router.py`
- RAG 问答链：`app/modules/knowledge_base/rag_chain.py`
- 数据库连接：`app/database/connection.py`（导出 engine / SessionLocal / Base / get_db）
- LLM 封装：`app/services/llm_service.py`（`call_llm` / `call_llm_with_tools` / `call_llm_with_tool_result`）

## 测试定位

- 知识库 API：`tests/test_kb_api.py`
- RAG 问答链：`tests/test_rag_chain.py`
- 面试 Session 管理：`tests/test_interview_session_manager.py`
- 面试出题引擎：`tests/test_question_engine.py`
- 数据库与 Redis：`tests/test_database.py`、`tests/test_redis.py`

## 注释风格提醒

- AI 生成代码时，中文注释采用“精炼学习笔记”风格：只写在函数逻辑、关键方法调用、隐藏约束、容易看不懂的实现细节处。
- review git diff 中的 Python 文件时，要额外检查一遍这些文件是否补了足够的中文注释，以及这些中文注释是否符合上述风格。
- 注释主要服务于理解文件结构、实现思路，以及关键代码实现行的原理。
- 可以贴着实现写短提示，但不逐行注释，也不写翻译变量名式注释。
