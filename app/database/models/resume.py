from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, JSON, Text

from app.database.connection import Base


class ResumeRecord(Base):
    """简历分析记录，content_hash 用于去重避免重复调用 LLM"""

    __tablename__ = "resume_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resume_id = Column(String(64), nullable=False, unique=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, default="")
    file_ext = Column(String(20), nullable=False, default="")
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="pending")
    target_role = Column(String(100), default="")
    analysis_result = Column(JSON)
    raw_text = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
