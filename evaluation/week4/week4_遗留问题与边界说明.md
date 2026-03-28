# 第 4 周边界说明：遗留问题与刻意取舍

> 本文档记录本周没做、故意不做、留到下月的内容，防止后续回看时误判为遗漏。

---

## 入口层（`app/main.py`）

### 已冻结，不再修改

| 字段 / 行为 | 当前状态 | 说明 |
|---|---|---|
| `POST /task` 统一入口 | ✅ 已完成 | 唯一业务端点，不再新增路由 |
| 请求体：`task_type` + `payload` | ✅ 已冻结 | 第 5 月 RAG 接入不改这两个字段 |
| HTTP 状态码：成功 200 / 失败 400 | ✅ 已冻结 | — |

### 刻意未做（下月再接）

| 功能 | 为什么不做 | 改动位置 |
|---|---|---|
| `session_id` 参数 | session 连续改写依赖检索链路，第 5 月统一接入 | `main.py` 的 `TaskRequest` 增加 `session_id: Optional[str]` 字段 |
| 鉴权 / Rate Limiting | 本周目标是最小后端骨架，不是生产部署 | 路由层增加 middleware |

---

## 流程层（`app/orchestrators/job_copilot_orchestrator.py`）

### 已冻结，不再修改

| 节点 | 当前状态 | 说明 |
|---|---|---|
| 任务识别 → Prompt 加载 → LLM 调用 → 结果汇总 | ✅ 已完成 | 四节点主链路稳定 |
| Trace 记录每个节点 | ✅ 已完成 | 每节点均有 node_name / status / remark |
| 异常兜底（`except Exception`） | ✅ 已完成 | 捕获所有未预期异常，写入失败节点 |

### 刻意未做（下月再接）

| 功能 | 为什么不做 | 改动位置 |
|---|---|---|
| 工具调用（Tool Use） | 依赖 RAG 检索结果，第 5 月接入文档切分后再做 | orchestrator 中在 LLM 调用节点前后插入检索节点 |
| session 对话历史拼接 | 同上，依赖 session 存储，第 5 月统一接入 | orchestrator 中在 Prompt 加载后拼接历史消息 |
| 多模型路由 | 本周只验证骨架正确性，模型策略是优化项 | `llm_service.py` 中按 task_type 路由不同模型 |

---

## 数据层（`app/types/`）

### 已冻结，不再修改

| 类型 | 当前状态 | 说明 |
|---|---|---|
| `TaskResult`：status / task_type / result / error / trace / retriever_context | ✅ 已冻结 | 响应协议锁定，下月不改字段名和类型 |
| `TraceEvent`：node_name / status / timestamp / remark | ✅ 已冻结 | — |
| `RetrieverContext`：context_id / status / timestamp / chunks | ✅ 字段预留 | 当前始终为 null，第 5 月填充真实数据 |
| `RetrieverChunk`：chunk_id / source_title / source_url / content / range | ✅ 字段预留 | 同上 |

### 刻意未做（下月再接）

| 功能 | 为什么不做 | 改动位置 |
|---|---|---|
| `retriever_context` 真实填充 | RAG 检索链路第 5 月才建，现在填充没有意义 | orchestrator 调用检索后传入 `TaskResult.from_success()` |
| `session` 相关字段 | 同流程层原因 | `TaskResult` 增加 `session_id` 和 `history` 字段（或独立 SessionRecord 类型） |

---

## 结论

本周所有「未做」均为**刻意取舍**，不是遗漏：

- 入口层协议已冻结，下月只加字段，不改现有字段
- 流程层骨架稳定，下月插入检索节点和 session 节点
- 数据层结构预留到位，下月填充真实数据即可

**判断标准**：如果后续发现某个「没做」导致无法继续推进，才算真正遗漏；否则都是取舍。
