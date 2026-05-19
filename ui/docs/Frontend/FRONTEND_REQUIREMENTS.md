# 前端需求文档

> 目标读者：执行此文档的 AI Agent。
> 性质：需求与约定，不是执行手册。实现方式由你决定。

---

## 1. 项目背景

job-copilot-v0 是一个求职 AI 助手后端（FastAPI），支持 JD 分析、简历优化、模拟面试、知识库问答等功能。后端已全部完成（W1~W5），API 可用但无前端界面。

**前端唯一目标：** 让面试官在 2 分钟内理解三件事——这是什么应用、解决什么问题、用了什么技术。手段是可交互演示，不是静态展示。

### 1.1 交付策略

分 3 批交付，每批完成后需通过验证再进入下一批：

| 批次 | 内容 | 验证标准 |
|------|------|----------|
| Batch 1 | 项目初始化 + Landing Page + JD 分析 | `npm run dev` 启动无报错；Landing Page 可见且暗色模式可切换；JD 分析输入文本后能渲染结果卡片（mock mode 下用假数据） |
| Batch 2 | 简历优化 + 模拟面试 | 简历优化并排对比可渲染；面试聊天完整走通 start → answer → evaluate 流程（mock mode） |
| Batch 3 | 自我介绍 + 知识库查询 + 简历分析 | 三个功能均可操作；知识库流式渲染正常；简历上传 → 轮询 → 报告展示流程通畅 |

每批交付后执行 `npm run build`，确认无 TypeScript 编译错误。

---

## 2. 技术栈

| 层 | 选型 |
|---|---|
| 框架 | React 18+ |
| 构建工具 | Vite |
| 样式 | Tailwind CSS |
| 组件库 | shadcn/ui（源码复制模式，非 npm 依赖） |
| 语言 | TypeScript |
| 路由 | React Router v6（每个功能独立路径） |
| 状态管理 | Zustand（面试聊天等复杂状态） |
| HTTP 客户端 | 原生 fetch 即可，不引入 axios |

### 2.1 架构决策（已锁定）

以下选型已确定，执行时不要偏离：

| 决策 | 选型 | 理由 |
|------|------|------|
| 路由 | React Router v6 | 每个功能有独立 URL，可分享、可刷新 |
| 状态管理 | Zustand | 面试聊天有频繁状态更新，需细粒度订阅避免不必要 re-render |
| Tailwind | v3（非 v4） | 生态成熟，shadcn/ui 官方支持好 |
| shadcn/ui 初始化 | 使用 CLI (`npx shadcn-ui@latest init`) | 保证配置正确，组件按需添加 |
| 暗色模式 | shadcn/ui 内置方案（class strategy） | 不引入 next-themes（非 Next.js 项目） |

---

## 3. 功能清单与优先级

### 高优（精做）

| 功能 | 后端端点 | 交互形式 | 验收条件 |
|---|---|---|---|
| JD 分析 | `POST /api/task` (task_type=jd_analyze) | textarea 输入 JD → 提交 → 结构化结果卡片 | 输入任意文本 → 点击提交 → 渲染包含"硬性要求/核心技能/加分项"三个区块的卡片；loading 期间显示骨架屏或 spinner |
| 简历优化 | `POST /api/task` (task_type=resume_optimize) | textarea 输入简历片段 + 目标关键词 → 提交 → 对比展示 | 输入简历文本 + 关键词 → 提交 → 左右并排展示原文与优化后文本；差异处有视觉区分（高亮或颜色） |
| 模拟面试 | `POST /api/interview/start`、`/api/interview/answer`、`/api/interview/evaluate` | 聊天界面（详见 §3.1） | 完整走通 start → 多轮 answer → evaluate 流程；消息按时间线排列；结束后展示评分报告 |

### 中优（能跑通即可）

| 功能 | 后端端点 | 交互形式 | 验收条件 |
|---|---|---|---|
| 自我介绍生成 | `POST /api/task` (task_type=self_intro_generate) | textarea 输入 → 提交 → 文本展示 | 输入文本 → 提交 → 渲染结果文本；有"复制到剪贴板"按钮且功能正常 |
| 知识库查询 | `POST /api/kb/query` 或 `/api/kb/query/stream` | textarea 输入问题 → 提交 → 流式文本 | 输入问题 → 提交 → 文本逐字渲染（打字机效果）；流结束后文本完整可选中 |
| 简历分析 | `POST /api/resume/upload`、`GET /api/resume/{id}/status`、`GET /api/resume/{id}/report` | 文件上传 → 轮询等待 → 报告展示 | 上传 PDF/DOCX → 显示进度状态（pending/analyzing）→ 完成后渲染结构化报告；失败时显示错误提示 |

