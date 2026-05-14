"""简历分析 Celery 异步任务：解析 → 去重 → LLM 分析 → 写回结果。"""

import hashlib
import json
import logging

from celery.exceptions import Retry

from celery_app import celery
from app.database.connection import SessionLocal
from app.modules.resume.parser import parse_resume
from app.modules.resume.analyzer import analyze_resume
from app.modules.resume.service import (
    get_resume_by_hash,
    release_content_hash,
    update_resume_status,
    update_content_hash,
)

logger = logging.getLogger(__name__)
_DUPLICATE_RETRY_DELAY_SECONDS = 10
_DUPLICATE_WAIT_MAX_RETRIES = 30


def _record_resume_id(record) -> str:
    return str(record.resume_id)


def _resume_content_hash(raw_text: str, target_role: str) -> str:
    payload = {
        "raw_text": raw_text,
        "target_role": target_role or "",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _retry_duplicate_in_progress(task):
    raise task.retry(
        exc=RuntimeError("duplicate_in_progress"),
        countdown=_DUPLICATE_RETRY_DELAY_SECONDS,
        max_retries=_DUPLICATE_WAIT_MAX_RETRIES,
    )


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
        content_hash = _resume_content_hash(raw_text, target_role)

        # 3. 去重：相同内容+目标岗位 → 复用已有结果；进行中任务等待；失败记录释放后允许重试
        existing = get_resume_by_hash(db, content_hash)
        if existing and _record_resume_id(existing) != str(resume_id):
            if existing.status == "completed":
                result = existing.analysis_result
                update_resume_status(db, resume_id, "completed", result=result)
                return {"status": "completed", "reused": True, "result": result}
            if existing.status in {"pending", "analyzing"}:
                _retry_duplicate_in_progress(self)
            if existing.status == "failed":
                if not release_content_hash(db, existing):
                    _retry_duplicate_in_progress(self)
            else:
                _retry_duplicate_in_progress(self)

        if not update_content_hash(db, resume_id, content_hash):
            _retry_duplicate_in_progress(self)

        # 4. 调用 LLM 分析
        update_resume_status(db, resume_id, "analyzing")
        result = analyze_resume(raw_text, target_role)

        # 5. 写回成功结果
        update_resume_status(db, resume_id, "completed", result=result)
        return {"status": "completed", "result": result}

    except Retry:
        raise
    except Exception as e:
        logger.error(f"简历分析失败 [{resume_id}]: {e}")
        if self.request.retries >= self.max_retries:
            update_resume_status(db, resume_id, "failed", error=str(e))
        raise self.retry(exc=e)
    finally:
        db.close()
