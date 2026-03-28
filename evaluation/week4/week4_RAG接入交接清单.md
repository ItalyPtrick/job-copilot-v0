# 第 5 月 RAG 接入交接清单

> 本文档明确第 5 月从哪几个接口、字段、模块开始接入 RAG，避免下月重新分析方向。

---

## 接入点一：数据层——填充 `retriever_context`

**文件**：`app/types/retriever_context.py`

当前状态：`RetrieverContext` 和 `RetrieverChunk` 字段已定义，响应中始终返回 `null`。

第 5 月动作：
- 实现实际检索逻辑后，构造 `RetrieverContext` 对象传入 `TaskResult.from_success()`
- `RetrieverChunk` 字段说明：
  - `chunk_id`：检索文档片段的唯一 ID
  - `source_title`：来源文档标题（如简历文件名、JD 标题）
  - `source_url`：来源 URL（本地文件可为空字符串）
  - `content`：实际片段内容
  - `range`：片段在源文档中的位置（如 `"第2-5段"`，可选）

**不需要修改**：`TaskResult` 字段结构已冻结，`retriever_context` 字段名和类型不变。

---

## 接入点二：流程层——在 orchestrator 插入检索节点

**文件**：`app/orchestrators/job_copilot_orchestrator.py`

当前流程：任务识别 → Prompt 加载 → LLM 调用 → 结果汇总

第 5 月目标流程：任务识别 → Prompt 加载 → **RAG 检索** → LLM 调用（携带检索结果）→ 结果汇总

第 5 月动作：
- 在 Prompt 加载后、LLM 调用前，插入检索节点
- 检索节点需记录 `TraceEvent`（node_name 建议：`"RAG 检索完成"`）
- 将检索结果拼入 system_prompt 或作为独立上下文传给 `call_llm()`
- 检索失败时：记录 ERROR trace，降级为无检索上下文继续调用 LLM（不中断主链路）

**新增 TraceNodeNames 常量**：在 `app/types/trace_event.py` 的 `TraceNodeNames` 中增加 `RAG_RETRIEVAL = "RAG 检索完成"`。

---

## 接入点三：入口层——为 session 预留参数位

**文件**：`app/main.py`

当前状态：`TaskRequest` 只有 `task_type` 和 `payload`，无 session 相关字段。

第 5 月动作（session 连续改写）：
- `TaskRequest` 增加 `session_id: Optional[str] = None`
- session 历史存储方案待定（内存 dict / Redis / 文件），确定后在 orchestrator 中拼接历史消息

**注意**：`session_id` 加入请求体是破坏性变更（调用方需更新请求格式），需提前通知或做版本兼容。

---

## 第 5 月开工顺序建议

| 顺序 | 任务 | 原因 |
|---|---|---|
| 1 | 文档接入与切分 | RAG 的数据来源，先有 chunk 才能检索 |
| 2 | 检索链路（orchestrator 插入节点） | 有了数据才能接检索 |
| 3 | `retriever_context` 真实填充 | 检索完成后直接填字段 |
| 4 | session 连续改写 | 依赖检索链路稳定后再加 |

---

## 本月不需要动的部分

- `TaskResult` 字段结构：已冻结，不改
- `POST /task` 路由：不改（session_id 作为可选字段追加，不破坏现有调用）
- 三类 Prompt 文件：根据 RAG 效果再决定是否调整