### §3.1 模拟面试聊天界面详细需求

这是前端最复杂的组件，需要特别注意：

**交互流程：**
1. 用户点击"开始面试"，填写配置（skill、题目数量、追问次数），调用 `/api/interview/start`
2. 返回 `session_id` + 第一道题，以聊天气泡形式展示
3. 用户在输入框回答，调用 `/api/interview/answer`，返回追问或下一题
4. 所有消息（系统题目 + 用户回答 + 追问）按时间线排列
5. 面试结束后，用户点击"获取评估"，调用 `/api/interview/evaluate`，返回评分报告

**状态管理要求：**
- `session_id`：面试期间持久保存，所有后续请求必须携带
- 消息列表：包含系统消息（题目/追问）和用户消息（回答），需区分样式
- 面试状态：未开始 → 进行中 → 已结束（影响按钮可用性和输入框状态）

**边界条件：**
- `/interview/answer` 响应中 `status` 字段决定 UI 行为：
  - `"answer_ok"`：显示追问，用户继续回答
  - `"next_question"`：显示下一题，用户继续回答
  - `"complete"`：面试结束，显示"获取评估"按钮
- `/interview/evaluate` 是同步调用（LLM 评估耗时较长），前端需显示 loading 状态
- 面试过程中如果用户刷新页面，session 数据丢失（Redis TTL 2 小时），需处理无 session 的情况

**聊天 UI 规范：**
- 系统消息（题目/追问）左对齐，用户回答右对齐
- 每条消息显示发送者标识
- 消息列表自动滚动到底部
- 输入框在面试进行中可用，结束后禁用

---

## 4. 页面结构

### 4.1 Landing Page

**目的：** 10 秒内传达"这是什么"。

**必须包含的内容：**
- 项目名称 + 一句话定位（如"基于 LLM 的求职 AI 助手"）
- 解决什么问题（3~4 句，面向求职场景的痛点）
- 技术栈展示（FastAPI / PostgreSQL / Redis / Celery / RAG / Docker，可用图标或标签形式）
- "试一试"按钮，跳转到功能区

**设计要求：**
- 简洁，不要大段文字堆砌
- 技术栈部分要醒目（面试官重点关注）
- 支持暗色模式

### 4.2 功能区

**导航：** 左侧固定侧边栏，右侧内容区。

**侧边栏结构：**
```
┌──────────────────────────────────────────────┐
│ [Logo/项目名]                                │
├────────────┬─────────────────────────────────┤
│            │                                 │
│  JD 分析   │                                 │
│  简历优化  │         内容区                   │
│  模拟面试  │     （当前功能页面）              │
│  ────────  │                                 │
│  自我介绍  │                                 │
│  知识库    │                                 │
│  简历分析  │                                 │
│            │                                 │
│  ────────  │                                 │
│  [暗色切换]│                                 │
├────────────┴─────────────────────────────────┤
└──────────────────────────────────────────────┘
```

- 高优功能排在上方，中优功能用分隔线隔开排在下方
- 侧边栏宽度固定（~220px），内容区自适应
- 当前选中项有高亮状态
- 暗色模式切换按钮放在侧边栏底部

**模拟面试页面特殊要求：**
- 聊天界面占满内容区高度
- 配置面板（skill 选择、题目数量等）放在聊天区顶部，面试开始后自动折叠

---

## 5. API 集成约定

### 5.1 路径约定

前端所有 API 请求使用 `/api` 前缀的**相对路径**：

```
前端请求:  POST /api/task
实际到达:  POST /task（Vite proxy / Nginx strip prefix）
```

| 场景 | 配置 |
|---|---|
| 开发时 | Vite proxy: `/api` → `http://localhost:8000` |
| 部署时 | Nginx: `location /api/` 反代到 `http://localhost:8000/`，strip `/api` 前缀 |

前端代码中**禁止硬编码** `http://localhost:8000` 或任何域名。统一用 `/api/...` 相对路径。

### 5.2 请求/响应格式

所有请求的 Content-Type 为 `application/json`，文件上传除外（`multipart/form-data`）。

响应格式参考后端 API 文档（`http://localhost:8000/docs`），前端按需取字段。

### 5.3 SSE 流式处理

