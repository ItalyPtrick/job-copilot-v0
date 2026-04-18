# job-copilot-v0

基于 Python + FastAPI + LLM 的求职 AI 助手后端。参考 [interview-guide](https://github.com/Snailclimb/interview-guide) 功能设计，用 Python 生态重新实现。

当前阶段：**W1 数据层进行中**（D1-D6 已完成，D7 待开始）。后端骨架已验收（W4 收口）。

---

## 当前进度

| 能力 | 状态 | 关键文件 |
|---|---|---|
| 统一任务入口 `POST /task` | ✅ | `app/main.py` |
| 三类任务（jd_analyze / resume_optimize / self_intro_generate） | ✅ | `app/orchestrators/job_copilot_orchestrator.py` |
| LLM 调用 + Tool Calling | ✅ | `app/services/llm_service.py`, `app/tools/` |
| Trace 执行轨迹（四节点） | ✅ | `app/types/trace_event.py` |
| 数据持久化（SQLite + SQLAlchemy + Alembic） | ✅ | `app/database/`, `alembic/` |
| RAG 字段预留（`retriever_context`） | ✅ 预留 | `app/types/retriever_context.py` |
| Streamlit 极简前端 | ✅ Demo | `ui/minimal_app.py` |

验收文档：`evaluation/week4/`

---

## 下一步计划

详见 `docs/00-roadmap.md`。

| 阶段 | 内容 | 对应文档 |
|---|---|---|
| Phase 1 剩余 | Redis session 缓存 + RAG 知识库（向量检索 + SSE 流式） | `01-database-and-persistence.md`, `02-rag-knowledge-base.md` |
| Phase 2 | 模拟面试（出题 + 追问 + 评估）+ 简历智能分析 | `03-mock-interview.md`, `04-resume-analysis.md` |
| Phase 3 | Docker Compose 部署 + 面试展示准备 | `06-deployment.md`, `07-interview-showcase.md` |
| 加分项 | 语音面试（WebSocket + Whisper + edge-tts） | `05-voice-interview.md` |

---

## 环境与命令

conda 环境：`job-copilot-v0`，Python 3.11

```bash
# 启动后端（必须从项目根目录）
conda activate job-copilot-v0
uvicorn app.main:app --reload

# 启动前端
streamlit run ui/minimal_app.py

# 运行测试
pytest tests/ -v

# 数据库迁移
alembic upgrade head
alembic downgrade base && alembic upgrade head   # 验证迁移可逆
```

环境变量（`.env`，已 gitignore）：

| 变量 | 用途 |
|---|---|
| `OPENAI_API_KEY` | LLM API 密钥 |
| `OPENAI_BASE_URL` | LLM API 地址（可选，用于代理/兼容端点） |
| `OPENAI_MODEL` | 模型名称 |
| `DATABASE_URL` | 数据库连接串，默认 `sqlite:///./job_copilot.db` |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6379/0` |

---

## Daily Plan Mentor

消息包含 `/daily-plan-mentor` 或"开始/继续今天的学习"时，读取 `.claude/skills/daily_plan_mentor.md` 执行。

---

## 自动提醒规则

当一天的计划全部完成后，主动提醒用户：

1. "是否要帮你更新 `Today_Plan/daily_progress.txt`？"
2. "是否检查 `README.md` 和 `CLAUDE.md` 需不需要更新？"
