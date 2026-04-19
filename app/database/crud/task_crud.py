from sqlalchemy.orm import Session

from app.database.models.task_record import TaskRecord


# 任务记录相关的 CRUD 操作
def get_tasks_by_type(db: Session, task_type: str, limit: int = 10) -> list[TaskRecord]:
    return (
        db.query(TaskRecord)
        .filter(TaskRecord.task_type == task_type)
        .order_by(TaskRecord.created_at.desc())
        .limit(limit)
        .all()
    )


# 获取最近20条任务记录
def get_recent_tasks(db: Session, limit: int = 20) -> list[TaskRecord]:
    return (
        db.query(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit).all()
    )
