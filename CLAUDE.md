# job-copilot-v0

基于 Python + FastAPI + LLM 的求职 AI 助手后端。

当前阶段：W1~W5 全部完成。项目总览与常规使用说明以 `README.md` 为准，设计决策记录在 `docs/design-decisions.md`。

---

## 环境约束

conda 环境：`job-copilot-v0`，Python 3.11。
激活conda命令（powershell）：conda activate job-copilot-v0
完整Python路径（conda 未初始化时）：C:\Users\admin\.conda\envs\job-copilot-v0\python.exe

环境变量（`.env`，已 gitignore）：

| 变量                        | 用途                                            |
| --------------------------- | ----------------------------------------------- |
| `OPENAI_API_KEY`            | 聊天模型 API 密钥                               |
| `OPENAI_BASE_URL`           | 聊天模型 API 地址（可选，用于代理/兼容端点）    |
| `OPENAI_MODEL`              | 聊天模型名称                                    |
| `OPENAI_EMBEDDING_API_KEY`  | 向量模型 API 密钥                               |
| `OPENAI_EMBEDDING_BASE_URL` | 向量模型 API 地址（兼容 OpenAI embeddings）     |
| `OPENAI_EMBEDDING_MODEL`    | 向量模型名称                                    |
| `DATABASE_URL`              | 数据库连接串，默认 `sqlite:///./job_copilot.db` |
| `REDIS_URL`                 | Redis 连接串，默认 `redis://localhost:6379/0`   |
| `CELERY_BROKER_URL`         | Celery broker，默认 `redis://localhost:6379/1`  |
| `POSTGRES_PASSWORD`         | Docker Compose 中 PG 密码，默认 `postgres`      |

补充说明：
- 聊天模型读取 `OPENAI_*`，embedding 读取 `OPENAI_EMBEDDING_*`，两者可走不同端点。
- 百炼兼容接口需设置 `check_embedding_ctx_length=False` + `chunk_size=10`，已在代码中配置，新增 embedding 调用时保持一致。
- RAG 问答链在 `app/modules/knowledge_base/rag_chain.py`，使用 LCEL 组合；流式版本仅输出文本，`sources` 由非流式返回。

---

## Daily Plan Mentor

仅当用户显式调用 `/daily-plan-mentor` 时，使用 `.claude/skills/daily-plan-mentor/SKILL.md` 执行今日计划导师流程。

“开始今天的学习”“继续今天计划”“按今天计划推进”等自然语言请求不自动触发该 Skill。

---

## 自动提醒规则

当一天的计划全部完成后，主动提醒用户：

1. "是否要帮你更新 `Today_Plan/daily_progress.txt`？"
2. "是否检查 `CLAUDE.md` 需不需要更新？仅当用户明确要求时再检查 `README.md`。"
3. "是否检查今天形成的设计决策是否已同步到 `docs/design-decisions.md`？"

---

## design-decisions.md 文风

- 每条决策包含：问题 → 解法 → 为什么这样做（而非为什么不那样做）
- 有真实踩坑经历的条目，在"解法"前加一句"踩坑：最初尝试 X，发现 Y"
- 涉及性能/成本权衡时嵌入具体数字（token 数、延迟、费用）
- 子决策用缩进层级挂在父条目下，不另起顶级标题

---

## 文档维护提醒

- 中文 Markdown 文件避免用终端追加、重定向或脚本直接拼接内容。
- 优先使用编辑器直接修改，并确保保存为 UTF-8 编码。

## 常用命令

```bash
uvicorn app.main:app --reload
pytest tests/ -v --basetemp=.pytest_tmp   # 面试相关测试需要 Redis 运行
alembic upgrade head
```

## 安全边界

- 不读取或输出 `.env` 中的密钥值。
- 不删除 `data/` 目录（chroma 索引 + 上传文件）。
- 不手动修改 alembic 版本链；需要迁移时用 `alembic revision --autogenerate`。
- 不在无明确任务要求时改动跨模块契约：API 响应结构、Redis key 前缀/结构、`llm_service` 对外接口。如必须改，先说明影响面。

## 代码导航

- 入口：`app/main.py`，任务编排：`app/orchestrators/job_copilot_orchestrator.py`
- 面试模块：`app/modules/interview/`（schemas / session_manager / question_engine / evaluation / interview_planner / router）
- 日程模块：`app/modules/schedule/`（invite_parser / router）
- 知识库模块：`app/modules/knowledge_base/`（router / rag_chain / document_loader）
- 简历模块：`app/modules/resume/`（parser / analyzer / tasks / service / report_export / router）
- LLM 封装：`app/services/llm_service.py`，数据库：`app/database/connection.py`
- 测试文件对应 `tests/test_<模块名>.py`，面试 Skill 配置在 `app/skills/`

## 注释风格提醒

- AI 生成代码时，中文注释采用“精炼学习笔记”风格：只写在函数逻辑、关键方法调用、隐藏约束、容易看不懂的实现细节处。
- review git diff 中的 Python 文件时，要额外检查一遍这些文件是否补了足够的中文注释，以及这些中文注释是否符合上述风格。
- 注释主要服务于理解文件结构、实现思路，以及关键代码实现行的原理。
- 可以贴着实现写短提示，但不逐行注释，也不写翻译变量名式注释。
