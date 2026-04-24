from collections.abc import Generator
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
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
    # 幂等改造后响应添加 reused 字段；初次上传固定为 False。
    assert response.json() == {
        "status": "success",
        "filename": "guide.txt",
        "collection_name": "default",
        "chunks_count": 1,
        "reused": False,
    }
    assert captured["collection_name"] == "default"
    assert captured["documents"] == chunks

    saved = session.query(KnowledgeDocument).one()
    assert saved.filename == "guide.txt"
    assert saved.collection_name == "default"
    assert saved.chunks_count == 1
    assert saved.status == "completed"
    # 两阶段 commit 后 updated_at 在第二次 UPDATE 时刷新；不为 NULL 即为达标。
    assert saved.updated_at is not None


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


def test_upload_keeps_failed_record_and_cleans_file_when_vector_store_fails(
    app_client, monkeypatch
):
    # 向量写入失败时，DB 保留 status=failed 的占位记录（便于排查），落盘文件被清理。
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
        lambda collection_name, documents: (_ for _ in ()).throw(
            RuntimeError("chroma down")
        ),
    )

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 500
    # 占位记录保留，标记 failed，不整条删除。
    records = session.query(KnowledgeDocument).all()
    assert len(records) == 1
    assert records[0].status == "failed"
    assert list(upload_dir.glob("*")) == []


def test_upload_cleans_up_vectors_when_db_second_commit_fails(app_client, monkeypatch):
    # 两阶段 commit ：第一次（uploading 占位）成功、第二次（切换 completed）抛错，
    # 验证向量补偿删除被触发，且第三次（标成 failed）成功落库。
    client, session = app_client
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())
    captured = {}

    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)

    def fake_load_and_split(file_path):
        # 故意回填保存后的文件名，能贴近真实 loader 的 source_file 语义并验证回滚键一致性。
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

    commit_calls = {"n": 0}  # commit 计数器，用字典方便修改闭包内的值
    original_commit = session.commit  # 保存真实 commit 方法

    def flaky_commit():
        commit_calls["n"] += 1
        # 第一次放行（清理 failed）、第二次放行（uploading 落库）、第三次抛错（completed 失败）、第四次放行（failed 落库）。
        if commit_calls["n"] == 3:
            raise RuntimeError("db commit failed")
        original_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "知识库上传失败"}
    # 验证 failed 状态已真实持久化，而不是只停留在当前会话内存。
    records = session.query(KnowledgeDocument).all()
    assert len(records) == 1
    assert records[0].status == "failed"
    assert list(upload_dir.glob("*")) == []
    assert captured["added"][0] == "default"
    expected_source_file = captured["added"][1][0].metadata["source_file"]
    assert captured["deleted"] == ("default", expected_source_file)


def test_upload_after_failed_record_succeeds(app_client, monkeypatch):
    # failed 记录不应卡死后续重传：第一次上传失败留下 status=failed，第二次同文件上传应清理 failed 并成功。
    client, session = app_client
    add_calls = {"n": 0}
    chunks = [
        Document(
            page_content="FastAPI 是 Python Web 框架",
            metadata={"source_file": "guide.txt", "chunk_index": 0},
        )
    ]
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())

    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(document_loader, "load_and_split", lambda fp: chunks)

    def counting_add(collection_name, documents):
        add_calls["n"] += 1
        # 第一次调用抛异常模拟向量写入失败，后续放行。
        if add_calls["n"] == 1:
            raise RuntimeError("chroma down")

    monkeypatch.setattr(vector_store, "add_documents", counting_add)

    files = {"file": ("guide.txt", "same retry body", "text/plain")}
    data = {"collection_name": "default"}

    # 第一次上传：向量写入失败 → 500 + status=failed
    first = client.post("/kb/upload", files=files, data=data)
    assert first.status_code == 500
    records = session.query(KnowledgeDocument).all()
    assert len(records) == 1
    assert records[0].status == "failed"

    # 第二次上传同文件：应清理 failed 记录并重新走完整流程
    second = client.post("/kb/upload", files=files, data=data)
    assert second.status_code == 200
    body = second.json()
    assert body["reused"] is False
    assert body["chunks_count"] == 1
    # DB 只剩 1 条 completed，failed 已被清理
    records = session.query(KnowledgeDocument).all()
    assert len(records) == 1
    assert records[0].status == "completed"


def test_upload_duplicate_returns_reused_and_skips_embedding(app_client, monkeypatch):
    # 同内容第二次上传时：响应 reused=True、embedding 不再被调用，DB 仍只保留一条 completed 记录。
    client, session = app_client
    add_calls = {"n": 0}
    load_calls = {"n": 0}
    chunks = [
        Document(
            page_content="FastAPI 是 Python Web 框架",
            metadata={"source_file": "guide.txt", "chunk_index": 0},
        )
    ]
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())

    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)

    def fake_load(file_path):
        load_calls["n"] += 1
        return chunks

    def fake_add(collection_name, documents):
        add_calls["n"] += 1

    monkeypatch.setattr(document_loader, "load_and_split", fake_load)
    monkeypatch.setattr(vector_store, "add_documents", fake_add)

    files = {"file": ("guide.txt", "same content body", "text/plain")}
    data = {"collection_name": "default"}

    first = client.post("/kb/upload", files=files, data=data)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["reused"] is False
    assert first_body["chunks_count"] == 1
    assert add_calls["n"] == 1
    assert load_calls["n"] == 1
    assert session.query(KnowledgeDocument).one().status == "completed"

    # 第二次上传相同内容文件：hash 短路命中，跳过 loader 和 embedding。
    second = client.post("/kb/upload", files=files, data=data)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["reused"] is True
    assert second_body["chunks_count"] == 1
    assert add_calls["n"] == 1
    assert load_calls["n"] == 1
    assert session.query(KnowledgeDocument).count() == 1


def test_upload_returns_409_when_integrity_error_on_placeholder_commit(
    app_client, monkeypatch
):
    # 并发冲突场景：第一次 commit（uploading 占位）抛 IntegrityError，请求返回 409，落盘文件被清理，不进入向量写入阶段。
    client, session = app_client
    add_calls = {"n": 0}
    upload_dir = Path("data/test-uploads") / str(uuid.uuid4())

    monkeypatch.setattr(router, "UPLOAD_DIR", upload_dir)

    def counting_add(collection_name, documents):
        add_calls["n"] += 1

    monkeypatch.setattr(vector_store, "add_documents", counting_add)

    commit_calls = {"n": 0}
    original_commit = session.commit

    def integrity_on_placeholder():
        commit_calls["n"] += 1
        # 第一次放行（清理 failed）、第二次抛 IntegrityError（uploading 占位并发冲突）。
        if commit_calls["n"] == 2:
            raise IntegrityError("stmt", {}, Exception("uq_kb_collection_hash"))
        original_commit()

    monkeypatch.setattr(session, "commit", integrity_on_placeholder)

    response = client.post(
        "/kb/upload",
        files={"file": ("guide.txt", "hello knowledge base", "text/plain")},
        data={"collection_name": "default"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "同文件正在处理中"}
    assert add_calls["n"] == 0
    assert list(upload_dir.glob("*")) == []


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
