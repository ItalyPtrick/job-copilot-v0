from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database.connection import Base


# 这里记录的是文件级 upload record，不负责 chunk 级强关联。
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    collection_name = Column(String(100), nullable=False, default="default")
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    chunks_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="uploading")
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))