知识库查询使用 `/kb/query/stream`（SSE）。前端需要：
- 使用 `fetch` + `ReadableStream` 或 `EventSource` 接收事件
- 逐字渲染到界面（打字机效果）
- 事件类型：`event: message`（数据，data 字段为纯文本片段）、`event: done`（结束，data 为空）
- 参考实现：`app/modules/knowledge_base/router.py` 中的 `query_stream` 端点

### 5.4 文件上传

简历分析需要上传文件（PDF/DOCX/TXT）。前端需要：
- 使用 `multipart/form-data` 提交到 `POST /api/resume/upload`，字段名 `file`
- 上传后获得 `resume_id`，轮询 `GET /api/resume/{id}/status`
- 轮询间隔：2 秒，超时：60 秒（超时后显示"分析超时，请重试"）
- 状态值：`pending` → `analyzing` → `completed` / `failed`
- 完成后调用 `GET /api/resume/{id}/report` 获取结果
- 参考实现：`app/modules/resume/router.py`

### 5.5 错误处理

- 后端返回 HTTP 4xx/5xx 时，前端显示友好提示（不要显示 raw JSON error）
- 网络不可达时显示"服务不可用，请确认后端已启动"
- 模拟面试中 session 过期时提示"面试会话已过期，请重新开始"

### 5.6 Mock 策略

前端需内置 mock mode，后端不可用时自动降级，确保演示不依赖后端在线。

**触发条件：** API 请求失败（网络错误或 5xx）时，自动切换到 mock 数据。不需要手动开关。

**实现要求：**
- 在 `src/api/` 层封装：真实请求失败 → 返回预置的 mock 数据
- 每个功能对应一份 mock 数据文件，放在 `src/mocks/` 目录
- mock 数据应模拟真实后端响应结构，内容可以是固定的示例数据
- 使用 mock 数据时，在页面顶部显示一个不显眼的提示条："当前为演示模式（后端未连接）"

**各功能 mock 行为：**
| 功能 | mock 行为 |
|------|-----------|
| JD 分析 | 返回一份预置的分析结果 JSON |
| 简历优化 | 返回预置的原文 + 优化后对比 |
| 模拟面试 | 预置 3 轮问答 + 评估报告，模拟延迟 1~2 秒 |
| 自我介绍 | 返回预置文本 |
| 知识库查询 | 模拟逐字输出（setTimeout 模拟流式） |
| 简历分析 | 模拟 pending → completed 状态变化（3 秒后完成），返回预置报告 |

> Mock 模式提示条的视觉样式见 `DESIGN_SYSTEM.md` §6.9。

---

## 6. 设计规范

### 6.1 整体风格

- 现代简洁，参考 shadcn/ui 默认风格
- 中文界面（所有文案、按钮、提示均为中文）
- 适配桌面端即可，不要求移动端响应式

### 6.2 暗色模式

- 使用 shadcn/ui class strategy（html 标签加 `dark` class）
- Landing Page 和功能区都需支持
- 默认跟随系统偏好

### 6.3 色彩

- 主色调由你决定，但要与 shadcn/ui 默认主题协调
- Landing Page 技术栈标签可用彩色区分
- 聊天界面的系统消息和用户消息用不同背景色区分

---

## 7. 项目结构约定

代码放在 `ui/` 目录，初始化为标准 React + Vite 项目。

```
ui/
├── src/
│   ├── components/       # 通用组件（shadcn/ui 组件也在此）
│   ├── features/         # 功能模块（按功能拆分）
│   ├── pages/            # 页面组件（对应路由）
│   ├── hooks/            # 自定义 hooks
│   ├── stores/           # Zustand stores
│   ├── mocks/            # Mock 数据文件
│   ├── lib/              # 工具函数
│   └── api/              # API 请求封装（含 mock fallback 逻辑）
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

`ui/` 目录下现有的 `minimal_app.py` 是旧文件，初始化时可删除。

---

## 8. 不需要做的事

- 不需要用户认证/登录
- 不需要移动端适配
- 不需要国际化（纯中文）
- 不需要写测试（demo 性质）
- 不需要对接 CI/CD
- 不需要 SEO 优化

---

## 9. 执行前桥接文档

如果下一步要让另一个 agent 直接开始写执行计划，先读这份文档：

- `ui/docs/Frontend/IMPLEMENTATION_OUTLINE.md`

它只负责把当前需求拆成可执行批次和模块边界，不替代执行计划。
