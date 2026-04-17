from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from app.database.connection import Base


# 记录每次任务执行的输入、结果与错误信息。
class TaskRecord(Base):
    __tablename__ = "task_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSON)
    status = Column(String(20), nullable=False)  # 任务状态：success / error
    result = Column(JSON)
    error_type = Column(String(100))
    error_message = Column(String(500))
    trace = Column(JSON)  # 执行轨迹，便于排错。
    created_at = Column(DateTime, default=datetime.now)
