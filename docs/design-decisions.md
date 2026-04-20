# 设计决策笔记

> 项目开发过程中的技术选型、架构权衡、踩坑解决记录。面试前回顾此文件。

---

### W2-D1 RAG 基础设施选型
- **问题**：W2 需要尽快打通知识库索引、检索和后续生成链路，先确定 RAG 基础设施选型。
- **方案**：使用 `langchain + langchain-openai + chromadb` 作为当前阶段的 RAG 底座。
- **理由**：`langchain` 提供统一的 `Document`、`splitter`、`retriever` 抽象，便于 D2-D4 持续复用；`langchain-openai` 能直接接入现有 OpenAI 兼容环境变量；`chromadb` 支持本地持久化，部署和调试成本低，比一开始上 `PGVector` / `Elasticsearch` 更适合当前学习和原型阶段。

### W2-D1 知识库模块边界
- **问题**：W2 后续会连续扩展向量存储、文档加载、RAG chain 和接口层，需要先固定知识库相关代码的边界。
- **方案**：新增 `app/modules/knowledge_base/` 作为知识库能力模块，先创建模块目录和 `__init__.py`，并将 `data/chroma/`、`data/uploads/` 加入 `.gitignore`。
- **理由**：按业务能力收口比把代码分散到 `services/`、`tools/` 更清晰，也能提前隔离向量索引和上传文件等本地产物，避免后续职责混乱和误提交。

### W2-D1 百炼 Embedding 兼容性适配
- **问题**：阿里云百炼兼容 embeddings 接口与 `langchain_openai` 默认的 token 预切分输入不完全兼容，快速验证时写入 Chroma 失败。
- **方案**：保留百炼兼容接口与 `text-embedding-v4`，在 `OpenAIEmbeddings` 初始化中设置 `check_embedding_ctx_length=False`。
- **理由**：当前项目在上游已经做文档切块，embedding 输入本就应为小块字符串；关闭客户端 token 预切分不影响当前基础 RAG 链路，却能以最小改动适配百炼兼容接口。