# job-copilot-v0 项目规范

## Daily Plan Mentor 桥接规则

以下入口**必须且只能**触发 `.claude/skills/daily_plan_mentor.md`，不得先调用其他 skill、普通讲解模式或其他 agent：

**命中条件（满足任意一条即触发）：**
- 消息中包含 `/daily-plan-mentor`（无论前后是否附带自然短语）
- 消息独立包含以下自然短语之一：「开始今天的学习」「继续今天的学习」「继续今天计划」

**触发动作：**
立即读取 `.claude/skills/daily_plan_mentor.md` 并严格按其工作流程执行，跳过所有其他路由判断。

---

## 会话启动协议

每次新会话开始：
1. 读取 `progress.txt` 了解当前进度和已知 Bug
2. 如果 `lessons.md` 存在，读取历史教训并主动避免
3. 用一句话确认：”已同步进度：[摘要]，准备开始。”

> **例外：Daily Plan Mentor 触发时**，跳过步骤 1（不读取 `progress.txt`）。学习状态由 `Today_Plan/*.md` 和 `Today_Plan/daily_progress.txt` 独立提供，详见 `.claude/skills/daily_plan_mentor.md`。

---

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
