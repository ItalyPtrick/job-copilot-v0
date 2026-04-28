# W3 日计划概览（Doc 03：模拟面试）

每天 3-4 小时。W3 从“固定出题 + 固定追问”调整为更接近真人面试官的链路：Skill 蓝图化、难度 rubric、自适应追问 planner、主问题与追问聚合评估。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 03 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | 多轮对话管理、结构化输出（Doc 03 §1 前 2 节） | **Step 1**：创建 `app/modules/interview/` 目录结构 + `schemas.py`（InterviewStatus / InterviewConfig / InterviewQuestion / InterviewEvalItem / InterviewReport） | `python -c "from app.modules.interview.schemas import InterviewConfig, InterviewReport; print('OK')"` 输出 OK |
| **D2** | Skill 驱动出题、评估引擎架构（Doc 03 §1 后 2 节） | **Step 2**：创建 `session_manager.py`（create_session / get_session / update_session，基于 Redis）；创建 Skill 定义文件 `app/skills/python_backend.md` | `python -c "from app.modules.interview.session_manager import create_session, get_session; print('OK')"` 输出 OK；Redis session CRUD 单元测试通过 |
| **D3** | Skill 蓝图化、难度 rubric、追问函数职责边界 | **Step 3**：重构 `question_engine.py`（load_skill + build_skill_blueprint + generate_question + generate_follow_up） | `pytest tests/test_question_engine.py -v` 全绿；`generate_question` 使用蓝图摘要、难度 rubric 和应用层去重 |
| **D4** | 主问题与追问的评估边界；按面试轮次而非裸问答评分 | **Step 4**：创建 `evaluation.py`（_extract_interview_turns + evaluate_batch + generate_report + evaluate_interview） | `python -c "from app.modules.interview.evaluation import evaluate_interview; print('OK')"` 输出 OK；主问题 + 追问能聚合为同一 turn |
| **D5** | FastAPI 路由设计 + 自适应追问 planner | **Step 5**：创建 `router.py`（start / answer / evaluate）；实现 planner 决策 follow_up / next_question / complete；修改 `main.py` 注册 `/interview` | `/interview/start` 返回 session_id + 第一题；`/interview/answer` 能返回追问、下一题或 completed |
| **D6** | 面试安排模块 + W3 关键路径测试 | **Step 6**：创建 `app/modules/schedule/`（invite_parser.py + router.py）；补 question_engine / planner / evaluation / invite_parser 测试 | planner、evaluation、invite_parser 相关测试全绿 |
| **D7** | 面试复习（Skill 蓝图、难度 rubric、自适应追问、主追问评估、双引擎解析） | 端到端验证：start → 多轮 answer（含追问/下一题）→ evaluate；清理代码与文档 | 完整面试流程跑通；`pytest tests/ -v` 全绿；能讲出新版 Doc 03 的 6 个问题和 6 个亮点 |
