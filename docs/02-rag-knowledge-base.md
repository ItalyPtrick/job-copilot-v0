# RAG 知识库模块

本模块实现检索增强生成（RAG）知识库，让 AI 基于用户上传的文档内容回答问题，而非纯依赖 LLM 的预训练知识。这是 AI 应用面试中最常被考察的技术。

---

## 1. 概念学习

### 什么是 RAG？

**RAG（Retrieval-Augmented Generation，检索增强生成）** 是一种结合信息检索和文本生成的架构：

```
用户问题 → 检索相关文档片段 → 将文档片段 + 问题一起发给 LLM → LLM 基于真实文档生成回答
```

**为什么需要 RAG？**
- **解决幻觉**：LLM 会编造不存在的信息，RAG 让回答有据可查
- **知识更新**：LLM 的训练数据有截止日期，RAG 可以检索最新文档
- **私有数据**：企业/个人文档不在 LLM 训练集中，必须通过检索注入
- **成本低于 Fine-tuning**：不需要重新训练模型，只需管理文档

### RAG vs Fine-tuning

| 维度 | RAG | Fine-tuning |
|---|---|---|
| 适用场景 | 知识库问答、文档检索 | 风格/格式定制、特定领域深度理解 |
| 数据更新 | 实时更新文档即可 | 需要重新训练 |
| 成本 | 低（只需向量数据库） | 高（GPU + 训练时间） |
| 可解释性 | 高（可展示检索来源） | 低 |
| 本项目选择 | ✅ 选 RAG | ❌ 不适合 |

### Embedding（向量嵌入）

Embedding 是将文本转换为高维向量的过程，语义相似的文本在向量空间中距离更近：

```
"Python 是一种编程语言" → [0.12, -0.34, 0.56, ..., 0.78]  (1536维)
"Python is a programming language" → [0.11, -0.33, 0.55, ..., 0.77]  (相似！)
"今天天气很好" → [0.89, 0.12, -0.67, ..., 0.23]  (不同方向)
```

**常用 Embedding 模型：**

| 模型 | 维度 | 优缺点 |
|---|---|---|
| OpenAI text-embedding-3-small | 1536 | 质量好，需要 API Key，有费用 |
| OpenAI text-embedding-3-large | 3072 | 质量最好，费用更高 |
| BAAI/bge-small-zh-v1.5 | 512 | 中文优秀，开源免费，本地运行 |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 英文通用，开源免费 |

**本项目选择：** 先用 OpenAI Embedding（简单可靠），后续可换开源模型降低成本。

### 文档分块策略

长文档需要切分成小块再向量化，分块策略直接影响检索质量：

| 策略 | 描述 | 优缺点 |
|---|---|---|
| **固定长度分块** | 按字符/token 数切割（如每 500 字） | 简单但可能切断语义 |
| **递归字符分块** | 先按段落 → 句子 → 字符逐级切割 | LangChain 默认，兼顾语义和长度 |
| **语义分块** | 用 Embedding 相似度判断分割点 | 质量最好但计算成本高 |
| **Markdown Header 分块** | 按标题层级切割 | 适合结构化文档 |

**本项目选择：** 递归字符分块（`RecursiveCharacterTextSplitter`），chunk_size=500, overlap=100。

### 向量数据库对比

| 数据库 | 类型 | 优缺点 | 适用场景 |
|---|---|---|---|
| **ChromaDB** | 嵌入式 | 零配置，Python 原生，单文件存储 | 开发/小规模 |
| **pgvector** | PostgreSQL 扩展 | 复用现有 PG，支持 SQL 过滤 | 生产环境 |
| **FAISS** | 内存库 | 速度最快，但不持久化 | 大规模检索 |
| **Milvus** | 独立服务 | 功能最全，但部署复杂 | 企业级 |

**本项目选择：** ChromaDB（初期）→ pgvector（Phase 3 切 PostgreSQL 后迁移）。

### 检索策略

| 策略 | 描述 | 适用场景 |
|---|---|---|
| **相似度搜索** | 返回与查询向量最近的 top-k 个文档 | 通用 |
| **MMR（最大边际相关）** | 在相关性和多样性之间平衡 | 避免返回重复内容 |
| **混合检索** | 向量检索 + BM25 关键词检索 | 兼顾语义和精确匹配 |

**本项目选择：** 先用相似度搜索，后续添加 MMR。

---

## 2. 技术选型

