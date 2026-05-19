# 前端实现执行计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐步执行本计划。每个 Step 使用 checkbox (`- [ ]`) 语法追踪进度。
>
> **必须使用的 Skills：**
> - `frontend-design:frontend-design` — 所有涉及 UI 组件/页面创建的 Step（标记为 🎨）必须调用此 skill，确保视觉质量不落入 AI 通用审美。执行时需结合 `DESIGN_SYSTEM.md` 的色彩/字体/间距规范作为约束输入。
> - `feature-dev:feature-dev` — 复杂功能模块（标记为 🏗️）建议调用此 skill 的完整流程（Discovery → Exploration → Architecture → Implementation → Review），确保架构决策经过多方案对比。
> - `context7` — 配置类步骤（标记为 📚）遇到 Vite/Tailwind/shadcn/React Router/Zustand 的 API 不确定时，必须用 context7 查询官方文档，不凭记忆猜测。

**Goal:** 为 job-copilot-v0 构建完整的 React 前端，包含 6 个功能模块 + Landing Page + Mock fallback 机制。

**Architecture:** SPA 架构，React Router v6 管理路由，Zustand 管理全局状态（theme/interview/mockMode），`src/api/` 层统一封装请求并在后端不可用时自动降级到 mock 数据。所有 API 请求使用 `/api/` 相对路径前缀，由 Vite proxy（开发）或 Nginx（生产）strip 后转发到后端。

**Tech Stack:** React 18 · TypeScript · Vite · Tailwind CSS · shadcn/ui · Zustand · React Router v6 · 原生 fetch

---

## 文件结构总览

```
ui/
├── public/
├── src/
│   ├── api/              # 请求封装 + mock fallback 逻辑
│   │   ├── client.ts     # 基础 fetch 封装（错误处理、mock 降级）
│   │   ├── jd.ts         # analyzeJD()
│   │   ├── resume.ts     # optimizeResume()
│   │   ├── interview.ts  # startInterview(), submitAnswer(), evaluate()
│   │   ├── selfIntro.ts  # generateSelfIntro()
│   │   ├── kb.ts         # queryKB(), queryKBStream()
│   │   └── resumeAnalysis.ts  # uploadResume(), getStatus(), getReport()
│   ├── mocks/            # 静态 mock 数据
│   │   ├── jd.ts
│   │   ├── resume.ts
│   │   ├── interview.ts
│   │   ├── selfIntro.ts
│   │   ├── kb.ts
│   │   └── resumeAnalysis.ts
│   ├── stores/           # Zustand stores
│   │   ├── theme.ts      # useThemeStore（暗色模式）
│   │   ├── mockMode.ts   # useMockModeStore（mock 状态全局感知）
│   │   └── interview.ts  # useInterviewStore（session/messages/status）
│   ├── components/       # 跨功能复用组件
│   │   ├── ui/           # shadcn/ui 组件（Button, Input, Card, Tabs...）
│   │   ├── AppLayout.tsx # Sidebar + Content area 布局壳
│   │   ├── Sidebar.tsx   # 导航侧边栏
│   │   ├── MockBanner.tsx    # Mock 模式提示条
│   │   ├── ChatBubble.tsx    # 聊天气泡（系统/用户）
│   │   ├── ResultCard.tsx    # 结果展示卡片
│   │   ├── SkeletonBlock.tsx # 骨架屏
│   │   └── MarkdownRenderer.tsx # Markdown 渲染
│   ├── features/         # 功能模块页面
│   │   ├── landing/      # Landing Page
│   │   │   └── LandingPage.tsx
│   │   ├── jd-analyze/
│   │   │   └── JDAnalyzePage.tsx
│   │   ├── resume-optimize/
│   │   │   └── ResumeOptimizePage.tsx
│   │   ├── interview/
│   │   │   ├── InterviewPage.tsx
│   │   │   ├── ConfigPanel.tsx
│   │   │   ├── ChatArea.tsx
│   │   │   └── EvaluationReport.tsx
│   │   ├── self-intro/
│   │   │   └── SelfIntroPage.tsx
│   │   ├── knowledge-base/
│   │   │   └── KnowledgeBasePage.tsx
│   │   └── resume-analysis/
│   │       └── ResumeAnalysisPage.tsx
│   ├── lib/              # 工具函数
│   │   └── utils.ts      # cn() 等
│   ├── App.tsx           # 路由定义
│   ├── main.tsx          # 入口
│   └── index.css         # Tailwind 指令 + 全局样式
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── postcss.config.js
├── components.json       # shadcn/ui 配置
└── package.json
```

**依赖方向（严格单向）：**
- `features/` → `api/` → `mocks/`
- `features/` → `stores/`
- `features/` → `components/`
- 反向依赖禁止

---

## Batch 0：项目骨架

> 目标：从零初始化项目，搭建基础设施层（不含任何 UI 功能）。完成后 `npm run dev` 可启动空白页面。

### Step 0-1：项目初始化（Vite + React + TS） 📚

