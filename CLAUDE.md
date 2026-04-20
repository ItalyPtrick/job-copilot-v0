# job-copilot-v0

基于 Python + FastAPI + LLM 的求职 AI 助手后端。

当前阶段：W1 数据层已完成，W2 正在推进知识库接入；项目总览与常规使用说明以 `README.md` 为准。

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
- 当前仓库实际接入的 embedding 模型是 `text-embedding-v4`。

---

## Daily Plan Mentor

消息包含 `/daily-plan-mentor` 或“开始/继续今天的学习”时，读取 `.claude/skills/daily_plan_mentor.md` 执行。

---

## 自动提醒规则

当一天的计划全部完成后，主动提醒用户：

1. "是否要帮你更新 `Today_Plan/daily_progress.txt`？"
2. "是否检查 `README.md` 和 `CLAUDE.md` 需不需要更新？"

---

## 文档维护提醒

- 中文 Markdown 文件避免用终端追加、重定向或脚本直接拼接内容。
- 优先使用编辑器直接修改，并确保保存为 UTF-8 编码。

## 注释风格提醒

- AI 生成代码时，中文注释采用“精炼学习笔记”风格：只写在函数逻辑、关键方法调用、隐藏约束、容易看不懂的实现细节处。
- 不逐行注释，不写翻译变量名式注释；注释要帮助理解“为什么这样写”或“这里的关键点是什么”。
