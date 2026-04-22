# 项目包装：简历项目经历

面向 **AI 应用开发** 岗位，提供两个版本：完整版（假设除语音模块外全部完成）和现实版（当前 W2-D4 进度）。

---

## 版本 A：完整版（除语音模块外全部完成）

### 作品简介

> 独立设计开发了一个基于 Python + FastAPI + LLM 的求职 AI 助手平台，实现了 RAG 知识库问答、AI 模拟面试、简历智能分析三大核心模块，采用 Orchestrator 模式统一调度任务，Docker Compose 一键部署。

### 简历项目经历

```
求职 AI 助手平台 | Python · FastAPI · LangChain · OpenAI · Docker
──────────────────────────────────────────────────────────────
- 设计并实现 RAG 知识库问答系统，支持 PDF/DOCX/TXT/MD 四种格式文档上传，
  使用 RecursiveCharacterTextSplitter 进行语义分块（500字/100重叠），
  OpenAI Embedding 向量化后存入 ChromaDB，通过 top-5 相似度检索 + SSE 流式输出实现实时问答

- 实现 AI 模拟面试引擎，基于 Skill 定义文件驱动结构化出题，
  支持多轮智能追问（Redis 缓存面试 session），
  采用分批评估 + Structured Output 架构生成面试报告（评分 + 亮点 + 改进建议）

- 使用 Celery + Redis 实现简历异步分析管道，支持多格式简历解析 + LLM 智能分析，
  通过内容哈希（SHA256）实现幂等去重，支持最多 3 次自动重试，PDF 报告导出

- 设计 Orchestrator 统一任务调度架构，所有任务经 POST /task 统一入口分发，
  支持 LLM 直接调用和 Tool Calling 两种模式，
  全链路 Trace 记录（节点名 + 状态 + 时间戳）便于调试和监控

- 基于 SQLAlchemy 2.0 + Alembic 构建数据持久化层，
  SQLite 开发 / PostgreSQL 生产的渐进式架构，Redis 缓存面试会话（TTL 2h 自动过期）

- 采用 Docker Compose 编排 4 个服务（FastAPI + Celery Worker + PostgreSQL + Redis），
  healthcheck 确保启动顺序，Volume 挂载持久化数据，一键部署可演示
```

---

## 版本 B：现实版（当前进度：W2-D4）

### 作品简介

> 独立设计开发了一个基于 Python + FastAPI + LLM 的求职 AI 助手平台，已实现数据持久化层和 RAG 知识库核心管道（文档上传→分块→向量化→检索增强问答），采用 Orchestrator 模式统一调度任务，全链路 Trace 记录。

### 简历项目经历

```
求职 AI 助手平台（开发中） | Python · FastAPI · LangChain · OpenAI · ChromaDB
──────────────────────────────────────────────────────────────
- 设计并实现 RAG 知识库核心管道，支持 PDF/DOCX/TXT/MD 四种格式文档加载，
  使用 RecursiveCharacterTextSplitter 进行语义分块（500字/100重叠），
  OpenAI Embedding 向量化后存入 ChromaDB，实现 top-5 相似度检索 + LangChain LCEL 链式问答

- 基于 LangChain 实现流式与非流式双模式 RAG 问答链，
  非流式 chain.invoke() 用于同步场景，异步 chain.astream() 用于 SSE 流式输出，
  检索结果附带来源引用（文件名 + 分块索引）

- 设计 Orchestrator 统一任务调度架构，所有任务经 POST /task 统一入口分发，
  支持 LLM 直接调用和 Tool Calling 两种模式，
  全链路 Trace 记录（节点名 + 状态 + 时间戳）便于调试和监控

- 基于 SQLAlchemy 2.0 + Alembic 构建数据持久化层，
  实现 TaskRecord 等模型的 ORM 映射和自动迁移，
  Redis 集成用于会话缓存（set/get/delete + TTL），pytest 覆盖数据库和缓存的单元测试
```

---

## 包装原则备注

1. **只写真实实现的功能**——版本 B 不提模拟面试、简历分析、Docker 部署（尚未开始）
2. **量化用合理数据**——"4 种格式"、"top-5 检索"、"500 字分块"都来自实际代码参数
3. **每条 bullet 面试能展开 2 分钟**——技术选型理由、遇到的问题、优化方向都能讲
4. **版本 B 随施工推进更新**——每完成一个模块，把对应 bullet 从版本 A 搬过来
5. **不写"熟悉/了解"**——简历写的是你"做了什么"，而非"学了什么"
