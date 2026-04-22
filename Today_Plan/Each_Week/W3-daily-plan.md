# W3 日计划概览（Doc 03：模拟面试）

每天 3-4 小时。学习内容对应 Doc 03 的"概念学习"章节，编码任务对应"分步实现方案"的 Step。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 03 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | 多轮对话管理、结构化输出（Doc 03 §1 前 2 节："多轮对话管理" + "结构化输出"） | **Step 1**：创建 `app/modules/interview/` 目录结构 + `schemas.py`（InterviewStatus / InterviewConfig / InterviewQuestion / InterviewEvalItem / InterviewReport） | `python -c "from app.modules.interview.schemas import InterviewConfig, InterviewReport; print('OK')"` 输出 OK |
| **D2** | Skill 驱动出题、评估引擎架构（Doc 03 §1 后 2 节："Skill 驱动出题" + "评估引擎"） | **Step 2**：创建 `session_manager.py`（create_session / get_session / update_session，基于 Redis）；创建 Skill 定义文件 `app/skills/python_backend.md` | `python -c "from app.modules.interview.session_manager import create_session, get_session; print('OK')"` 输出 OK；Redis session CRUD 单元测试通过 |
| **D3** | 无新概念，专注编码 | **Step 3**：创建 `question_engine.py`（generate_question + generate_follow_up，调用 `call_llm` + Skill 文件生成面试题） | `python -c "from app.modules.interview.question_engine import generate_question, generate_follow_up; print('OK')"` 输出 OK |
| **D4** | 无新概念，专注编码 | **Step 4**：创建 `evaluation.py`（evaluate_batch 分批评估 + generate_report 汇总报告 + evaluate_interview 完整流程 + _extract_qa_pairs 提取问答对） | `python -c "from app.modules.interview.evaluation import evaluate_interview; print('OK')"` 输出 OK |
| **D5** | FastAPI 路由设计（POST /interview/start、/answer、/evaluate） | **Step 5**：创建 `router.py`（3 个面试路由）；修改 `main.py` 注册 `/interview` 路由；扩展 `redis_client.py` 添加面试 session 专用操作 | `curl -X POST http://localhost:8000/interview/start -H "Content-Type: application/json" -d '{"skill":"python_backend"}'` 返回 session_id + 第一题 |
| **D6** | 无新概念，专注面试安排 + 测试 | **Step 6**：创建 `app/modules/schedule/` 模块（invite_parser.py 双引擎解析）；编写 `tests/test_interview.py`（session / evaluation / invite_parser 测试） | `pytest tests/test_interview.py -v` 全绿 |
| **D7** | 面试复习（Doc 03 §6 全部 4 个问题 + 亮点） | 端到端验证：完整面试流程（start → 5 轮 answer → evaluate）；清理代码 | 完整面试流程跑通；能回答 Doc 03 §6 的 4 个面试问题；能讲出 5 个亮点 |
