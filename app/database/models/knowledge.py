from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.database.connection import Base


# 这里记录的是文件级 upload record，不负责 chunk 级强关联。
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    # (collection_name, file_hash) 唯一约束同时承担：上传幂等判重 + 并发竞争兜底。
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
    # 文件内容 SHA-256，上传幂等判重基准，与 collection_name 组成唯一约束。
    file_hash = Column(String(64), nullable=False)
    chunks_count = Column(Integer, nullable=False, default=0)
    # 状态机：uploading（占位中）→ completed（全部成功）/ failed（任一步失败）。
    status = Column(String(20), nullable=False, default="uploading")
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # onupdate 仅 UPDATE 时触发；INSERT 必须靠 default 兜底，否则占位记录 updated_at 为 NULL。
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
