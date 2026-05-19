# API Reference

> 目标读者：执行前端实现的 AI Agent。
> 本文档是接口契约，TypeScript interface 可直接用于 `src/api/` 类型定义。

---

## 1. 通用约定

### 1.1 基础路径

前端所有请求使用 `/api` 前缀的相对路径。开发时由 Vite proxy strip `/api` 后转发到 `http://localhost:8000`。

```
前端请求:  POST /api/task
实际到达:  POST http://localhost:8000/task
```

**禁止硬编码域名或端口。**

### 1.2 Content-Type

- JSON 请求：`application/json`
- 文件上传：`multipart/form-data`

### 1.3 统一错误格式

FastAPI HTTPException 返回：

```typescript
interface HTTPError {
  detail: string;
}
```

### 1.4 TaskResult 统一响应

`POST /api/task` 的所有 task_type 共享此响应结构：

```typescript
interface TaskResult {
  status: "success" | "error";
  task_type: string;
  result: any | null;
  error: { error_type: string; error_message: string } | null;
  retriever_context: any | null;
  trace: { node_name: string; status: string; remark: string }[] | null;
}
```

HTTP 状态码：成功 `200`，业务错误 `400`。

---

## 2. 端点详细 Schema

### 2.1 POST /api/task — JD 分析

**请求体**

```typescript
interface JDAnalyzeRequest {
  task_type: "jd_analyze";
  payload: {
    jd_text: string;        // 职位描述原文
    target_role: string;    // 目标岗位名称
  };
}
```

**响应体**

`TaskResult`，其中 `result` 字段为 LLM 结构化输出，包含：

