from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.database.connection import Base


# 文件级上传记录，不与 chunk 建立强关联。
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    # (collection_name, file_hash) 唯一约束：用于幂等判重，并兜底并发重复写入。
    __table_args__ = (
        UniqueConstraint(
            "collection_name",
            "file_hash",
            name="uq_kb_collection_hash",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    collection_name = Column(String(100), nullable=False, default="default")
    file_path = Column(String(500), nullable=False)
    # 文件内容 SHA-256；与 collection_name 一起作为幂等判重键。
    file_hash = Column(String(64), nullable=False)
    # 近重复指纹独立于 file_hash，用于识别轻微改写后的相似内容。
    similarity_fingerprint = Column(String(64), nullable=True)
    chunks_count = Column(Integer, nullable=False, default=0)
    # 状态流转：uploading -> completed / failed。
    status = Column(String(20), nullable=False, default="uploading")
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # updated_at 在 INSERT 时也要有值，不能只依赖 onupdate。
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
