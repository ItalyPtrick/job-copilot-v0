# W2 日计划概览（Doc 02：RAG 知识库）

每天 3-4 小时。学习内容对应 Doc 02 的"概念学习"章节，编码任务对应"分步实现方案"的 Step。

| 天 | 学习内容（概念/原理） | 编码任务（对应 Doc 02 的 Step） | 产出物 |
|:---:|---|---|---|
| **D1** | RAG 概念、RAG vs Fine-tuning、Embedding 原理、分块策略（Doc 02 §1 前 4 节："什么是 RAG" ~ "文档分块策略"） | **Step 1**：安装 `langchain`, `chromadb` 等依赖并更新 `requirements.txt`；创建 `app/modules/knowledge_base/vector_store.py`（ChromaDB 封装：`get_vector_store` / `add_documents` / `search`） | 依赖已安装；`python -c "from app.modules.knowledge_base.vector_store import get_vector_store; print('OK')"` 输出 OK |
| **D2** | 向量数据库对比、检索策略（Doc 02 §1 后 2 节："向量数据库对比" + "检索策略"） | **Step 2**：创建 `app/modules/knowledge_base/document_loader.py`（多格式加载 PDF/DOCX/TXT/MD + RecursiveCharacterTextSplitter 分块） | `python -c "from app.modules.knowledge_base.document_loader import load_and_split; print('OK')"` 输出 OK；用测试 txt 文件验证分块数 > 1 |
| **D3** | LangChain LCEL 链组合（prompt \| llm \| parser 的管道语法） | **Step 3**：创建 `app/modules/knowledge_base/rag_chain.py`（`rag_query` 非流式 + `rag_query_stream` SSE 流式） | `rag_query("default", "测试问题")` 能返回 `{"answer": ..., "sources": [...]}` |
| **D4** | FastAPI 文件上传（`UploadFile`）+ SSE 流式响应（`sse-starlette`） | **Step 4 + Step 5**：创建 `router.py`（4 个路由 + 错误处理）；修改 `main.py` 注册 `/kb` 路由 | 已完成并手工验证：`/kb/upload`、`/kb/query`、`/kb/query/stream`、`/kb/collections` 可用；当前来源展示先做到弱追溯 |
| **D5** | 无新概念，专注幂等重构与集成 | **Step 6** + 上传幂等改造：`UniqueConstraint` + `updated_at` + 两阶段 commit + reused 短路 + 409 并发 + Orchestrator `_build_retriever_context` 注入 + 测试 25 passed | ✅ 全部完成 |
| **D6** | 无新概念，专注测试 | 编写 `tests/test_rag_chain.py`（RAG 问答链相关测试）+ `tests/test_kb_api.py`（知识库接口集成测试）；补知识库接口与迁移验证 | 待完成：运行真实测试文件并完成知识库接口测试与数据库迁移验证；`knowledge_documents` 表字段与模型一致 |
| **D7** | 面试复习（Doc 02 §6 全部 5 个问题）+ 进阶探索（混合检索 BM25+向量、Reranking Cross-Encoder 概念，只看原理不写代码） | 端到端验证：用自己的 `docs/*.md` 文件上传→查询→流式返回；清理代码 | 完整流程跑通；能回答 Doc 02 §6 的 5 个面试问题；了解混合检索/Reranking 的概念和面试怎么讲 |
