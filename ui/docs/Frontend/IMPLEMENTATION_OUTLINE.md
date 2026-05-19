# 前端执行轮廓

> 目标读者：下一位负责写执行计划的 agent。
> 性质：需求文档和执行计划之间的最小桥接，不是实现细节说明书。

---

## 1. 先读顺序

1. `FRONTEND_REQUIREMENTS.md`
2. `API_REFERENCE.md`
3. `DESIGN_SYSTEM.md`
4. `DEPLOYMENT_REQUIREMENTS.md`

---

## 2. 模块边界

| 模块 | 职责 | 对外导出 | 依赖 |
|------|------|----------|------|
| `src/api/` | 所有后端请求封装，统一 `/api/*` 前缀、错误兜底、mock fallback | 每个功能一个 typed async 函数（如 `analyzeJD()`, `startInterview()`） | `src/mocks/` |
| `src/mocks/` | 每个功能一份静态 mock 数据 | JSON 对象，结构与后端响应一致 | 无 |
| `src/stores/` | Zustand 全局状态 | `useThemeStore`, `useInterviewStore`, `useMockModeStore` | 无 |
| `src/features/` | 按功能拆分的页面逻辑组件 | 每个功能一个目录，含页面组件 + 局部子组件 | `src/api/`, `src/stores/`, `src/components/` |
| `src/components/` | 跨功能复用的 UI 组件（ChatBubble, ResultCard, Skeleton 等） | React 组件 | 无（纯展示） |

**依赖方向：** `features/` → `api/` → `mocks/`；`features/` → `stores/`；`features/` → `components/`。反向依赖禁止。

---

## 3. 路由/页面

- `/`：Landing Page
- `/app/jd-analyze`
- `/app/resume-optimize`
- `/app/interview`
- `/app/self-intro`
- `/app/knowledge-base`
- `/app/resume-analysis`

---

## 4. 推荐交付顺序

### Batch 1

- 项目初始化
- Landing Page
- JD 分析

### Batch 2

- 简历优化
- 模拟面试

### Batch 3

- 自我介绍生成
- 知识库查询（含 SSE）
- 简历分析

---

## 5. 执行时的固定约束

- 所有真实请求统一走 `/api/*`
- 后端失败时自动降级到 mock
- 暗色模式默认跟随系统偏好
- 只做桌面端演示，不补移动端适配