**创建文件：**
- `ui/package.json`
- `ui/vite.config.ts`
- `ui/tsconfig.json`、`ui/tsconfig.node.json`
- `ui/index.html`
- `ui/src/main.tsx`、`ui/src/App.tsx`
- `ui/postcss.config.js`

**操作：**
- [ ] 在 `ui/` 目录执行 `npm create vite@latest . -- --template react-ts`（注意 `.` 表示当前目录）
- [ ] 删除 Vite 模板自带的 `src/App.css`、`src/assets/`、默认 counter 代码
- [ ] `npm install`
- [ ] 验证 `npm run dev` 启动成功

**完成标志：** 浏览器访问 `localhost:5173` 显示空白页面或最小文本，无报错。

---

### Step 0-2：Tailwind CSS + shadcn/ui 初始化 📚

**创建/修改文件：**
- `ui/tailwind.config.ts`
- `ui/src/index.css`（Tailwind 指令）
- `ui/components.json`（shadcn/ui 配置）
- `ui/src/lib/utils.ts`（`cn()` 工具函数）

**操作：**
- [ ] `npm install -D tailwindcss@^3.4 postcss autoprefixer`
- [ ] 创建 `postcss.config.js`：

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] 创建 `tailwind.config.ts`，配置 content 路径、CSS 变量模式的暗色主题色彩 token（参照 DESIGN_SYSTEM §2）
- [ ] `src/index.css` 写入 `@tailwind base; @tailwind components; @tailwind utilities;` + CSS 变量定义（亮色/暗色两套）
- [ ] `npx shadcn-ui@latest init`，选择 New York 风格、CSS variables、`src/components/ui` 路径
- [ ] 安装首批 shadcn 组件：`npx shadcn-ui@latest add button input textarea card tabs`
- [ ] 安装后续必用依赖：`npm install zustand lucide-react`
- [ ] 验证 `npm run build` 通过

**版本锁定说明：** 本项目使用 Tailwind CSS v3（非 v4）。`@tailwindcss/postcss` 是 v4 专用插件，不要安装。shadcn/ui 使用 `shadcn-ui@latest`（v3 兼容），不是 `shadcn@latest`（v4 向）。

**完成标志：** `npm run build` 无 TS 错误；`index.css` 中 CSS 变量与 DESIGN_SYSTEM 色彩体系对应；`postcss.config.js` 包含 tailwindcss + autoprefixer 插件。

---

### Step 0-3：Vite proxy 配置 📚

**修改文件：**
- `ui/vite.config.ts`

