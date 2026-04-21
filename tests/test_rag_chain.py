from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from langchain_core.documents import Document

from app.modules.knowledge_base.rag_chain import (
    FALLBACK_ANSWER,
    rag_query,
    rag_query_stream,
)


class FakeChain:
    # 假链替掉真实 LLM，顺手卡住 question 和 context
    def invoke(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        return "FastAPI 是一个现代 Python Web 框架。"


class FakeStreamChain:
    # 流式假链只验证 chunk 透传
    async def astream(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        assert "FastAPI 是 Python 的 Web 框架" in payload["context"]
        for chunk in ["FastAPI", " 是", " Python Web 框架"]:
            yield chunk


class FakeTruncationChain:
    # 这里返回固定 answer，截断断言才只受 sources 影响
    def invoke(self, payload):
        assert payload["question"] == "什么是 FastAPI"
        return "用于测试截断长度。"


# 空检索时直接走 fallback
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


# 链路负责 answer，检索元数据直接进 sources
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


# 长文本 source 只留前 50 字预览
def test_rag_query_truncates_source_content_to_50_chars(monkeypatch):
    long_text = "Python后端开发经验，熟悉FastAPI、SQLAlchemy、Redis与异步任务编排。" * 2
    docs = [
        Document(
            page_content=long_text,
            metadata={"source_file": "resume.md", "chunk_index": 3},
        )
    ]

    monkeypatch.setattr(
        "app.modules.knowledge_base.rag_chain.search",
        lambda collection_name, question, top_k=5: docs,
    )
    monkeypatch.setattr(
        "app.modules.knowledge_base.rag_chain._build_chain",
        lambda: FakeTruncationChain(),
    )

    result = rag_query("test_collection", "什么是 FastAPI")

    assert result["sources"][0]["content"] == long_text[:50]
    assert len(result["sources"][0]["content"]) == 50


class TestRagQueryStream(IsolatedAsyncioTestCase):
    # 空检索时只产出一次 fallback
    async def test_yields_fallback_when_no_docs(self):
        with patch("app.modules.knowledge_base.rag_chain.search", return_value=[]):
            chunks = []
            async for chunk in rag_query_stream("test_collection", "什么是 Python"):
                chunks.append(chunk)

        assert chunks == [FALLBACK_ANSWER]

    # 命中后按底层 astream 顺序往外吐 chunk
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
