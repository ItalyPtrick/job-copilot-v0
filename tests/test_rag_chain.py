from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from langchain_core.documents import Document

from app.modules.knowledge_base.rag_chain import (
    FALLBACK_ANSWER,
    rag_query,
    rag_query_stream,
)


class FakeChain:
    # 这里替掉真实 LLM，测试只关心 rag_query 的编排逻辑。
    def invoke(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        return "FastAPI 是一个现代 Python Web 框架。"


class FakeStreamChain:
    # 流式测试不碰真实模型，只验证 chunk 是否被原样透传。
    async def astream(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        for chunk in ["FastAPI", " 是", " Python Web 框架"]:
            yield chunk


# 空检索结果时应该直接短路，证明 fallback 不依赖真实模型。
def test_rag_query_returns_fallback_when_no_docs(monkeypatch):
    monkeypatch.setattr(
        "app.modules.knowledge_base.rag_chain.search",
        lambda collection_name, question, top_k=5: [],
    )

    result = rag_query("test_collection", "什么是 Python")

    assert result == {
        "answer": FALLBACK_ANSWER,
        "sources": [],
    }


# 命中文档后，重点验证 answer 来自链调用，sources 来自检索元数据。
def test_rag_query_returns_answer_and_sources_when_docs_found(monkeypatch):
    docs = [
        Document(
            page_content="FastAPI 是 Python 的 Web 框架",
            metadata={"source_file": "fastapi.md", "chunk_index": 0},
        )
    ]

    monkeypatch.setattr(
        "app.modules.knowledge_base.rag_chain.search",
        lambda collection_name, question, top_k=5: docs,
    )
    monkeypatch.setattr(
        "app.modules.knowledge_base.rag_chain._build_chain",
        lambda: FakeChain(),
    )

    result = rag_query("test_collection", "什么是 FastAPI")

    assert result["answer"] == "FastAPI 是一个现代 Python Web 框架。"
    assert result["sources"] == [
        {
            "content": "FastAPI 是 Python 的 Web 框架",
            "source_file": "fastapi.md",
            "chunk_index": 0,
        }
    ]


# 流式路径单独用异步测试，避免把 async generator 当同步迭代器误用。
class TestRagQueryStream(IsolatedAsyncioTestCase):
    # 空检索结果时应只产出一次 fallback，然后立刻结束。
    async def test_yields_fallback_when_no_docs(self):
        with patch("app.modules.knowledge_base.rag_chain.search", return_value=[]):
            chunks = []
            async for chunk in rag_query_stream("test_collection", "什么是 Python"):
                chunks.append(chunk)

        assert chunks == [FALLBACK_ANSWER]

    # 命中文档后，rag_query_stream 应原样透传底层 astream 的 chunk 序列。
    async def test_yields_chunks_when_docs_found(self):
        docs = [
            Document(
                page_content="FastAPI 是 Python 的 Web 框架",
                metadata={"source_file": "fastapi.md", "chunk_index": 0},
            )
        ]

        with patch("app.modules.knowledge_base.rag_chain.search", return_value=docs), patch(
            "app.modules.knowledge_base.rag_chain._build_chain",
            return_value=FakeStreamChain(),
        ):
            chunks = []
            async for chunk in rag_query_stream("test_collection", "什么是 FastAPI"):
                chunks.append(chunk)

        assert chunks == ["FastAPI", " 是", " Python Web 框架"]