**操作：**
- [ ] 在 `vite.config.ts` 中添加 `server.proxy` 配置：

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
}
```

**完成标志：** 前端请求 `/api/xxx` 在开发时被正确代理到 `localhost:8000/xxx`。

---

### Step 0-4：API 层骨架 + Mock fallback 机制

**创建文件：**
- `ui/src/api/client.ts`
- `ui/src/api/types.ts`（共享响应类型：`TaskResult`、`InterviewStartResponse`、`InterviewAnswerResponse`、`InterviewEvaluateResponse`、`ResumeStatus`、`ResumeReport` 等）
- `ui/src/mocks/`（目录，暂为空）
- `ui/src/stores/mockMode.ts`

**操作：**
- [ ] `client.ts` 实现核心 `request<T>()` 函数：
  - 接受 `url: string` + `options: { method, body?, headers? }` 参数
  - **核心契约：** `request()` 负责 `JSON.stringify(body)` 并设置 `Content-Type: application/json`；当 body 为 `FormData` 时跳过序列化和 Content-Type（浏览器自动设置 multipart boundary）
  - 调用 `fetch(url, options)`
  - 捕获网络错误或 5xx → 设置 `useMockModeStore` 为 true → 返回对应 mock 数据
  - 检测响应 content-type 非 JSON（如收到 HTML）→ 视为 proxy 未生效，触发 mock fallback
  - 正常响应 → 解析 JSON 返回 typed 结果
  - **全局 mock 短路：** 若 `useMockModeStore.getState().isMockMode === true`，直接调用 mockFn 返回，不发起网络请求
- [ ] `mockMode.ts` 实现 Zustand store：`{ isMockMode: boolean, setMockMode: (v) => void }`
- [ ] 每个 API 函数签名预留 `mockFn` 参数，失败时调用对应 mock 函数

**流式 API 例外：** `request()` + `mockFn` 模式仅覆盖 JSON 请求/响应 API。流式端点（如 Step 3-2 的 `queryKBStream()`）使用 raw `fetch` + `ReadableStream`，不经过 `request()`。流式函数需自行实现：try/catch 网络错误 → 设置 mockMode → 调用对应 mock 流式函数；AbortController 超时控制；组件卸载时 abort。

**完成标志：** `client.ts` 导出 `request()` 函数；`useMockModeStore` 可被 import。

---

### Step 0-5：Theme store + 暗色模式基础 📚

**创建文件：**
- `ui/src/stores/theme.ts`

**操作：**
- [ ] 实现 `useThemeStore`：`{ theme: 'light' | 'dark', toggle: () => void }`
- [ ] 初始值读取 `window.matchMedia('(prefers-color-scheme: dark)')`
- [ ] `toggle()` 时切换 `document.documentElement.classList` 的 `dark` class
- [ ] 在 `main.tsx` 中初始化主题（读取系统偏好并应用）

**完成标志：** 页面 `<html>` 标签根据系统偏好自动添加/移除 `dark` class。

---

### Batch 0 Definition of Done

- [ ] `npm run dev` 启动无报错
- [ ] `npm run build` 通过（零 TS 类型错误）
- [ ] Tailwind 样式生效（可在 App.tsx 中临时加一个带 Tailwind class 的 div 验证）
- [ ] shadcn/ui Button 组件可正常渲染
- [ ] Vite proxy 配置存在（功能验证需后端运行，此处仅确认配置正确）
- [ ] `src/api/client.ts`、`src/stores/theme.ts`、`src/stores/mockMode.ts` 可被 import 无报错

---

## Batch 1：App Shell + Landing Page + JD 分析

> 目标：搭建应用外壳（Sidebar 布局）、Landing Page、第一个功能页面（JD 分析）。完成后用户可从 Landing 进入功能区并使用 JD 分析。

### Step 1-1：App Shell 布局组件 🎨

**创建文件：**
- `ui/src/components/AppLayout.tsx`
- `ui/src/components/Sidebar.tsx`
- `ui/src/components/MockBanner.tsx`

**职责：**
- `AppLayout`：顶层布局壳，包含 MockBanner（条件渲染）+ Sidebar + 内容区 `<Outlet />`
- `Sidebar`：220px 固定宽度，导航项列表 + 底部暗色切换按钮，当前路由高亮
- `MockBanner`：读取 `useMockModeStore`，mock 模式时在页面顶部显示提示条

**操作：**
- [ ] 安装路由依赖：`npm install react-router-dom`
- [ ] 创建 `Sidebar.tsx`：使用 React Router `NavLink` 渲染 6 个功能导航项（高优在上，分隔线，中优在下），底部放暗色模式切换按钮
- [ ] 创建 `MockBanner.tsx`：`useMockModeStore().isMockMode` 为 true 时渲染黄色提示条 "当前为演示模式（后端未连接）"
- [ ] 创建 `AppLayout.tsx`：flex 布局，左侧 Sidebar，右侧 `<main>` 包裹 `<Outlet />`（max-width 720px 居中）
- [ ] 验证 `npm run build` 通过

**完成标志：** 三个组件可被 import；布局结构符合 DESIGN_SYSTEM §9.2 的 ASCII 图。

---

### Step 1-2：路由配置 📚

**修改文件：**
- `ui/src/App.tsx`

**操作：**
- [ ] 在 `App.tsx` 中配置路由（`react-router-dom` 已在 Step 1-1 安装）：
  - `/` → `LandingPage`
  - `/app` → `AppLayout`（嵌套路由）
    - index → `<Navigate to="/app/jd-analyze" replace />`（默认重定向）
    - `/app/jd-analyze` → `JDAnalyzePage`
    - `/app/resume-optimize` → `ResumeOptimizePage`（暂用占位组件）
    - `/app/interview` → `InterviewPage`（暂用占位组件）
    - `/app/self-intro` → `SelfIntroPage`（暂用占位组件）
    - `/app/knowledge-base` → `KnowledgeBasePage`（暂用占位组件）
    - `/app/resume-analysis` → `ResumeAnalysisPage`（暂用占位组件）
- [ ] 未实现的页面暂时渲染 "Coming Soon" 文本
- [ ] 验证 `npm run dev` 后各路由可访问

**完成标志：** 访问 `/app/jd-analyze` 显示 AppLayout 壳 + 占位内容；Sidebar 导航点击可切换路由。

---

### Step 1-3：Landing Page 🎨

**创建文件：**
- `ui/src/features/landing/LandingPage.tsx`

**操作：**
- [ ] 实现 Landing Page：
  - Hero 区域：项目名 "Job Copilot" + 一句话定位 + "试一试" 按钮（`<Link to="/app/jd-analyze">`）
  - 技术栈展示：分组卡片（后端框架 / 数据层 / AI 能力 / 部署）
  - 右上角暗色模式切换按钮
  - 最大宽度 1080px 居中
- [ ] 验证暗色模式切换正常

**完成标志：** Landing Page 渲染项目名、技术栈卡片、"试一试"按钮；点击按钮跳转到 `/app/jd-analyze`。

---

### Step 1-4：JD 分析 — Mock 数据 + API 函数

**创建文件：**
- `ui/src/mocks/jd.ts`
- `ui/src/api/jd.ts`

**操作：**
- [ ] `mocks/jd.ts` 导出预置的 JD 分析结果：

```typescript
export const mockJDResult = {
  status: "success" as const,
  task_type: "jd_analyze",
  result: {
    hard_requirements: ["熟悉 Python 基础语法", "了解 Git 版本控制"],
    core_skills: ["Python", "Git", "Linux"],
    bonus_skills: ["Docker", "CI/CD"],
  },
  error: null,
  retriever_context: null,
  trace: null,
};
```

- [ ] `api/jd.ts` 导出 `analyzeJD(jdText: string, targetRole: string)` 函数：
  - 调用 `request<TaskResult>('/api/task', { method: 'POST', body: { task_type: 'jd_analyze', payload: { jd_text: jdText, target_role: targetRole } } })`
  - mock fallback 返回 `mockJDResult`

**完成标志：** `analyzeJD()` 函数类型正确；后端不可用时返回 mock 数据。

---

### Step 1-5：JD 分析 — 页面组件 🎨

**创建文件：**
- `ui/src/features/jd-analyze/JDAnalyzePage.tsx`
- `ui/src/components/ResultCard.tsx`
- `ui/src/components/SkeletonBlock.tsx`

**操作：**
- [ ] `SkeletonBlock.tsx`：通用骨架屏组件（脉冲动画），接受 `lines` prop 控制行数
- [ ] `ResultCard.tsx`：接受 `title: string` + `items: string[]`，渲染标题 + 标签列表
- [ ] `JDAnalyzePage.tsx`：
  - 表单：textarea（JD 文本）+ input（目标岗位）+ 提交按钮
  - 提交后调用 `analyzeJD()`，loading 期间显示 SkeletonBlock
  - 成功后渲染 3 个 ResultCard（硬性要求 / 核心技能 / 加分项）
  - 错误时显示 toast 或内联错误提示
- [ ] 手工验证：输入文本 → 提交 → 显示结果（mock 模式下）

**完成标志：** JD 分析完整流程可走通（输入 → loading → 结果卡片）；mock 模式提示条出现。

---

### Batch 1 Definition of Done

- [ ] `npm run dev` 启动无报错
- [ ] `npm run build` 通过
- [ ] Landing Page 正常渲染，"试一试"按钮跳转到功能区
- [ ] Sidebar 导航可切换路由，当前项高亮
- [ ] 暗色模式切换正常（Landing + 功能区）
- [ ] JD 分析完整流程可手工验证（输入 → 提交 → 结果展示）
- [ ] 后端不可用时自动降级到 mock，顶部显示提示条

---

## Batch 2：简历优化 + 模拟面试

> 目标：实现两个高优功能。模拟面试是前端最复杂的模块（多轮对话状态机 + 聊天 UI）。

### Step 2-1：简历优化 — Mock + API

**创建文件：**
- `ui/src/mocks/resume.ts`
- `ui/src/api/resume.ts`

**操作：**
- [ ] `mocks/resume.ts` 导出预置数据：原文 + 优化后文本
- [ ] `api/resume.ts` 导出 `optimizeResume(resumeItem: string, targetKeywords: string[], roleSummary: string)` 函数：
  - POST `/api/task`，body: `{ task_type: "resume_optimize", payload: { resume_item, target_jd_keywords, role_summary } }`
  - mock fallback 返回预置对比数据

**完成标志：** 函数类型正确，mock 降级正常。

---

### Step 2-2：简历优化 — 页面组件 🎨

**创建文件：**
- `ui/src/features/resume-optimize/ResumeOptimizePage.tsx`

**操作：**
- [ ] 实现页面：
  - 表单：textarea（简历片段）+ input（目标关键词，逗号分隔）+ input（目标岗位）+ 提交按钮
  - 提交后调用 `optimizeResume()`，loading 期间显示骨架屏
  - 成功后左右并排展示原文与优化后文本，差异处用背景色区分
- [ ] 手工验证完整流程

**完成标志：** 输入简历文本 → 提交 → 左右对比展示原文与优化结果。

---

### Step 2-3：模拟面试 — Interview Store 🏗️

**创建文件：**
- `ui/src/stores/interview.ts`

**操作：**
- [ ] 实现 `useInterviewStore`：

```typescript
interface InterviewState {
  sessionId: string | null;
  status: "idle" | "in_progress" | "completed" | "evaluated";
  messages: Array<{
    role: "system" | "user";
    content: string;
    metadata?: Record<string, any>;
  }>;
  evaluationResult: InterviewEvaluateResponse | null;
  // actions
  startSession: (sessionId: string, firstQuestion: string) => void;
  addMessage: (role: "system" | "user", content: string, metadata?: any) => void;
  setStatus: (status: InterviewState["status"]) => void;
  setEvaluation: (result: InterviewEvaluateResponse) => void;
  reset: () => void;
}
```

- [ ] `reset()` 清空所有状态，回到 idle

**完成标志：** Store 可被 import，类型正确，`reset()` 可将状态归零。

---

### Step 2-4：模拟面试 — Mock + API 🏗️

**创建文件：**
- `ui/src/mocks/interview.ts`
- `ui/src/api/interview.ts`

**操作：**
- [ ] `mocks/interview.ts` 导出：
  - `mockStartResponse`：含 session_id + 第一道题
  - `mockAnswerResponses`：3 轮回答的预置响应数组（follow_up → next_question → complete）
  - `mockEvaluateResponse`：评估报告
  - mock 模拟延迟 1~2 秒（`await new Promise(r => setTimeout(r, 1500))`）
- [ ] `api/interview.ts` 导出：
  - `startInterview(config)` → POST `/api/interview/start`
  - `submitAnswer(sessionId, answer)` → POST `/api/interview/answer`
  - `evaluateInterview(sessionId)` → POST `/api/interview/evaluate`
  - 各函数 mock fallback 使用对应 mock 数据

**完成标志：** 三个 API 函数类型正确；mock 模式下可模拟完整面试流程。

---

### Step 2-5：模拟面试 — 配置面板 + 聊天区 🎨🏗️

**创建文件：**
- `ui/src/features/interview/InterviewPage.tsx`
- `ui/src/features/interview/ConfigPanel.tsx`
- `ui/src/features/interview/ChatArea.tsx`
- `ui/src/components/ChatBubble.tsx`

**操作：**
- [ ] `ChatBubble.tsx`：接受 `role: "system" | "user"` + `content: string`
  - system 消息左对齐，浅色背景
  - user 消息右对齐，主题色背景
- [ ] `ConfigPanel.tsx`：
  - skill 选择（下拉，默认 python_backend）
  - 题目数量（number input，默认 10）
  - 追问次数（number input，默认 1）
  - "开始面试"按钮
  - 面试开始后自动折叠（`display: none` 或 height 动画）
- [ ] `ChatArea.tsx`：
  - 读取 `useInterviewStore().messages` 渲染 ChatBubble 列表
  - 底部输入框 + 发送按钮
  - 面试进行中：输入框可用；已结束：输入框禁用，显示"获取评估"按钮
  - 消息列表自动滚动到底部（`useEffect` + `scrollIntoView`）
- [ ] `InterviewPage.tsx`：组合 ConfigPanel + ChatArea，管理面试生命周期：
  - 点击"开始面试" → 调用 `startInterview()` → store.startSession()
  - 用户发送回答 → 调用 `submitAnswer()` → 根据 `action` 字段追加消息（以 API_REFERENCE / 后端实现为准：`action: "follow_up" | "next_question" | "complete"`，注意 FRONTEND_REQUIREMENTS 中的 `status: answer_ok` 为旧契约，已废弃）
  - 点击"获取评估" → 调用 `evaluateInterview()` → 显示评估报告
- [ ] 手工验证完整流程（mock 模式）

**完成标志：** 面试完整流程可走通：配置 → 开始 → 多轮问答 → 评估报告展示。

---

### Step 2-6：模拟面试 — 评估报告组件 🎨

**创建文件：**
- `ui/src/features/interview/EvaluationReport.tsx`

**操作：**
- [ ] 实现评估报告展示：
  - 总分（大字号）+ 总结评语
  - 强项 / 待改进（标签列表）
  - 逐题详情：题目、回答、分数、反馈、分类（可折叠列表）
- [ ] 在 `InterviewPage` 中，`status === "evaluated"` 时渲染此组件

**完成标志：** 评估报告渲染所有字段；逐题详情可展开/折叠。

---

### Batch 2 Definition of Done

- [ ] `npm run dev` 启动无报错
- [ ] `npm run build` 通过
- [ ] 简历优化：输入 → 提交 → 左右对比展示
- [ ] 模拟面试完整流程：配置 → 开始 → 多轮问答（含追问）→ 结束 → 评估报告
- [ ] 面试聊天 UI：系统消息左对齐、用户消息右对齐、自动滚动
- [ ] 面试结束后输入框禁用，显示"获取评估"按钮
- [ ] Mock 模式下所有功能可演示

---

## Batch 3：自我介绍 + 知识库查询 + 简历分析

> 目标：实现三个中优功能，包含 SSE 流式渲染和文件上传 + 轮询两个技术难点。

### Step 3-1：自我介绍生成 — Mock + API + 页面 🎨

**创建文件：**
- `ui/src/mocks/selfIntro.ts`
- `ui/src/api/selfIntro.ts`
- `ui/src/features/self-intro/SelfIntroPage.tsx`

**操作：**
- [ ] `mocks/selfIntro.ts`：预置一段自我介绍文本
- [ ] `api/selfIntro.ts`：`generateSelfIntro(tone, resumeItem, targetKeywords, roleSummary)` → POST `/api/task`
- [ ] `SelfIntroPage.tsx`：
  - 表单：语气选择（formal/conversational 单选）+ textarea（核心经历）+ input（目标关键词）+ input（目标岗位）+ 提交按钮
  - 结果区：渲染生成的文本 + "复制到剪贴板"按钮（`navigator.clipboard.writeText`）
- [ ] 手工验证

**完成标志：** 输入 → 提交 → 文本展示 + 复制按钮功能正常。

---

### Step 3-2：知识库查询 — SSE 流式 Mock + API 🏗️📚

**创建文件：**
- `ui/src/mocks/kb.ts`
- `ui/src/api/kb.ts`

**操作：**
- [ ] `mocks/kb.ts`：
  - 预置答案文本，`mockKBStream()` 使用 `setTimeout` 逐字输出模拟流式（每 50ms 一个字符）
  - 返回一个 async generator 或回调模式
- [ ] `api/kb.ts`：
  - `queryKB(question, collectionName?, topK?)` → POST `/api/kb/query`（同步，返回 answer + sources）
  - `queryKBStream(question, collectionName?, topK?, onChunk: (text: string) => void, onDone: () => void, onError: (err: Error) => void)` → POST `/api/kb/query/stream`
    - 使用 `fetch` + `response.body.getReader()` + `TextDecoder` 解析 SSE 事件流：按行缓冲字段（`event:`、`data:` 等），遇到空行（`\n\n`）时组装为一个完整事件再 dispatch
    - 完整事件中 `event: message` → 调用 `onChunk(data 字段值)`
    - 完整事件中 `event: done` → 调用 `onDone()`
    - 连接断开且未收到 done → 调用 `onError()`
  - mock fallback：调用 `mockKBStream()` 模拟逐字输出

**完成标志：** `queryKBStream()` 可正确解析 SSE 事件流；mock 模式下逐字回调正常。

---

### Step 3-3：知识库查询 — 页面组件 🎨

**创建文件：**
- `ui/src/features/knowledge-base/KnowledgeBasePage.tsx`
- `ui/src/components/MarkdownRenderer.tsx`

**操作：**
- [ ] 安装 markdown 渲染依赖：`npm install react-markdown remark-gfm`
- [ ] `MarkdownRenderer.tsx`：封装 `react-markdown`，应用 DESIGN_SYSTEM §17 的样式（代码块、标题、列表等）
- [ ] `KnowledgeBasePage.tsx`：
  - textarea 输入问题 + 提交按钮
  - 提交后调用 `queryKBStream()`，逐字追加到显示区域（打字机效果）
  - 流式输出期间禁用提交按钮，显示"生成中..."
  - 流结束后文本完整可选中，按钮恢复
  - 异常中断时显示"生成中断，请重试"提示
- [ ] 手工验证流式输出效果

**完成标志：** 输入问题 → 提交 → 文本逐字渲染 → 完成后可选中；中断时有错误提示。

---

### Step 3-4：简历分析 — Mock + API（含文件上传 + 轮询）

**创建文件：**
- `ui/src/mocks/resumeAnalysis.ts`
- `ui/src/api/resumeAnalysis.ts`

**操作：**
- [ ] `mocks/resumeAnalysis.ts`：
  - `mockUploadResponse`：`{ resume_id: "mock-123", status: "analyzing" }`
  - `mockStatusResponses`：模拟 pending → analyzing → completed 状态变化（3 秒后完成）
  - `mockReportResponse`：预置分析报告
- [ ] `api/resumeAnalysis.ts`：
  - `uploadResume(file: File, targetRole?: string)` → POST `/api/resume/upload`（`multipart/form-data`）
  - `getResumeStatus(resumeId: string)` → GET `/api/resume/{resumeId}/status`
  - `getResumeReport(resumeId: string)` → GET `/api/resume/{resumeId}/report`
  - `pollResumeStatus(resumeId: string, onStatusChange, onComplete, onTimeout)` → 每 2 秒轮询 status，超时 60 秒

**完成标志：** 上传函数正确构造 FormData；轮询函数在 status 变为 completed/failed 时停止。

---

### Step 3-5：简历分析 — 页面组件 🎨

**创建文件：**
- `ui/src/features/resume-analysis/ResumeAnalysisPage.tsx`

**操作：**
- [ ] 实现页面：
  - 文件上传区：`<input type="file" accept=".pdf,.docx,.txt" />` + 可选的目标岗位 input + 上传按钮
  - 上传后进入轮询状态：显示进度指示（"分析中..."脉冲动画）
  - 轮询完成（status=completed）→ 调用 `getResumeReport()` → 渲染结构化报告
  - 轮询失败（status=failed 或超时）→ 显示错误提示 + 重试按钮
- [ ] 手工验证完整流程（mock 模式）

**完成标志：** 上传文件 → 显示分析中 → 完成后展示报告；超时/失败有错误提示。

---

### Batch 3 Definition of Done

- [ ] `npm run dev` 启动无报错
- [ ] `npm run build` 通过
- [ ] 自我介绍：输入 → 生成 → 复制到剪贴板
- [ ] 知识库查询：输入 → 流式逐字渲染 → 完成；中断时有错误提示
- [ ] 简历分析：上传 → 轮询等待 → 报告展示；超时有提示
- [ ] 所有 6 个功能 + Landing Page 在 mock 模式下可完整演示

---

## 依赖关系图

```
Batch 0（骨架）
  ├── Step 0-1 → Step 0-2 → Step 0-3    [串行：后者依赖前者产物]
  ├── Step 0-4                            [依赖 0-1 + 0-2 完成（需 TS 编译 + zustand）]
  └── Step 0-5                            [依赖 0-1 + 0-2 完成，与 0-4 可并行]

