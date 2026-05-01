# job-copilot-v0 六周实施计划

基于项目 8 份文档（Doc 00-07），从 Doc 01（数据层）开始，每天 3-4 小时，每周 7 天。

**起点**：`app/` 下已有可用骨架（FastAPI + LLM + Tool Calling + Trace + 3 个基础任务 + Streamlit Demo），从 Doc 01 开始新增功能。

> Doc 05（语音面试）为加分项，6 周核心不含。

| 周次 | 对应文档 | 核心任务 | 验收标准（怎么算"做完了"） |
|:---:|:---:|---|---|
| **W1** | Doc 01 | **数据层：SQLite + SQLAlchemy + Alembic + Redis** | ① `pytest tests/test_database.py` 全绿 ② `alembic upgrade head` / `downgrade base` / `upgrade head` 三连成功 ③ `/task` 执行后在 SQLite 中能查到 `task_records` 记录 ④ Redis `set_session` / `get_session` 单元测试通过 |
| **W2** | Doc 02 | **RAG 知识库：文档上传→分块→向量化→检索问答→SSE 流式** | ① `POST /kb/upload` 上传 txt/pdf 返回 chunks_count > 0 ② `POST /kb/query` 返回带 sources 的 answer ③ `POST /kb/query/stream` SSE 流式返回 ④ `pytest tests/test_rag_chain.py` 全绿 ⑤ Orchestrator 可注入 RetrieverContext |
| **W3** | Doc 03 | **模拟面试：Session 管理 + Skill 出题 + 多轮追问 + 评估引擎** | ① `POST /interview/start` 返回 session_id + 第一题 ② `POST /interview/answer` 连续回答 5 题不崩溃 ③ `POST /interview/evaluate` 返回结构化评分报告（overall_score + items） ④ Redis 中 session 有 TTL ⑤ 面试安排：`parse_invite` 能解析腾讯会议/飞书格式 |
| **W4** | Doc 04 | **简历分析：多格式解析 + Celery 异步 + PDF 报告导出** | ① `POST /resume/upload` 立即返回 resume_id + "analyzing" ② Celery Worker 后台完成分析，数据库状态更新为 "completed" ③ `GET /resume/{id}/report` 返回结构化分析结果 ④ `GET /resume/{id}/export` 下载 PDF 报告 ⑤ 内容哈希去重：相同简历不重复调用 LLM |
| **W5** | Doc 06 + UI | **Docker 部署 + Streamlit 前端完善** | ① `docker compose up -d` 一键启动 4 个服务（api + worker + postgres + redis） ② `curl http://localhost:8000/` 在容器内返回成功 ③ Streamlit 多页面：RAG 问答页、模拟面试页、简历分析页 ④ 数据库切换到 PostgreSQL（改连接字符串即可） |
| **W6** | Doc 07 + 收尾 | **集成测试 + Bug 修复 + 面试准备** | ① 完整演示流程跑通：上传简历→分析→RAG 问答→模拟面试 ② README 更新（架构图 + 截图 + 快速启动） ③ 能用 2 分钟讲清项目架构 ④ 准备好 3 个技术难点 + 解决方案 ⑤ 简历项目描述定稿 |

---

> W1-W4 日计划见 `Today_Plan/Each_Week/`，W5-W6 待 W4 完成后展开。
