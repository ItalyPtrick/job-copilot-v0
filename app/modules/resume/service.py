import hashlib

from sqlalchemy.orm import Session

from app.database.models import ResumeRecord


# content_hash 列 unique+not null，创建时用占位值填充，任务完成后替换为真实哈希
def _placeholder_content_hash(resume_id: str, filename: str, target_role: str) -> str:
    return hashlib.sha256(
        f"pending:{resume_id}:{filename}:{target_role}".encode()
    ).hexdigest()


def create_resume_record(
    db: Session,
    resume_id: str,
    filename: str,
    file_path: str,
    file_ext: str,
    target_role: str = "",
) -> ResumeRecord:
    """创建简历记录，初始状态 pending"""
    record_data = {
        "resume_id": resume_id,
        "filename": filename,
        "file_path": file_path,
        "file_ext": file_ext,
        "target_role": target_role,
        "status": "pending",
        "content_hash": _placeholder_content_hash(resume_id, filename, target_role),
    }
    record = ResumeRecord(**record_data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_resume_by_id(db: Session, resume_id: str) -> ResumeRecord | None:
    """按 resume_id 查询"""
    record = (
        db.query(ResumeRecord)
        .filter(ResumeRecord.resume_id == str(resume_id))
        .first()
    )
    if record:
        return record

    try:
        record_id = int(resume_id)
    except (TypeError, ValueError):
        return None
    return db.query(ResumeRecord).filter(ResumeRecord.id == record_id).first()


def get_resume_by_hash(db: Session, content_hash: str) -> ResumeRecord | None:
    """按内容哈希查询（去重用）"""
    return (
        db.query(ResumeRecord)
        .filter(ResumeRecord.content_hash == content_hash)
        .first()
    )


def update_content_hash(db: Session, resume_id: str, content_hash: str) -> bool:
    """任务解析完成后，用真实内容哈希替换占位哈希"""
    from sqlalchemy.exc import IntegrityError

    record = get_resume_by_id(db, resume_id)
    if not record:
        return False
    record.content_hash = content_hash
    try:
        db.commit()
    except IntegrityError:
        # 并发场景：另一任务已写入相同哈希，调用方据此停止继续分析
        db.rollback()
        return False
    return True


def update_resume_status(
    db: Session,
    resume_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> ResumeRecord | None:
    """更新简历分析状态和结果"""
    record = get_resume_by_id(db, resume_id)
    if not record:
        return None
    record.status = status
    if result is not None:
        record.analysis_result = result
    if error is not None:
        record.analysis_result = {"error": error}
    db.commit()
    db.refresh(record)
    return record