Batch 1（依赖 Batch 0 全部完成）
  ├── Step 1-1 → Step 1-2                [串行：路由依赖布局壳]
  ├── Step 1-3                            [依赖 1-2，与 1-4 可并行]
  ├── Step 1-4                            [依赖 0-4，与 1-3 可并行]
  └── Step 1-5                            [依赖 1-2 + 1-4]

Batch 2（依赖 Batch 1 全部完成）
  ├── Step 2-1 → Step 2-2                [串行]
  ├── Step 2-3 → Step 2-4 → Step 2-5 → Step 2-6  [串行：面试模块内部强依赖]
  └── 2-1/2-2 与 2-3 可并行              [简历优化与面试无依赖]

Batch 3（依赖 Batch 1 完成，与 Batch 2 可并行执行）
  ├── Step 3-1                            [独立，仅依赖 api/client.ts]
  ├── Step 3-2 → Step 3-3                [串行：页面依赖 SSE API]
  ├── Step 3-4 → Step 3-5                [串行：页面依赖轮询 API]
  └── 3-1、3-2/3-3、3-4/3-5 三组可并行
```

**关键并行机会：**
- Batch 2 的简历优化（2-1/2-2）与面试模块（2-3~2-6）可由两个 agent 并行
- Batch 3 的三个功能完全独立，可由三个 agent 并行
- Batch 2 和 Batch 3 之间无依赖，理论上可并行（但建议 Batch 2 先行，因为面试模块复杂度高，早暴露问题）

---

## 关键风险与规避策略

### 风险 1：SSE 流式解析

**场景：** 知识库查询 `/api/kb/query/stream` 使用 SSE，需逐行解析事件流。

**风险点：**
- 连接中途断开（网络波动、后端崩溃）时未收到 `event: done`，前端卡在"生成中"状态
- `ReadableStream` 的 chunk 边界不一定对齐 SSE 事件边界（一个 chunk 可能包含半行）

**规避策略：**
- 使用 `TextDecoder` + 行缓冲区：累积 chunk 直到遇到 `\n`，按行缓冲字段（`event:`、`data:` 等）；遇到空行（`\n\n`）时将已缓冲字段组装为一个完整 SSE 事件再 dispatch。注意：单个 `\n` 分隔同一事件内的字段，`\n\n` 才是事件边界。
- 设置 30 秒无数据超时：如果 30 秒内未收到任何 chunk，主动 abort 并提示用户
- `reader.read()` 返回 `done: true` 且未收到 `event: done` → 视为异常终止，显示"生成中断，请重试"
- Mock 模式使用 `setTimeout` 逐字模拟，不依赖真实 SSE

---

### 风险 2：文件上传 + 轮询

**场景：** 简历分析需要上传文件后轮询状态直到完成。

**风险点：**
- 轮询无限循环（后端永远不返回 completed/failed）
- 用户离开页面后轮询继续执行，浪费资源
- 上传大文件时无进度反馈

**规避策略：**
- 硬性超时 60 秒：超时后停止轮询，显示"分析超时，请重试"
- 使用 `useEffect` cleanup 或 `AbortController` 在组件卸载时取消轮询
- 轮询间隔 2 秒（API_REFERENCE 规定）
- 文件大小前端校验（限制 10MB），超出时阻止上传并提示
- Mock 模式模拟 3 秒后完成，不做真实轮询

---

### 风险 3：面试 Session 状态管理

**场景：** 面试是多轮对话，session_id 必须贯穿整个流程。

**风险点：**
- 页面刷新后 Zustand store 清空，session_id 丢失，后续请求 404
- 用户在面试进行中切换到其他页面再回来，状态丢失
- Redis TTL 2 小时，长时间不操作后 session 过期

**规避策略：**
- 页面刷新/session 丢失时：检测 `sessionId === null && status !== "idle"` → 重置为 idle，显示"面试已中断，请重新开始"
- 不做 session 持久化（localStorage）——需求文档明确"session 数据丢失需处理降级"，不是"需要恢复"
- 面试进行中离开页面：不阻止，但回来时如果 store 已清空则提示重新开始
- 每次 API 调用检查 404 响应 → 如果 session 不存在，重置状态并提示

---

### 风险 4：Mock Fallback 全局提示条

**场景：** 后端不可用时自动降级到 mock 数据，需全局感知。

**风险点：**
- 单个请求失败就切换到 mock 模式，但可能只是暂时性错误
- mock 模式一旦激活，后续所有请求都走 mock，即使后端已恢复
- 提示条遮挡内容

**规避策略：**
- 触发条件：网络错误（`TypeError: Failed to fetch`）或 HTTP 5xx → 切换到 mock
- 不做自动恢复：一旦进入 mock 模式，本次会话保持（刷新页面重置）。理由：避免真实/mock 数据混合导致状态不一致
- 提示条使用固定定位在页面最顶部，高度 32px，不遮挡功能区内容（功能区 padding-top 补偿）
- 400 错误（业务错误）不触发 mock 降级——这是正常的业务响应

---

### 风险 5：`/api` Proxy Strip（开发 vs 部署环境差异）

**场景：** 前端统一使用 `/api/xxx` 路径，开发时 Vite proxy strip 前缀，部署时 Nginx strip。

**风险点：**
- 开发时忘记配置 proxy，请求直接打到 Vite dev server 返回 HTML
- 部署时 Nginx rewrite 规则错误，后端收到带 `/api` 前缀的路径
- SSE 端点在 Nginx 默认配置下被缓冲，流式变成一次性吐出

**规避策略：**
- `vite.config.ts` 中 proxy rewrite 规则：`path.replace(/^\/api/, '')` — 确保 strip 干净
- 前端代码中绝对禁止硬编码 `http://localhost:8000` 或任何域名，统一用 `/api/...`
- `client.ts` 中所有请求路径必须以 `/api/` 开头，加断言检查（开发模式下）
- 部署文档（已有）明确 Nginx 配置：`proxy_buffering off` 对整个 `/api/` location 生效
- 开发时如果 proxy 未生效（收到 HTML 响应），`client.ts` 检测 content-type 非 JSON → 触发 mock fallback 而非崩溃