| 组件 | 选择 | 版本 | 理由 |
|---|---|---|---|
| RAG 框架 | LangChain | 0.2+ | 社区最大，文档最全，面试官最熟 |
| 向量数据库 | ChromaDB | 0.5+ | 嵌入式零依赖，开发效率高 |
| Embedding | OpenAI text-embedding-3-small | — | 质量好，接口简单 |
| 文档加载 | LangChain Document Loaders | — | 支持 PDF/DOCX/MD/TXT |
| 文本分块 | RecursiveCharacterTextSplitter | — | LangChain 内置，兼顾语义 |
| 流式响应 | sse-starlette | 2.0+ | FastAPI SSE 支持 |

**新增依赖：**
```
langchain>=0.2
langchain-openai>=0.1
langchain-community>=0.2
chromadb>=0.5
sse-starlette>=2.0
pymupdf>=1.24       # PDF 解析
python-docx>=1.1    # DOCX 解析
```

---

## 3. 与现有代码的集成点

### 新增文件

```
app/
├── modules/
│   └── knowledge_base/
│       ├── __init__.py
│       ├── router.py           # FastAPI 路由（/kb）
│       ├── vector_store.py     # ChromaDB 封装
│       ├── document_loader.py  # 文档加载与分块
│       └── rag_chain.py        # RAG 问答链
├── database/models/
│   └── knowledge.py            # 知识库上传记录 SQLAlchemy 模型
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 注册 `/kb` 路由蓝图 |
| `app/types/retriever_context.py` | 已有！RAG 检索结果填入此结构 |
| `app/orchestrators/job_copilot_orchestrator.py` | 预留 RAG 上下文注入扩展点，当前仍待完成 |
| `requirements.txt` | 添加 langchain, chromadb 等 |
| `.env` | 确认聊天模型读取 `OPENAI_*`，Embedding 读取 `OPENAI_EMBEDDING_*` |

### 关键集成：RetrieverContext

你已经定义了 `RetrieverContext` 和 `RetrieverChunk`（`app/types/retriever_context.py`），RAG 检索结果直接填入：

```python
# 当前 TaskResult 已有 retriever_context 字段
class TaskResult(BaseModel):
    retriever_context: Optional[RetrieverContext] = None  # ← 这里接 RAG 结果
```

---

## 4. 分步实现方案

### Step 1：ChromaDB 向量存储封装

`app/modules/knowledge_base/vector_store.py`：

```python
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

CHROMA_DIR = "./data/chroma"
embeddings = OpenAIEmbeddings(
    model="text-embedding-v4",
    check_embedding_ctx_length=False,
)

def get_vector_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )

def add_documents(collection_name: str, documents: list):
    store = get_vector_store(collection_name)
    store.add_documents(documents)

def delete_source_file(collection_name: str, source_file: str):
    store = get_vector_store(collection_name)
    store._collection.delete(where={"source_file": source_file})

def search(collection_name: str, query: str, top_k: int = 5) -> list:
    store = get_vector_store(collection_name)
    return store.similarity_search(query, k=top_k)
```

### Step 2：文档加载与分块

`app/modules/knowledge_base/document_loader.py`：

```python
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter

SUPPORTED_EXTENSIONS = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
}

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""],
)

def load_and_split(file_path: str) -> list:
    """加载文档并分块"""
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}")

    loader = SUPPORTED_EXTENSIONS[ext](file_path)
    documents = loader.load()

    # 为每个文档块添加元数据
    chunks = text_splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["source_file"] = Path(file_path).name

    return chunks
```

> 当前这组 metadata 只提供弱追溯：命中后能定位到“哪个保存后的文件、哪个块”，还没有把 upload record、document 级唯一标识或 chunk 强关联一并落地。后续如果要补强追溯，应在保留 `source_file`、`chunk_index` 的基础上，再结合 `knowledge_documents` / upload record 建立更稳定的文件级锚点。

### Step 3：RAG 问答链

`app/modules/knowledge_base/rag_chain.py`：

```python
import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.modules.knowledge_base.vector_store import search

load_dotenv()

FALLBACK_ANSWER = "根据现有知识库内容，我无法回答这个问题"
RAG_PROMPT_TEMPLATE = """你是一个知识库问答助手。
请根据以下检索到的文档内容回答用户问题。
如果文档中没有相关信息，请明确说明“根据现有知识库内容，我无法回答这个问题”。

文档内容：
{context}

用户问题：
{question}
"""
MODEL_NAME = os.getenv("OPENAI_MODEL")


def _build_context(documents):
    return "\n\n---\n\n".join(document.page_content for document in documents)


def _build_sources(documents):
    return [
        {
            "content": document.page_content[:50],
            "source_file": document.metadata.get("source_file"),
            "chunk_index": document.metadata.get("chunk_index"),
        }
        for document in documents
    ]


def _build_chain():
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0, streaming=True)
    parser = StrOutputParser()
    return prompt | llm | parser


