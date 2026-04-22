from collections.abc import Generator
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models.knowledge import KnowledgeDocument
from app.modules.knowledge_base import document_loader, rag_chain, router, vector_store


@pytest.fixture
def app_client() -> Generator[tuple[TestClient, object], None, None]:
    # 这里先造测试库，再用 dependency_overrides 把请求期 get_db 指到这份 session。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    test_app = FastAPI()
    test_app.include_router(router.router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_get_db

    # 这里单独挂知识库路由，只保留 HTTP 契约与依赖覆写，不触发真实 app lifespan。
    with TestClient(test_app) as client:
        yield client, session

    test_app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_upload_returns_success_and_persists_record(app_client, monkeypatch):
    # upload 这组测试主要卡住“向量写入成功后，接口响应与 upload record 要同步成立”。
    client, session = app_client
    captured = {}
    chunks = [
        Document(
            page_content="FastAPI 是 Python Web 框架",
            metadata={"source_file": "guide.txt", "chunk_index": 0},
        )
    ]

    monkeypatch.setattr(document_loader, "load_and_split", lambda file_path: chunks)

    def fake_add_documents(collection_name, documents):
        captured["collection_name"] = collection_name
        captured["documents"] = documents

    monkeypatch.setattr(vector_store, "add_documents", fake_add_documents)

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "filename": "guide.txt",
        "collection_name": "default",
        "chunks_count": 1,
    }
    assert captured["collection_name"] == "default"
    assert captured["documents"] == chunks

    saved = session.query(KnowledgeDocument).one()
    assert saved.filename == "guide.txt"
    assert saved.collection_name == "default"
    assert saved.chunks_count == 1
    assert saved.status == "completed"


def test_upload_returns_400_for_unsupported_format(app_client, monkeypatch):
    # 验证 loader 明确判定格式不支持时，接口要稳定返回 400 而不是吞成 500。
    client, _ = app_client

    monkeypatch.setattr(
        document_loader,
        "load_and_split",
        lambda file_path: (_ for _ in ()).throw(ValueError("不支持的文件格式: .exe")),
    )

    response = client.post(
        "/kb/upload",
        files={"file": ("virus.exe", "boom", "application/octet-stream")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "不支持的文件格式: .exe"}


def test_query_returns_answer_and_sources(app_client, monkeypatch):
    # 验证非流式 query 会把 rag_chain 的 answer 与 sources 原样透出给 HTTP 层。
    client, _ = app_client
    captured = {}

    def fake_rag_query(collection_name, question, top_k=5):
        captured["collection_name"] = collection_name
        captured["question"] = question
        captured["top_k"] = top_k
        return {
            "answer": "这是答案",
            "sources": [
                {
                    "content": "chunk preview",
                    "source_file": "guide.txt",
                    "chunk_index": 0,
                }
            ],
        }

    monkeypatch.setattr(rag_chain, "rag_query", fake_rag_query)

    response = client.post(
        "/kb/query",
        json={
            "question": "什么是 FastAPI",
            "collection_name": "default",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "这是答案",
        "sources": [
            {
                "content": "chunk preview",
                "source_file": "guide.txt",
                "chunk_index": 0,
            }
        ],
    }
    assert captured == {
        "collection_name": "default",
        "question": "什么是 FastAPI",
        "top_k": 3,
    }


def test_query_requires_question(app_client):
    # 验证缺少必填 question 时，由 Pydantic/FastAPI 边界校验直接返回 422。
    client, _ = app_client

    response = client.post(
        "/kb/query",
        json={"collection_name": "default"},
    )

    assert response.status_code == 422


def test_query_rejects_non_positive_top_k(app_client):
    # 验证 top_k <= 0 会在请求模型层被拦住，不进入实际检索逻辑。
    client, _ = app_client

    response = client.post(
        "/kb/query",
        json={
            "question": "什么是 FastAPI",
            "collection_name": "default",
            "top_k": 0,
        },
    )

    assert response.status_code == 422


def test_upload_cleans_up_file_and_rolls_back_when_vector_store_fails(
    app_client, monkeypatch
):
    # 这里只验证“向量写入阶段就失败”时，DB 与落盘文件会被清理。
    client, session = app_client
    chunks = [
        Document(
            page_content="FastAPI 是 Python Web 框架",
            metadata={"source_file": "guide.txt", "chunk_index": 0},
        )
    ]
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())

    # 临时上传目录单独隔离，失败用例里才能稳定断言“测试文件已被清干净”。
    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(document_loader, "load_and_split", lambda file_path: chunks)
    monkeypatch.setattr(
        vector_store,
        "add_documents",
        lambda collection_name, documents: (_ for _ in ()).throw(RuntimeError("chroma down")),
    )

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 500
    assert session.query(KnowledgeDocument).count() == 0
    assert list(upload_dir.glob("*")) == []


def test_upload_cleans_up_vectors_when_db_commit_fails(app_client, monkeypatch):
    # 这里卡住“向量已写入但 DB 提交失败”时，补偿删除是否真的发生。
    client, session = app_client
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())
    captured = {}

    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)

    def fake_load_and_split(file_path):
        # 这里故意回填保存后的文件名，才能贴近真实 loader 的 source_file 语义并验证回滚键一致性。
        return [
            Document(
                page_content="FastAPI 是 Python Web 框架",
                metadata={"source_file": Path(file_path).name, "chunk_index": 0},
            )
        ]

    monkeypatch.setattr(document_loader, "load_and_split", fake_load_and_split)
    monkeypatch.setattr(
        vector_store,
        "add_documents",
        lambda collection_name, documents: captured.update(
            {"added": (collection_name, documents)}
        ),
    )
    monkeypatch.setattr(
        vector_store,
        "delete_source_file",
        lambda collection_name, source_file: captured.update(
            {"deleted": (collection_name, source_file)}
        ),
    )

    def fail_commit():
        raise RuntimeError("db commit failed")

    monkeypatch.setattr(session, "commit", fail_commit)

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "知识库上传失败"}
    assert session.query(KnowledgeDocument).count() == 0
    assert list(upload_dir.glob("*")) == []
    assert captured["added"][0] == "default"
    expected_source_file = captured["added"][1][0].metadata["source_file"]
    assert captured["deleted"] == ("default", expected_source_file)