---

## Skill 使用指南

执行本计划时，以下 skill 是**必须调用**的，不是可选建议。

### 🎨 `frontend-design:frontend-design`

**适用步骤：** 1-1、1-3、1-5、2-2、2-5、2-6、3-1、3-3、3-5（所有创建 UI 组件/页面的步骤）

**调用时机：** 开始编写 JSX/TSX 组件代码之前。

**输入约束：** 调用时必须将 `DESIGN_SYSTEM.md` 的相关章节作为上下文提供给 skill，确保：
- 色彩使用 CSS 变量（§2 色彩体系）
- 间距遵循 4px 网格（§4）
- 组件样式符合规范（§6 按钮/输入框/聊天气泡/卡片等）
- 动效使用 `transition-all duration-200`（§7）
- Landing Page 遵循 §9.1，功能区遵循 §9.2

**注意：** 此 skill 强调"大胆的美学方向"和"避免 AI 通用审美"。但本项目已有明确的设计规范（DESIGN_SYSTEM.md），执行时以设计规范为准，skill 的创意自由度限定在规范允许的范围内（如图标选择、微交互细节、空状态插画风格等）。

---

### 🏗️ `feature-dev:feature-dev`

**适用步骤：** 2-3~2-6（模拟面试整体模块）、3-2（SSE 流式解析）