def rag_query(collection_name: str, question: str, top_k: int = 5) -> dict:
    documents = search(collection_name, question, top_k)
    if not documents:
        return {"answer": FALLBACK_ANSWER, "sources": []}

    chain = _build_chain()
    answer = chain.invoke({"context": _build_context(documents), "question": question})
    return {"answer": answer, "sources": _build_sources(documents)}


async def rag_query_stream(collection_name: str, question: str, top_k: int = 5):
    documents = await asyncio.to_thread(search, collection_name, question, top_k)
    if not documents:
        yield FALLBACK_ANSWER
        return

    chain = _build_chain()
    async for chunk in chain.astream(
        {"context": _build_context(documents), "question": question}
    ):
        yield chunk
```

### Step 4：FastAPI 路由

`app/modules/knowledge_base/router.py` 已落地，当前接口形状如下：

- `POST /kb/upload`
  - 入参：`UploadFile` + `collection_name`（multipart/form-data）
  - 行为：文件落盘到 `data/uploads/` → `load_and_split(...)` → `add_documents(...)` → 写入 `knowledge_documents`
  - 成功返回：`status`、`filename`、`collection_name`、`chunks_count`
- `POST /kb/query`
  - 入参：JSON body（`question`、`collection_name`、`top_k`）
  - 返回：`answer + sources`
- `POST /kb/query/stream`
  - 入参：JSON body（`question`、`collection_name`、`top_k`）
  - 返回：SSE 事件流，协议固定为 `event: message` / `event: done`
- `GET /kb/collections`
  - 直接读取 Chroma 当前 collection 状态
  - 返回数组：`[{"name": ..., "count": ...}]`

其中 `/kb/query/stream` 当前只流式输出文本，不返回 `sources`；如果后续要在流式路径展示来源，应在路由层扩展 SSE 事件结构，而不是改变现有 `rag_query_stream()` 的职责。当前 `source_file` 既用于 query 结果里的弱追溯展示，也用于 upload 失败后的向量补偿删除。

### Step 5：注册路由到主应用

`app/main.py` 已通过 `app.include_router(kb_router)` 完成知识库路由注册，`/docs` 中可见 `/kb/upload`、`/kb/query`、`/kb/query/stream`、`/kb/collections`。

### Step 6：集成到 Orchestrator（可选）

让现有的 `/task` 接口也能使用 RAG 上下文：

```python
# 在 execute_task 中，如果任务需要 RAG 上下文
from app.modules.knowledge_base.vector_store import search
from app.types.retriever_context import RetrieverContext, RetrieverChunk

def _build_retriever_context(query: str, collection: str = "default") -> RetrieverContext:
    docs = search(collection, query, top_k=3)
    chunks = [
        RetrieverChunk(
            chunk_id=f"chunk_{i}",
            source_title=doc.metadata.get("source_file", "unknown"),
            content=doc.page_content,
        )
        for i, doc in enumerate(docs)
    ]
    return RetrieverContext(
        context_id=str(uuid.uuid4()),
        status="success",
        chunks=chunks,
    )
```

---

## 5. 测试方案

### 单元测试

```python
# tests/test_rag_chain.py
import pytest
from pathlib import Path

def test_document_loader():
    """测试文档加载与分块"""
    from app.modules.knowledge_base.document_loader import load_and_split

    # 创建测试文本文件
    test_file = Path("tests/fixtures/test_doc.txt")
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("这是测试文档。" * 200, encoding="utf-8")

    chunks = load_and_split(str(test_file))
    assert len(chunks) > 1
    assert all(len(c.page_content) <= 600 for c in chunks)  # chunk_size + 容差

def test_vector_store_add_and_search():
    """测试向量存储的写入与检索"""
    from app.modules.knowledge_base.vector_store import add_documents, search
    from langchain.schema import Document

    test_docs = [
        Document(page_content="Python 是一种编程语言", metadata={"source": "test"}),
        Document(page_content="FastAPI 是 Python 的 Web 框架", metadata={"source": "test"}),
    ]

    add_documents("test_collection", test_docs)
    results = search("test_collection", "什么是 FastAPI", top_k=1)
    assert len(results) == 1
    assert "FastAPI" in results[0].page_content
```

### 集成测试

```python
# tests/test_kb_api.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.modules.knowledge_base.router import router as kb_router


def build_test_client(session):
    test_app = FastAPI()
    test_app.include_router(kb_router)
    test_app.dependency_overrides[get_db] = lambda: iter([session])
    return TestClient(test_app)