```typescript
interface JDAnalyzeResult {
  hard_requirements: string[];   // 硬性要求
  core_skills: string[];         // 核心技能
  bonus_skills: string[];        // 加分项
  [key: string]: any;            // LLM 可能返回额外字段
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 200 | 分析成功 |
| 400 | payload 缺失必填字段或 LLM 返回错误 |

**示例**

请求：
```json
{
  "task_type": "jd_analyze",
  "payload": {
    "jd_text": "Python开发实习生\n任职要求：\n1. 熟悉Python基础语法\n2. 了解Git版本控制",
    "target_role": "Python开发实习生"
  }
}
```

响应：
```json
{
  "status": "success",
  "task_type": "jd_analyze",
  "result": {
    "hard_requirements": ["熟悉Python基础语法", "了解Git版本控制"],
    "core_skills": ["Python", "Git"],
    "bonus_skills": []
  },
  "error": null,
  "retriever_context": null,
  "trace": [{"node_name": "jd_analyze", "status": "success", "remark": ""}]
}
```

---

### 2.2 POST /api/task — 简历优化

**请求体**

```typescript
interface ResumeOptimizeRequest {
  task_type: "resume_optimize";
  payload: {
    resume_item: string;              // 待优化的简历条目
    target_jd_keywords: string[];     // 目标 JD 关键词
    role_summary: string;             // 目标岗位概述
  };
}
```

**响应体**

`TaskResult`，其中 `result` 为优化后的文本（string 或含 optimized 字段的对象，取决于 LLM 输出）。

**示例**

请求：
```json
{
  "task_type": "resume_optimize",
  "payload": {
    "resume_item": "负责公司后端开发工作，完成了一些功能模块。",
    "target_jd_keywords": ["FastAPI", "Python", "RESTful API"],
    "role_summary": "Python后端开发工程师"
  }
}
```

---

### 2.3 POST /api/task — 自我介绍生成

**请求体**

```typescript
interface SelfIntroRequest {
  task_type: "self_intro_generate";
  payload: {
    tone: "formal" | "conversational";  // 语气风格
    resume_item: string;                 // 简历核心经历
    target_jd_keywords: string[];        // 目标关键词
    role_summary: string;                // 目标岗位
  };
}
```

**响应体**

`TaskResult`，其中 `result` 为生成的自我介绍文本（string）。

---

### 2.4 POST /api/interview/start

**请求体**

```typescript
interface InterviewStartRequest {
  skill?: string;                          // 面试技能方向，默认 "python_backend"
  total_questions?: number;                // 主问题数量，默认 10，最小 1
  follow_up_count?: number;                // 每题追问次数，默认 1，最小 0
  difficulty_distribution?: Record<string, number> | null;  // 难度分布，可选
}
```

**响应体**

```typescript
interface InterviewStartResponse {
  session_id: string;
  question: {
    question: string;       // 题干
    category: string;       // 分类
    difficulty: string;     // 难度：easy / medium / hard
    difficulty_reason: string;
    follow_up_hint: string;
    assessment_focus: string;  // 考察重点
  };
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 200 | 面试创建成功 |
| 400 | 配置无效或 skill 不存在 |
| 503 | LLM 出题服务不可用 |

### 2.5 POST /api/interview/answer

**请求体**

```typescript
interface InterviewAnswerRequest {
  session_id: string;
  answer: string;   // 不能为空
}
```

**响应体**

```typescript
interface InterviewAnswerResponse {
  action: "follow_up" | "next_question" | "complete";
  reason: string;
  performance_signal: string;
  follow_up?: string;       // 仅 action="follow_up" 时存在
  question?: {              // 仅 action="next_question" 时存在
    question: string;
    category: string;
    difficulty: string;
    difficulty_reason: string;
    follow_up_hint: string;
    assessment_focus: string;
  };
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 200 | 回答处理成功 |
| 400 | session 不在进行中 |
| 404 | session 不存在 |
| 503 | LLM 服务不可用 |

**前端行为映射**

| action | UI 行为 |
|--------|---------|
| `follow_up` | 显示 `follow_up` 字段内容为新消息，用户继续输入 |
| `next_question` | 显示 `question` 字段内容为新消息，用户继续输入 |
| `complete` | 禁用输入框，显示"获取评估"按钮 |

---

### 2.6 POST /api/interview/evaluate

**请求体**

```typescript
interface InterviewEvaluateRequest {
  session_id: string;
}
```

**响应体**

```typescript
interface InterviewEvaluateResponse {
  overall_score: number;        // 总分（1-10 的平均分，保留一位小数）
  summary: string;              // 总结评语
  strengths: string[];          // 强项分类
  improvements: string[];       // 待改进分类
  items: {
    question: string;
    answer: string;
    score: number;              // 单题分数 1-10
    feedback: string;
    category: string;
  }[];
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 200 | 评估成功 |
| 400 | session 未完成，不能评估 |
| 404 | session 不存在 |
| 503 | 评估服务不可用 |

**注意：** 此接口耗时较长（LLM 批量评估），前端需显示 loading 状态。

---

### 2.7 POST /api/kb/query

**请求体**

```typescript
interface KBQueryRequest {
  question: string;              // 不能为空
  collection_name?: string;      // 默认 "default"
  top_k?: number;                // 默认 5，最小 1
}
```

**响应体**

```typescript
interface KBQueryResponse {
  answer: string;
  sources: {
    content: string;
    metadata: Record<string, any>;
  }[];
}
```

---

### 2.8 POST /api/kb/query/stream（SSE）

**请求体**

同 `KBQueryRequest`。

**响应格式**

Content-Type: `text/event-stream`

事件流格式：
```
event: message
data: 这是第一个文本片段

event: message
data: 这是第二个文本片段

event: done
data:
```

**前端消费方式：**
- 使用 `fetch` + `response.body.getReader()` 逐行解析 SSE
- 每收到 `event: message`，将 `data` 追加到界面（打字机效果）
- 收到 `event: done` 后停止渲染，标记完成
- 流式接口不返回 `sources`，如需来源信息请用同步 `/kb/query`

**错误处理：**
- 流式过程中若后端出错，连接将直接断开（不会发送 `event: error`）
- 前端通过 `reader.closed` 或 `catch` 捕获异常，向用户展示"生成中断，请重试"
- 若连接断开时未收到 `event: done`，视为异常终止

### 2.9 POST /api/resume/upload

**请求格式**

`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | PDF / DOCX / TXT |
| `target_role` | string | 否 | 目标岗位，默认空 |

**响应体**

```typescript
interface ResumeUploadResponse {
  resume_id: string;
  status: "analyzing";   // 上传后立即进入分析状态
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 202 | 上传成功，异步分析已触发 |
| 400 | 文件格式不支持或文件为空 |

---

### 2.10 GET /api/resume/{resume_id}/status

**响应体**

```typescript
interface ResumeStatusResponse {
  resume_id: string;
  filename: string;
  status: "pending" | "analyzing" | "completed" | "failed";
  target_role: string;
  created_at: string;   // ISO datetime string
}
```

**轮询策略：** 每 2 秒请求一次，超时 60 秒后提示用户重试。

---

### 2.11 GET /api/resume/{resume_id}/report

**响应体**

```typescript
interface ResumeReportResponse {
  resume_id: string;
  filename: string;
  status: "completed";
  target_role: string;
  analysis_result: Record<string, any>;  // LLM 结构化分析结果
  created_at: string;
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 200 | 报告获取成功 |
| 404 | 简历记录不存在 |
| 409 | 分析尚未完成 |

---

## 3. 面试状态机

```
未开始 ──[POST /interview/start]──→ 进行中 ──[action="complete"]──→ 已结束 ──[POST /interview/evaluate]──→ 已评估
```

**session 生命周期：**
- session 存储在 Redis，TTL 2 小时
- 页面刷新后 session 数据丢失（前端 Zustand store 清空），需处理无 session 的降级
- `session_id` 在面试期间必须随每个请求携带

**前端状态管理建议：**

```typescript
type InterviewStatus = "idle" | "in_progress" | "completed" | "evaluated";
```

---

## 4. 可用的 skill 列表

面试 `/start` 接口的 `skill` 参数对应 `app/skills/` 目录下的 YAML 文件名（不含扩展名）。前端可硬编码以下选项供用户选择：

- `python_backend` — Python 后端开发（默认）

如需动态获取列表，后端暂无专门端点，建议前端硬编码。


