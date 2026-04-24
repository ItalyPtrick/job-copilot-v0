import hashlib
import shutil
import uuid
from pathlib import Path

import chromadb
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database.connection import get_db
from app.database.models.knowledge import KnowledgeDocument
from app.modules.knowledge_base import document_loader, rag_chain, vector_store

# 知识库模块的接口层，处理上传和查询请求
router = APIRouter(prefix="/kb", tags=["knowledge_base"])
UPLOAD_DIR = Path("./data/uploads")


# 路由层只收请求参数，真正的检索与生成仍复用 rag_chain。
class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    collection_name: str = Field(default="default", min_length=1)
    top_k: int = Field(default=5, ge=1)


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    collection_name: str = Form(default="default"),
    db: Session = Depends(get_db),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(file.filename or "").suffix
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}{extension}"

    # filename 面向接口响应与 upload record；source_file 对齐 chunk metadata，用作向量侧回滚锚点。
    filename = file.filename or save_path.name
    source_file = save_path.name

    # 先落盘再读 hash，避免一次性把上传内容全读进内存；hash 前移是上传幂等判重的前提。
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file_hash = _calculate_file_hash(save_path)
    file_size = save_path.stat().st_size

    # 上传幂等短路：同 (collection_name, file_hash) 已有 completed 记录，直接复用，跳过 embedding 以省 API 计费。
    existing = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.collection_name == collection_name,
            KnowledgeDocument.file_hash == file_hash,
            KnowledgeDocument.status == "completed",
        )
        .first()
    )
    if existing is not None:
        save_path.unlink(missing_ok=True)
        return {
            "status": "success",
            "filename": filename,
            "collection_name": collection_name,
            "chunks_count": existing.chunks_count,
            "reused": True,
        }

    # 清理同 hash 的 failed 记录，释放唯一约束名额，允许重传。
    db.query(KnowledgeDocument).filter(
        KnowledgeDocument.collection_name == collection_name,
        KnowledgeDocument.file_hash == file_hash,
        KnowledgeDocument.status == "failed",
    ).delete()
    db.commit()

    # 两阶段 commit 第一阶段：先写 uploading 占位，让唯一约束对并发请求生效。
    record = KnowledgeDocument(
        filename=filename,
        collection_name=collection_name,
        file_path=str(save_path),
        file_hash=file_hash,
        chunks_count=0,
        status="uploading",
        file_size=file_size,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        # 并发冲突：另一个请求已占位处理中；本请求直接 409，调用方自行重试。
        db.rollback()
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409, detail="同文件正在处理中"
        ) from error
    db.refresh(record)

    vectors_written = False
    try:
        chunks = document_loader.load_and_split(str(save_path))
        vector_store.add_documents(collection_name, chunks)
        vectors_written = True

        # 两阶段 commit 第二阶段：真正落地 completed；onupdate 自动刷新 updated_at。
        record.status = "completed"
        record.chunks_count = len(chunks)
        db.commit()
    except ValueError as error:
        # 不支持的格式：占位记录没有继续保留价值，直接删除，避免误占唯一约束名额。
        db.delete(record)
        db.commit()
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        # 真正失败（向量库异常、DB 异常等）：保留 failed 记录便于排查；向量与落盘文件都清理。
        try:
            record.status = "failed"
            db.commit()
        except Exception:
            db.rollback()
        if vectors_written:
            vector_store.delete_source_file(collection_name, source_file)
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="知识库上传失败") from error

    return {
        "status": "success",
        "filename": filename,
        "collection_name": collection_name,
        "chunks_count": len(chunks),
        "reused": False,
    }


@router.post("/query")
def query(request: QueryRequest):
    return rag_chain.rag_query(request.collection_name, request.question, request.top_k)


@router.post("/query/stream")
async def query_stream(request: QueryRequest):
    # 当前 SSE 协议只承诺 message/done 两类事件，sources 仍由非流式 query 返回。
    async def event_generator():
        async for chunk in rag_chain.rag_query_stream(
            request.collection_name,
            request.question,
            request.top_k,
        ):
            yield {"event": "message", "data": chunk}

        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_generator())


@router.get("/collections")
def list_collections():
    # 这里读的是 Chroma 当前真实索引状态，不从 knowledge_documents 反推 collection 列表。
    client = chromadb.PersistentClient(path=vector_store.CHROMA_DIR)
    collections = client.list_collections()
    return [
        {"name": collection.name, "count": collection.count()}
        for collection in collections
    ]


# 文件级 SHA-256 指纹，是上传幂等短路和 (collection_name, file_hash) 唯一约束的判重基准。
def _calculate_file_hash(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
