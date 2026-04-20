from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from langchain_core.documents import Document

from app.modules.knowledge_base.rag_chain import (
    FALLBACK_ANSWER,
    rag_query,
    rag_query_stream,
)


class FakeChain:
    def invoke(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        return "FastAPI 是一个现代 Python Web 框架。"


class FakeStreamChain:
    async def astream(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        for chunk in ["FastAPI", " 是", " Python Web 框架"]:
            yield chunk


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


class TestRagQueryStream(IsolatedAsyncioTestCase):
    async def test_yields_fallback_when_no_docs(self):
        with patch("app.modules.knowledge_base.rag_chain.search", return_value=[]):
            chunks = []
            async for chunk in rag_query_stream("test_collection", "什么是 Python"):
                chunks.append(chunk)

        assert chunks == [FALLBACK_ANSWER]

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
