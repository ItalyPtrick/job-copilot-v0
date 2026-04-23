import hashlib
import shutil
import uuid
from pathlib import Path

import chromadb
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
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
    vectors_written = False  # 先标记向量未落库

    try:
        # 先落盘再交给 loader，避免一次性把上传内容全读进内存。
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        chunks = document_loader.load_and_split(str(save_path))
        vector_store.add_documents(collection_name, chunks)
        vectors_written = True  # 标记向量已落库

        record = KnowledgeDocument(
            filename=filename,
            collection_name=collection_name,
            file_path=str(save_path),
            file_hash=_calculate_file_hash(save_path),
            chunks_count=len(chunks),
            status="completed",
            file_size=save_path.stat().st_size,
        )
        db.add(record)
        db.commit()
    except ValueError as error:  # 业务异常，返回400
        db.rollback()
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # 其他异常，返回500
        db.rollback()
        # 向量已落库但 DB 提交失败时，要按同一份 source_file metadata 做补偿删除，避免留下脏 chunk。
        if vectors_written:
            vector_store.delete_source_file(collection_name, source_file)
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="知识库上传失败") from error

    return {
        "status": "success",
        "filename": file.filename,
        "collection_name": collection_name,
        "chunks_count": len(chunks),
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


# 文件级 hash 先用于记录上传内容指纹，后续可继续扩展去重或排查重复上传。
def _calculate_file_hash(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