**调用时机：** 开始实现该功能模块之前，作为整体流程启动。

**为什么这些步骤需要：**
- 模拟面试：多轮对话状态机 + 3 个 API 端点协作 + 聊天 UI + 评估报告，是前端最复杂的模块。需要 feature-dev 的 Architecture Design 阶段来对比实现方案（如消息列表用 store 还是 useReducer、配置面板折叠用 CSS 还是条件渲染等）。
- SSE 流式：涉及 ReadableStream + TextDecoder + 行缓冲 + 超时处理，实现细节多，需要 Codebase Exploration 阶段确认 `client.ts` 的 mock fallback 如何与流式 API 协作。

**简化使用：** 对于这些步骤，feature-dev 的 Phase 1（Discovery）和 Phase 3（Clarifying Questions）可以跳过——需求已在本计划中完全定义。直接从 Phase 2（Codebase Exploration）开始，重点关注 Phase 4（Architecture Design）。

---

### 📚 `context7`（MCP tool: `resolve-library-id` → `query-docs`）

**适用步骤：** 0-1、0-2、0-3、0-5、1-2、3-2

**调用时机：** 遇到以下情况时必须查文档，不凭记忆：
- Vite 配置项（`server.proxy` 的 rewrite 语法、`build` 选项）
- Tailwind CSS v4 配置（如果版本有变化）
- shadcn/ui 初始化命令和 `components.json` 结构
- React Router v6 的 `createBrowserRouter` / `<Outlet>` 用法
- Zustand 的 `create()` API 和 persist middleware
- Web Streams API（`ReadableStream`、`TextDecoder`）用于 SSE 解析

**调用方式：**
1. 先调用 `resolve-library-id`（如 `libraryName: "Vite"`）获取 library ID
2. 再调用 `query-docs`（如 `query: "server proxy configuration rewrite"`）获取具体配置

---

### 不需要 Skill 的步骤

以下步骤是纯数据/逻辑层，不涉及 UI 设计或复杂架构决策，直接按计划实现即可：
- Step 0-4（API client 骨架）
- Step 1-4（JD 分析 mock + API 函数）
- Step 2-1（简历优化 mock + API）
- Step 3-4（简历分析 mock + API + 轮询逻辑）
