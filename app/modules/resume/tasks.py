import hashlib
import logging

from celery_app import celery
from app.database.connection import SessionLocal
from app.modules.resume.parser import parse_resume
from app.modules.resume.analyzer import analyze_resume
from app.modules.resume.service import (
    get_resume_by_hash,
    update_resume_status,
    update_content_hash,
)

logger = logging.getLogger(__name__)


def _record_resume_id(record) -> str:
    return str(record.resume_id)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_resume_task(self, resume_id: str, file_path: str, target_role: str = ""):
    """异步简历分析任务：解析 → 去重 → LLM 分析 → 写回结果"""
    db = SessionLocal()
    try:
        # 1. 解析文档提取文本
        raw_text = parse_resume(file_path)
        if not raw_text.strip():
            update_resume_status(db, resume_id, "failed", error="文档解析结果为空")
            return {"status": "failed", "error": "文档解析结果为空"}

        # 2. 计算内容哈希，用于去重
        content_hash = hashlib.sha256(
            f"{raw_text}{target_role}".encode()
        ).hexdigest()

        # 3. 去重：相同内容+目标岗位 → 复用已有结果
        existing = get_resume_by_hash(db, content_hash)
        if (
            existing
            and _record_resume_id(existing) != str(resume_id)
            and existing.status == "completed"
        ):
            result = existing.analysis_result
            update_resume_status(db, resume_id, "completed", result=result)
            return {"status": "completed", "reused": True, "result": result}

        if not existing or _record_resume_id(existing) == str(resume_id):
            if not update_content_hash(db, resume_id, content_hash):
                return {"status": "pending", "reason": "duplicate_in_progress"}
        else:
            return {"status": "pending", "reason": "duplicate_in_progress"}

        # 4. 调用 LLM 分析
        update_resume_status(db, resume_id, "analyzing")
        result = analyze_resume(raw_text, target_role)

        # 5. 写回成功结果
        update_resume_status(db, resume_id, "completed", result=result)
        return {"status": "completed", "result": result}

    except Exception as e:
        logger.error(f"简历分析失败 [{resume_id}]: {e}")
        if self.request.retries >= self.max_retries:
            update_resume_status(db, resume_id, "failed", error=str(e))
        raise self.retry(exc=e)
    finally:
        db.close()
