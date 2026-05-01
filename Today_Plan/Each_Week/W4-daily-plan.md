# W4 日计划概览（Doc 04：简历智能分析）

每天 3-4 小时。W4 实现完整简历分析流水线：多格式解析 → LLM 结构化分析 → Celery 异步任务 → PDF 报告导出。Celery 在 Windows 上使用 `--pool=solo` 模式。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 04 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | 文档解析原理、策略模式分派（Doc 04 §1 第 1 节） | **Step 1**：创建 `app/modules/resume/` 目录 + `parser.py`（PDF/DOCX/TXT 统一解析入口） | `pytest tests/test_resume_parser.py -v` 全绿 |
| **D2** | 结构化 Prompt + 内容哈希去重（Doc 04 §1 后 2 节） | **Step 2**：扩展 `ResumeRecord` 模型 + 创建 `analyzer.py`（LLM 分析器） + Alembic 迁移 | `alembic upgrade head` 成功；`python -c "from app.modules.resume.analyzer import analyze_resume; print('OK')"` |
| **D3** | Celery 架构、Task 重试机制（Doc 04 §1 异步任务） | **Step 3**：创建 `celery_app.py` + `tasks.py` + `service.py`；Celery Worker 启动验证 | `celery -A celery_app worker --pool=solo --loglevel=info` 成功启动 |
| **D4** | ReportLab 基础、中文字体注册（Doc 04 §4 Step 4） | **Step 4**：配置中文字体 + 创建 `report_export.py`（PDF 报告生成） | `pytest tests/test_report_export.py -v` 全绿；PDF 可打开 |
| **D5** | FastAPI 文件上传 + FileResponse（Doc 04 §4 Step 5） | **Step 5**：创建 `router.py`（upload/status/report/export）+ 注册到 main.py | curl 上传→查状态→拿报告→导出 PDF 全流程通 |
| **D6** | Celery 测试策略（task.apply 同步执行） | 测试完善：parser/analyzer/tasks/api/report_export 5 组测试 + 去重验证 | `pytest tests/test_resume_*.py tests/test_report_export.py -v` 全绿 |
| **D7** | Doc 04 §6 面试要点复习 | 端到端验证 + 代码清理 + 设计决策记录 + `pytest tests/ -v` 全量 | 全量测试通过；能讲清完整数据流 + 4 个面试问题 |
