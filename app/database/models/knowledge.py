from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer

from app.database.connection import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # TODO: W2/W3/W4 时补充具体字段