def test_upload_and_query(session):
    client = build_test_client(session)

    with open("tests/fixtures/test_doc.txt", "rb") as f:
        response = client.post(
            "/kb/upload",
            files={"file": ("test.txt", f, "text/plain")},
            data={"collection_name": "test"},
        )
    assert response.status_code == 200
    assert response.json()["chunks_count"] > 0

    response = client.post(
        "/kb/query",
        json={"question": "文档内容是什么", "collection_name": "test"},
    )
    assert response.status_code == 200
    assert "answer" in response.json()
```

> 当前 `tests/test_kb_api.py` 走“测试专用 FastAPI app + 单独挂知识库 router”的方式，避免触发 `app.main` 的真实 lifespan；`/kb/query` 也固定使用 JSON body，而不是 form-data。

### 验证命令

```bash
# 运行 RAG 相关测试
pytest tests/test_rag_chain.py tests/test_kb_api.py -v

# 初始化本地数据库
alembic upgrade head
```

### 手工验收口径

- `/kb/upload`：以“HTTP 响应 + `knowledge_documents` 记录 + `data/uploads/` 落盘文件”三点交叉验证成功，不只看 Swagger UI 单一展示
- `/kb/query`：返回 `answer + sources`
- `/kb/query/stream`：返回 `event: message` 与 `event: done`
- `/kb/collections`：能读到当前 Chroma collection 与 count

### 手动验证示例

```bash
# 上传文档
curl -X POST http://localhost:8000/kb/upload \
  -F "file=@your_document.pdf" \
  -F "collection_name=my_kb"

# 查询（非流式）
curl -X POST http://localhost:8000/kb/query \
  -H "Content-Type: application/json" \
  -d '{"question":"这个文档讲了什么","collection_name":"my_kb","top_k":3}'

# 查询（流式）
curl -N -X POST http://localhost:8000/kb/query/stream \
  -H "accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"question":"这个文档讲了什么","collection_name":"my_kb","top_k":3}'
```

---

## 6. 面试要点

### 常见问题

**Q: 解释一下你的 RAG 系统的完整流程？**
> 1. 文档上传后，用 PyMuPDF/python-docx 解析文本
> 2. 用 RecursiveCharacterTextSplitter 按 500 字分块，重叠 100 字保留上下文
> 3. 用 OpenAI Embedding 模型将每个块转为 1536 维向量，存入 ChromaDB
> 4. 用户提问时，先将问题向量化，在 ChromaDB 中做 top-k 相似度搜索
> 5. 将检索到的文档块拼接到 prompt 中，连同问题一起发给 LLM
> 6. 通过 SSE 流式返回答案文本；当前来源引用走非流式返回，后续如有需要再在路由层扩展 SSE 事件结构

**Q: 你的分块策略怎么选的？chunk_size 和 overlap 怎么定？**
> chunk_size=500 是经验值平衡：太小会丢失上下文，太大会引入噪声。overlap=100 保证分块边界处的信息不会被截断。RecursiveCharacterTextSplitter 会优先按段落、句子切割，尽量不在语义中间断开。实际项目中可以通过评估检索准确率来调优这两个参数。

**Q: ChromaDB 和 pgvector 的区别？你为什么先用 ChromaDB？**
> ChromaDB 是嵌入式向量数据库，零依赖、单文件存储，适合开发和中小规模场景。pgvector 是 PostgreSQL 扩展，优势是可以和业务数据在同一个数据库中，支持 SQL 过滤条件。我先用 ChromaDB 是因为开发效率高，后续切 PostgreSQL 后再迁移到 pgvector，检索逻辑不变。

**Q: RAG 的检索质量如何保证？有什么优化手段？**
> 几个方向：(1) 分块策略优化——根据文档类型选不同的分块方式；(2) 混合检索——向量搜索 + BM25 关键词匹配互补；(3) Re-ranking——用交叉编码器对检索结果重排序；(4) Query Expansion——用 LLM 改写用户问题提高检索命中率。

**Q: RAG 和 Fine-tuning 的区别，什么时候该用哪个？**
> RAG 适合"让 LLM 访问外部知识"，Fine-tuning 适合"改变 LLM 的行为/风格"。RAG 的优势是知识可以实时更新、成本低、可解释（能展示来源）。Fine-tuning 适合需要深度领域理解且数据不常变的场景。两者也可以结合使用。

### 能讲出的亮点

- **完整 RAG 流水线**：文档上传 → 解析 → 分块 → 向量化 → 检索 → 生成
- **流式响应**：SSE 实现打字机效果，用户体验好
- **与现有架构集成**：检索结果填入已预留的 `RetrieverContext`，Orchestrator 可注入 RAG 上下文
- **渐进式存储**：ChromaDB → pgvector，展示架构演进能力
- **多格式支持**：PDF/DOCX/MD/TXT 统一处理管道