def test_collections_returns_collection_names_and_counts(app_client, monkeypatch):
    # 验证 /kb/collections 暴露的是当前 Chroma collection 的 name/count 观测口径。
    client, _ = app_client

    class FakeCollection:
        def __init__(self, name, count):
            self.name = name
            self._count = count

        def count(self):
            return self._count

    class FakeClient:
        def list_collections(self):
            return [
                FakeCollection("default", 3),
                FakeCollection("resume", 7),
            ]

    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: FakeClient())

    response = client.get("/kb/collections")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "default", "count": 3},
        {"name": "resume", "count": 7},
    ]


def test_query_stream_returns_sse_messages_and_done_event(app_client, monkeypatch):
    # stream 路径当前协议只承诺 message/done 两类事件，不在 SSE 中返回 sources。
    client, _ = app_client

    async def fake_rag_query_stream(collection_name, question, top_k=5):
        assert collection_name == "default"
        assert question == "什么是 FastAPI"
        assert top_k == 3
        for chunk in ["FastAPI", " 是", " Python Web 框架"]:
            yield chunk

    monkeypatch.setattr(rag_chain, "rag_query_stream", fake_rag_query_stream)

    with client.stream(
        "POST",
        "/kb/query/stream",
        json={
            "question": "什么是 FastAPI",
            "collection_name": "default",
            "top_k": 3,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message" in body
    assert "data: FastAPI" in body
    # SSE 文本拼接时可能保留一个前导空格，这里只校验协议语义，不把空格差异当成失败。
    assert "data:  是" in body or "data: 是" in body
    assert "data:  Python Web 框架" in body or "data: Python Web 框架" in body
    assert "event: done" in body
    assert "data: [DONE]" in body
