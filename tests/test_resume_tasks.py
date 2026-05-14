"""简历分析 Celery 任务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.models import ResumeRecord
from app.modules.resume.service import create_resume_record, get_resume_by_id


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _analysis_result(name="张三"):
    return {
        "basic_info": {"name": name, "education": "本科", "years_of_experience": 3, "skills": ["Python"]},
        "strengths": ["项目经验完整"],
        "weaknesses": ["缺少量化成果"],
        "suggestions": ["补充指标"],
        "overall_score": 80,
        "match_analysis": "匹配 Python 后端岗位",
    }


def _create_record(SessionLocal, resume_id="resume-1", target_role="Python 后端"):
    db = SessionLocal()
    try:
        create_resume_record(
            db=db,
            resume_id=resume_id,
            filename=f"{resume_id}.txt",
            file_path=f"{resume_id}.txt",
            file_ext=".txt",
            target_role=target_role,
        )
    finally:
        db.close()


def test_resume_content_hash_includes_target_role():
    from app.modules.resume.tasks import _resume_content_hash

    raw_text = "相同简历内容"

    python_hash = _resume_content_hash(raw_text, "Python 后端")
    java_hash = _resume_content_hash(raw_text, "Java 后端")

    assert python_hash != java_hash
    assert python_hash == _resume_content_hash(raw_text, "Python 后端")
    assert len(python_hash) == 64


def test_resume_content_hash_uses_structured_payload_to_avoid_boundary_collision():
    from app.modules.resume.tasks import _resume_content_hash

    assert _resume_content_hash("ab", "c") != _resume_content_hash("a", "bc")


def test_analyze_task_success(monkeypatch, session_factory):
    from app.modules.resume import tasks

    SessionLocal = session_factory
    _create_record(SessionLocal)
    expected = _analysis_result()
    calls = []

    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: "张三\nPython 开发")

    def fake_analyze(raw_text, target_role):
        calls.append((raw_text, target_role))
        return expected

    monkeypatch.setattr(tasks, "analyze_resume", fake_analyze)

    result = tasks.analyze_resume_task.apply(args=("resume-1", "resume-1.txt", "Python 后端")).get()

    assert result == {"status": "completed", "result": expected}
    assert calls == [("张三\nPython 开发", "Python 后端")]


def test_analyze_task_retry_on_failure(monkeypatch, session_factory):
    from celery.exceptions import Retry
    from app.modules.resume import tasks

    SessionLocal = session_factory
    _create_record(SessionLocal)
    attempts = []

    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: "张三\nPython 开发")

    def fail_once(raw_text, target_role):
        attempts.append((raw_text, target_role))
        raise RuntimeError("LLM 暂时失败")

    monkeypatch.setattr(tasks, "analyze_resume", fail_once)

    with pytest.raises(Retry):
        tasks.analyze_resume_task.apply(
            args=("resume-1", "resume-1.txt", "Python 后端"),
            throw=True,
        )

    assert attempts == [("张三\nPython 开发", "Python 后端")]


def test_analyze_task_updates_db_status(monkeypatch, session_factory):
    from app.modules.resume import tasks

    SessionLocal = session_factory
    _create_record(SessionLocal)
    expected = _analysis_result()

    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: "张三\nPython 开发")
    monkeypatch.setattr(tasks, "analyze_resume", lambda raw_text, target_role: expected)

    tasks.analyze_resume_task.apply(args=("resume-1", "resume-1.txt", "Python 后端")).get()

    db = SessionLocal()
    try:
        record = get_resume_by_id(db, "resume-1")
        assert record.status == "completed"
        assert record.analysis_result == expected
    finally:
        db.close()


def test_analyze_task_dedup(monkeypatch, session_factory):
    from app.modules.resume import tasks

    SessionLocal = session_factory
    raw_text = "相同简历内容"
    target_role = "Python 后端"
    existing_result = _analysis_result("李四")
    content_hash = tasks._resume_content_hash(raw_text, target_role)

    db = SessionLocal()
    try:
        existing = create_resume_record(
            db=db,
            resume_id="resume-existing",
            filename="existing.txt",
            file_path="existing.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        existing.content_hash = content_hash
        existing.status = "completed"
        existing.analysis_result = existing_result
        create_resume_record(
            db=db,
            resume_id="resume-duplicate",
            filename="duplicate.txt",
            file_path="duplicate.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        db.commit()
    finally:
        db.close()

    analyze_calls = []
    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: raw_text)
    monkeypatch.setattr(tasks, "analyze_resume", lambda raw_text, target_role: analyze_calls.append(1))

    result = tasks.analyze_resume_task.apply(
        args=("resume-duplicate", "duplicate.txt", target_role)
    ).get()

    db = SessionLocal()
    try:
        duplicate = get_resume_by_id(db, "resume-duplicate")
        assert result == {"status": "completed", "reused": True, "result": existing_result}
        assert duplicate.status == "completed"
        assert duplicate.analysis_result == existing_result
        assert analyze_calls == []
    finally:
        db.close()


def test_analyze_task_retries_when_duplicate_is_in_progress(monkeypatch, session_factory):
    """相同内容的已有记录仍在分析时，后到任务应重试等待结果。"""
    from celery.exceptions import Retry
    from app.modules.resume import tasks

    SessionLocal = session_factory
    raw_text = "相同简历内容"
    target_role = "Python 后端"
    content_hash = tasks._resume_content_hash(raw_text, target_role)

    db = SessionLocal()
    try:
        existing = create_resume_record(
            db=db,
            resume_id="resume-existing",
            filename="existing.txt",
            file_path="existing.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        existing.content_hash = content_hash
        existing.status = "analyzing"
        create_resume_record(
            db=db,
            resume_id="resume-duplicate",
            filename="duplicate.txt",
            file_path="duplicate.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        db.commit()
    finally:
        db.close()

    analyze_calls = []
    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: raw_text)
    monkeypatch.setattr(tasks, "analyze_resume", lambda raw_text, target_role: analyze_calls.append(1))

    with pytest.raises(Retry):
        tasks.analyze_resume_task.apply(
            args=("resume-duplicate", "duplicate.txt", target_role),
            throw=True,
        )

    db = SessionLocal()
    try:
        duplicate = get_resume_by_id(db, "resume-duplicate")
        assert duplicate.status == "pending"
        assert duplicate.content_hash != content_hash
        assert analyze_calls == []
    finally:
        db.close()


def test_analyze_task_reanalyzes_when_duplicate_record_failed(monkeypatch, session_factory):
    """相同内容的旧记录 failed 时，新上传应释放旧 hash 并重新分析。"""
    from app.modules.resume import tasks

    SessionLocal = session_factory
    raw_text = "相同简历内容"
    target_role = "Python 后端"
    content_hash = tasks._resume_content_hash(raw_text, target_role)
    expected = _analysis_result("王五")

    db = SessionLocal()
    try:
        failed = create_resume_record(
            db=db,
            resume_id="resume-failed",
            filename="failed.txt",
            file_path="failed.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        failed.content_hash = content_hash
        failed.status = "failed"
        failed.analysis_result = {"error": "LLM 暂时失败"}
        create_resume_record(
            db=db,
            resume_id="resume-retry",
            filename="retry.txt",
            file_path="retry.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        db.commit()
    finally:
        db.close()

    analyze_calls = []
    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: raw_text)

    def fake_analyze(raw_text_arg, target_role_arg):
        analyze_calls.append((raw_text_arg, target_role_arg))
        return expected

    monkeypatch.setattr(tasks, "analyze_resume", fake_analyze)

    result = tasks.analyze_resume_task.apply(
        args=("resume-retry", "retry.txt", target_role)
    ).get()

    db = SessionLocal()
    try:
        failed = get_resume_by_id(db, "resume-failed")
        retry = get_resume_by_id(db, "resume-retry")
        assert result == {"status": "completed", "result": expected}
        assert failed.content_hash != content_hash
        assert failed.status == "failed"
        assert retry.content_hash == content_hash
        assert retry.status == "completed"
        assert retry.analysis_result == expected
        assert analyze_calls == [(raw_text, target_role)]
    finally:
        db.close()


def test_duplicate_wait_marks_record_failed_after_retry_budget_exhausted(
    monkeypatch,
    session_factory,
):
    """等待同内容进行中任务超过预算后，当前记录应落为 failed，避免永久 pending。"""
    from app.modules.resume import tasks

    SessionLocal = session_factory
    raw_text = "相同简历内容"
    target_role = "Python 后端"
    content_hash = tasks._resume_content_hash(raw_text, target_role)

    db = SessionLocal()
    try:
        existing = create_resume_record(
            db=db,
            resume_id="resume-existing",
            filename="existing.txt",
            file_path="existing.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        existing.content_hash = content_hash
        existing.status = "analyzing"
        create_resume_record(
            db=db,
            resume_id="resume-duplicate",
            filename="duplicate.txt",
            file_path="duplicate.txt",
            file_ext=".txt",
            target_role=target_role,
        )
        db.commit()
    finally:
        db.close()

    analyze_calls = []
    monkeypatch.setattr(tasks, "SessionLocal", SessionLocal)
    monkeypatch.setattr(tasks, "parse_resume", lambda file_path: raw_text)
    monkeypatch.setattr(tasks, "analyze_resume", lambda raw_text, target_role: analyze_calls.append(1))

    with pytest.raises(RuntimeError, match="duplicate_in_progress"):
        tasks.analyze_resume_task.apply(
            args=("resume-duplicate", "duplicate.txt", target_role),
            retries=tasks._DUPLICATE_WAIT_MAX_RETRIES,
            throw=True,
        )

    db = SessionLocal()
    try:
        duplicate = get_resume_by_id(db, "resume-duplicate")
        assert duplicate.status == "failed"
        assert duplicate.analysis_result == {"error": "duplicate_in_progress"}
        assert analyze_calls == []
    finally:
        db.close()
