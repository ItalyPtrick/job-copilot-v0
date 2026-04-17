# 项目总览与技术路线图

job-copilot-v0 是一个基于 Python + FastAPI + LLM 的求职 AI 助手平台，参考 [interview-guide](https://github.com/Snailclimb/interview-guide) 的功能设计，用 Python 生态重新实现并扩展。

---

## 1. 项目现状

### 已完成

| 能力 | 实现方式 | 关键文件 |
|---|---|---|
| 统一任务入口 | `POST /task` + Orchestrator 分发 | `app/main.py`, `app/orchestrators/job_copilot_orchestrator.py` |
| LLM 调用 | OpenAI SDK（支持 tool calling） | `app/services/llm_service.py` |
| 工具注册/执行 | 自研 Tool Registry | `app/tools/register.py`, `app/tools/schemas.py` |
| Trace 记录 | 每次请求附带完整执行轨迹 | `app/types/trace_event.py` |
| Prompt 模板 | Markdown 文件加载 | `app/services/prompt_service.py`, `app/prompts/*.md` |
| 3 个基础任务 | JD 分析、简历优化、自我介绍生成 | `app/prompts/jd_analyze.md` 等 |
| RAG 预留 | RetrieverContext 数据模型已定义 | `app/types/retriever_context.py` |
| 前端 | Streamlit 极简 Demo | `ui/minimal_app.py` |

### 待建设（参考 interview-guide）

| 功能 | 对应文档 | 优先级 |
|---|---|---|
| 数据持久化（数据库 + 缓存） | `01-database-and-persistence.md` | ★★★ 前置依赖 |
| RAG 知识库（向量检索 + 流式问答） | `02-rag-knowledge-base.md` | ★★★ |
| 模拟面试（出题 + 追问 + 评估 + 面试安排） | `03-mock-interview.md` | ★★★ |
| 简历智能分析（多格式解析 + 异步处理 + 报告导出） | `04-resume-analysis.md` | ★★ |
| 语音面试（WebSocket + ASR/TTS） | `05-voice-interview.md` | ★ 进阶 |
| Docker 部署 | `06-deployment.md` | ★★ 收尾 |

---

## 2. 技术栈映射

interview-guide 用 Java 生态实现，我们用 Python 生态的对等方案：

| 层 | interview-guide (Java) | job-copilot-v0 (Python) | 选择理由 |
|---|---|---|---|
| **后端框架** | Spring Boot 4.0 | FastAPI + Uvicorn | 异步原生，Python AI 生态首选 |
| **AI 框架** | Spring AI | OpenAI SDK + LangChain | Python 是 AI 应用的一等公民，库最丰富 |
| **数据库** | PostgreSQL + JPA | SQLite（初期）→ PostgreSQL + SQLAlchemy 2.0 | 渐进式，SQLite 零配置启动 |
| **向量存储** | pgvector | ChromaDB（初期）→ pgvector（进阶） | ChromaDB 嵌入式零依赖，适合快速迭代 |
| **数据库迁移** | JPA ddl-auto | Alembic | Python ORM 标准迁移工具 |
| **缓存/队列** | Redis + Redis Stream | Redis-py + Celery（或 asyncio） | Celery 是 Python 异步任务事实标准 |
| **对象存储** | RustFS (S3 兼容) | 本地文件系统（初期）→ MinIO | 初期不引入额外组件 |
| **前端** | Vite + React + TypeScript | Streamlit（Phase 1-2）→ React（Phase 3） | 先聚焦后端 AI 逻辑 |
| **WebSocket** | Spring WebSocket | FastAPI WebSocket | 框架内置支持 |
| **ASR/TTS** | 阿里云千问3 语音模型 | OpenAI Whisper + edge-tts | 开源方案，成本低 |
| **PDF 导出** | iText | ReportLab / WeasyPrint | Python PDF 生态成熟 |
| **测试** | JUnit | pytest | 已在用 |
| **部署** | Docker Compose | Docker Compose | 一致 |
| **构建工具** | Gradle | pip + requirements.txt | 一致 |

---

## 3. 目标架构

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit / React                  │
│              (前端 - 多页面应用)                       │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP / SSE / WebSocket
┌───────────────────────▼─────────────────────────────┐
│                    FastAPI                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ /task    │ │ /kb      │ │/interview│ │/resume │ │
│  │(现有)    │ │(知识库)  │ │(模拟面试)│ │(简历)  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │            │            │            │      │
│  ┌────▼────────────▼────────────▼────────────▼────┐ │
│  │              Orchestrator 层                    │ │
│  │  (任务分发 + Trace 记录 + 错误处理)             │ │
│  └────┬────────────┬────────────┬────────────┬────┘ │
│       │            │            │            │      │
│  ┌────▼────┐ ┌─────▼────┐ ┌────▼─────┐ ┌───▼────┐ │
│  │LLM 服务│ │RAG 检索  │ │Tool 注册 │ │文件处理│ │
│  │(OpenAI) │ │(向量+BM25)│ │(已有)    │ │(PDF等) │ │
│  └────┬────┘ └─────┬────┘ └──────────┘ └───┬────┘ │
└───────┼────────────┼────────────────────────┼──────┘
        │            │                        │
┌───────▼────┐ ┌─────▼──────┐ ┌──────────────▼──────┐
│  OpenAI    │ │ ChromaDB / │ │    PostgreSQL /     │
│  API       │ │ pgvector   │ │    SQLite + Redis   │
└────────────┘ └────────────┘ └─────────────────────┘
```

---

## 4. 实施路线图

### Phase 1：基础设施 + RAG（第 1-2 周）

**目标：** 项目从"纯内存骨架"进化为"有数据库 + 能做向量检索"

| 周 | 任务 | 产出 |
|---|---|---|
| 第 1 周前半 | SQLite + SQLAlchemy 模型定义 + Alembic 迁移 | 数据可持久化 |
| 第 1 周后半 | Redis 集成（session 缓存） | 面试会话可缓存 |
| 第 2 周前半 | 文档上传 → 分块 → 向量化流水线 | RAG 核心管道 |
| 第 2 周后半 | 检索增强问答 + SSE 流式响应 | RAG 知识库可用 |

### Phase 2：核心 AI 功能（第 3-4 周）

**目标：** 实现最有面试价值的两个模块

| 周 | 任务 | 产出 |
|---|---|---|
| 第 3 周 | 模拟面试：session 管理 + skill 出题 + 多轮追问 + 评估引擎 | 模拟面试可用 |
| 第 3 周末 | 面试安排：邀请解析 + 日历管理 | 面试安排可用 |
| 第 4 周前半 | 简历分析：多格式解析 + 异步处理 | 简历解析可用 |
| 第 4 周后半 | 简历分析：PDF 报告导出 + 重试机制 | 完整简历分析 |

### Phase 3：部署 + 完善 + 面试准备（第 5-6 周）

**目标：** 项目可演示、可部署、面试准备就绪

| 周 | 任务 | 产出 |
|---|---|---|
| 第 5 周前半 | Docker Compose 部署（API + Worker + PG + Redis） | 一键启动完整环境 |
| 第 5 周后半 | Streamlit 前端完善（多页面、完整交互流程） | 可演示的 UI |
| 第 6 周前半 | 集成测试 + Bug 修复 + 性能优化 | 项目稳定可靠 |
| 第 6 周后半 | 面试展示文档 + 项目 README 更新 + 架构图 | 面试准备就绪 |

> 第 6 周结束后开始投递简历。

### 加分项：语音面试（投递简历后并行开发）

**目标：** 边面试边迭代，为项目持续增加亮点

| 任务 | 产出 |
|---|---|
| WebSocket + ASR（Whisper）+ TTS（edge-tts）集成 | 语音面试原型 |
| 复用文字面试的出题/评估引擎 | 语音面试可用 |

> 语音面试是独立模块，不影响已有功能。面试中可以讲"我设计了 WebSocket + ASR/TTS 的语音面试架构"，即使未完成 demo 也有面试加分。

---

## 5. 关键技术决策记录

> 面试时常问"你为什么选这个技术"，以下是每个决策的理由，确保你能讲清楚。

### 为什么用 FastAPI 而不是 Flask/Django？
- **异步原生**：FastAPI 基于 ASGI，天然支持 async/await，适合 LLM 流式调用和 WebSocket
- **自动文档**：内置 Swagger UI，API 即文档
- **类型安全**：与 Pydantic 深度集成，请求/响应自动校验

### 为什么先用 ChromaDB 而不是直接上 pgvector？
- **零依赖启动**：ChromaDB 嵌入式运行，不需要安装 PostgreSQL
- **开发效率**：本地文件存储，重启不丢数据，适合快速迭代
- **迁移成本低**：后期切换到 pgvector 只需改存储后端，检索逻辑不变

### 为什么先用 SQLite 再切 PostgreSQL？
- **渐进式**：SQLite 零配置，项目初期不需要装额外服务
- **SQLAlchemy 抽象**：切换数据库只改连接字符串，业务代码不变
- **面试加分**：能展示"我考虑了渐进式架构演进"

### 为什么选 Celery 做异步任务？
- **Python 事实标准**：最成熟的分布式任务队列
- **与 Redis 天然集成**：broker + backend 都用 Redis
- **重试/监控**：内置重试机制和 Flower 监控面板
- **面试可讲**：比 asyncio 更有工程深度

### 为什么前端先用 Streamlit？
- **时间约束**：1-3 个月内找实习，前端不是核心竞争力
- **AI 应用面试惯例**：Streamlit 在 AI demo 中非常普遍，面试官不会扣分
- **快速验证**：几十行代码就能搭出可交互的 UI
- **后期可换**：核心是后端 API，前端随时可以切换到 React

---

## 6. 文档间的依赖关系

```
00-roadmap (本文档，全局参考)
    │
    ├─→ 01-database-and-persistence (所有模块的前置)
    │       │
    │       ├─→ 02-rag-knowledge-base (依赖数据库存储文档元数据)
    │       │
    │       ├─→ 03-mock-interview (依赖数据库存储面试记录, 依赖 Redis 缓存 session)
    │       │
    │       └─→ 04-resume-analysis (依赖数据库存储分析结果, 依赖 Celery 异步)
    │
    ├─→ 06-deployment (所有核心功能完成后)
    │
    ├─→ 07-interview-showcase (最后编写，汇总所有模块的面试要点)
    │
    └─→ 05-voice-interview (加分项，投递简历后并行开发，依赖 03 的评估引擎)
```
