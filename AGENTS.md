# job-copilot-v0 项目规范

## 项目简介

求职 AI 助手。FastAPI 后端接收任务请求，调用 LLM 完成三类任务：JD 分析、简历优化、自我介绍生成，响应附带 trace 执行轨迹。

## 环境启动

```bash
conda activate job-copilot-v0
# 从项目根目录启动，否则 app 模块找不到
cd C:/MyPython/job-copilot-v0
uvicorn app.main:app --reload
```

## 技术栈

- 后端: FastAPI + Uvicorn
- 前端: Streamlit (`ui/`)
- LLM: OpenAI SDK + Anthropic SDK
- 数据校验: Pydantic v2
- 测试: pytest
- Python: 3.11 (conda 环境 `job-copilot-v0`)

## 目录结构

```
app/
  main.py                          # FastAPI 入口，POST /task
  orchestrators/
    job_copilot_orchestrator.py    # 任务主流程 + trace 记录
  services/
    llm_service.py                 # LLM 调用封装
    prompt_service.py              # 从 prompts/ 加载 markdown
  prompts/
    jd_analyze.md
    resume_optimize.md
    self_intro_generate.md
  types/
    task_result.py                 # TaskResult / ErrorDetail (Pydantic)
    trace_event.py                 # TraceEvent / TraceNodeNames / TraceStatus
    retriever_context.py           # RetrieverContext（RAG 预留）
evaluation/                        # 验收测试文档
tests/                             # pytest
ui/                                # Streamlit 前端
schemas/                           # JSON Schema
```

## 核心 API

**POST /task** — 唯一业务端点

请求体（TaskRequest）:
- `task_type`: 字符串，必须是有效任务类型之一
- `payload`: dict，各任务所需字段不同

有效 task_type：`jd_analyze` / `resume_optimize` / `self_intro_generate`

响应结构（TaskResult）:
- `status`: "success" | "error"
- `task_type`: 原始任务类型
- `result`: 成功时的 LLM 输出（dict），失败时为 null
- `error`: ErrorDetail（error_type + error_message），成功时为 null
- `retriever_context`: RAG 预留，当前始终为 null
- `trace`: TraceEvent 列表，记录每个执行节点

HTTP 状态码：成功 200，失败 400。

## 任务执行流程

```
orchestrator.execute_task(task_type, payload)
  1. 任务识别  → 校验 task_type，无效直接 return TaskResult.from_error()
  2. Prompt 加载 → prompt_service.get_prompt(task_type)
  3. 调用 LLM  → llm_service.call_llm(system_prompt, payload)
  4. 结果汇总  → return TaskResult.from_success()
  异常兜底     → except Exception → TaskResult.from_error()
```

每步均记录 TraceEvent（node_name / status / remark）。

## 开发约定

- **新增任务类型**：在 `VALID_TASK_TYPES` 添加名称 + 创建 `app/prompts/<name>.md`
- **新增服务**：放 `app/services/`，保持单一职责
- **TaskResult 构造**：只用工厂方法 `from_success` / `from_error`，不直接构造
- **Trace 记录**：每个执行节点都要记录，失败时 remark 写入错误信息
- **不可变**：TaskResult / TraceEvent 为 Pydantic 模型，不要原地修改

## 未实现功能（后续阶段）

- 工具调用（RAG 检索）→ 第 5 月对接，retriever_context 字段预留
- session 连续改写（对话历史）→ 第 5 月对接

## 测试

```bash
# 从项目根目录运行
pytest tests/ -v
```

验收文档：`evaluation/week4_backend_acceptance.md`


## Daily Plan Coach Bridge

- Repo-local learning guidance lives in `skills/daily-plan-coach/SKILL.md`.
- The following project phrases are the only automatic bridge triggers for this skill:
  - `开始今天的学习`
  - `继续今天的学习`
  - `继续今天计划`
  - `进入 Daily Plan Coach 模式`
- When one of these triggers appears, Codex must read `skills/daily-plan-coach/SKILL.md` first, follow that workflow, and skip other generic learning, teaching, or explanation skills.
- The repo-local skill file above is the source of truth for teaching behavior, step assessment, and progress-writing rules.
- The study session state must come from `Today_Plan/*.md` and `Today_Plan/daily_progress.txt`.
- Do not treat project-level `progress.txt` as the study session state file.
