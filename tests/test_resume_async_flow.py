"""W4-D3 异步简历分析流程测试：service CRUD + 去重逻辑 + requirements 完整性"""

import pytest
from celery.exceptions import Retry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base


def _session_factory():
    """内存 SQLite，每次测试独立建表，不依赖外部数据库"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_resume_record_can_be_found_by_external_resume_id():
    """验证 create → get_by_id 链路，确认 resume_id/file_path/file_ext 正确持久化"""
    from app.modules.resume.service import create_resume_record, get_resume_by_id

    SessionLocal = _session_factory()
    db = SessionLocal()
    try:
        record = create_resume_record(
            db,
            resume_id="resume-abc",
            filename="resume.txt",
            file_path="resume.txt",
            file_ext=".txt",
        )

        found = get_resume_by_id(db, "resume-abc")

        assert found is not None
        assert found.id == record.id
        assert found.resume_id == "resume-abc"
        assert found.file_path == "resume.txt"
        assert found.file_ext == ".txt"
    finally:
        db.close()


def test_duplicate_in_progress_resume_retries_without_placeholder_completed(monkeypatch):
    """相同内容但前一份仍在 analyzing 时，后到任务保持 pending 并等待重试。"""
    from app.modules.resume import tasks
    from app.modules.resume.service import create_resume_record, update_content_hash

    SessionLocal = _session_factory()
    db = SessionLocal()
    try:
        raw_text = "same resume text"
        target_role = "python"
        content_hash = tasks._resume_content_hash(raw_text, target_role)

        existing = create_resume_record(
            db,
            resume_id="resume-existing",
            filename="existing.txt",
            file_path="existing.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        duplicate = create_resume_record(
            db,
            resume_id="resume-duplicate",
            filename="duplicate.txt",
            file_path="duplicate.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        update_content_hash(db, existing.resume_id, content_hash)
        existing.status = "analyzing"
        db.commit()
        duplicate_resume_id = duplicate.resume_id
        duplicate_file_path = duplicate.file_path
        duplicate_pk = duplicate.id
    finally:
        db.close()

    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: raw_text)
    with pytest.raises(Retry):
        tasks.analyze_resume_task.apply(
            args=(duplicate_resume_id, duplicate_file_path, target_role),
            throw=True,
        )

    db = SessionLocal()
    try:
        refreshed = db.get(type(existing), duplicate_pk)
        assert refreshed.status == "pending"
        assert refreshed.analysis_result is None
        assert refreshed.content_hash != content_hash
    finally:
        db.close()


def test_requirements_txt_is_utf8_without_nul_bytes():
    """防止 conda export 产生的二进制 NUL 或 @ file: 本地路径污染 requirements.txt"""
    data = open("requirements.txt", "rb").read()

    assert b"\x00" not in data
    text = data.decode("utf-8")
    assert "celery>=5.4" in text
    assert "@ file:" not in text
