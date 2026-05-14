"""简历模块 API 测试。"""

import hashlib
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.connection import Base, get_db
from app.database.models import ResumeRecord
from app.modules.resume import router as resume_router
from app.modules.resume.service import create_resume_record

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_session_factory(tmp_path):
    """每个 API 测试使用独立 SQLite，避免污染本地开发库。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'resume_api.db'}")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def mock_resume_task(monkeypatch):
    """API 测试只验证入队参数，不依赖 Redis/Celery worker。"""
    queued = []

    def fake_delay(*args):
        queued.append(args)

    monkeypatch.setattr(resume_router.analyze_resume_task, "delay", fake_delay)
    return queued


def test_upload_returns_resume_id():
    """上传简历返回 202 + resume_id"""
    with open("tests/fixtures/test_resume.txt", "rb") as f:
        resp = client.post("/resume/upload", files={"file": ("resume.txt", f)})
    assert resp.status_code == 202
    data = resp.json()
    assert "resume_id" in data
    assert data["status"] == "analyzing"


def test_upload_rejects_markdown_because_parser_does_not_support_it():
    """上传层允许的扩展名必须与解析器一致。"""
    resp = client.post("/resume/upload", files={"file": ("resume.md", b"# resume")})

    assert resp.status_code == 400


def test_upload_invalid_format():
    """不支持的文件格式返回 400"""
    resp = client.post("/resume/upload", files={"file": ("bad.exe", b"data")})
    assert resp.status_code == 400


def test_upload_does_not_reuse_file_hash_record_before_analysis(
    mock_resume_task,
    isolated_session_factory,
):
    """上传接口不使用文件字节 hash 复用旧记录，去重统一交给分析任务。"""
    marker = uuid.uuid4().hex
    content = f"same resume bytes {marker}".encode()
    file_hash = hashlib.sha256(content).hexdigest()
    existing_resume_id = f"existing-file-hash-record-{marker}"
    db = isolated_session_factory()
    try:
        existing = create_resume_record(
            db=db,
            resume_id=existing_resume_id,
            filename="old.txt",
            file_path="data/resumes/old.txt",
            file_ext=".txt",
            target_role="",
        )
        existing.content_hash = file_hash
        db.commit()
        existing_id = str(existing.resume_id)
    finally:
        db.close()

    resp = client.post("/resume/upload", files={"file": ("resume.txt", content)})

    assert resp.status_code == 202
    data = resp.json()
    assert data["resume_id"] != existing_id
    assert mock_resume_task[-1][0] == data["resume_id"]


def test_list_resumes_rejects_invalid_pagination():
    """分页参数必须限制下界和最大 page_size。"""
    assert client.get("/resume/list?page=0").status_code == 422
    assert client.get("/resume/list?page_size=101").status_code == 422


def test_list_resumes():
    """验证 列表接口返回分页数据"""
    resp = client.get("/resume/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data


def test_get_status_not_found():
    """验证 不存在的 resume_id 返回 404"""
    missing_id = str(uuid.uuid4())

    resp = client.get(f"/resume/{missing_id}/status")

    assert resp.status_code == 404


def test_get_report_not_ready(isolated_session_factory):
    """验证 未完成分析时报告接口返回未就绪提示"""
    resume_id = str(uuid.uuid4())
    db = isolated_session_factory()
    try:
        create_resume_record(
            db=db,
            resume_id=resume_id,
            filename="pending.txt",
            file_path="data/resumes/pending.txt",
            file_ext=".txt",
            target_role="Python 后端",
        )
    finally:
        db.close()

    resp = client.get(f"/resume/{resume_id}/report")

    assert resp.status_code == 409
    assert "分析尚未完成" in resp.json()["detail"]


def test_duplicate_upload_reuses_result(monkeypatch, isolated_session_factory):
    """验证 上传相同内容两次，第二次复用第一次的分析结果"""
    from app.modules.resume import tasks

    expected = {
        "basic_info": {
            "name": "张三",
            "education": "本科",
            "years_of_experience": 3,
            "skills": ["Python"],
        },
        "strengths": ["项目经验完整"],
        "weaknesses": ["缺少量化成果"],
        "suggestions": ["补充指标"],
        "overall_score": 80,
        "match_analysis": "匹配 Python 后端岗位",
    }
    analyze_calls = []

    def fake_analyze(raw_text, target_role):
        analyze_calls.append((raw_text, target_role))
        return expected

    def run_sync(resume_id, file_path, target_role):
        return tasks.analyze_resume_task.apply(
            args=(resume_id, file_path, target_role)
        ).get()

    monkeypatch.setattr(tasks, "analyze_resume", fake_analyze)
    monkeypatch.setattr(tasks, "SessionLocal", isolated_session_factory)
    monkeypatch.setattr(resume_router.analyze_resume_task, "delay", run_sync)

    marker = uuid.uuid4().hex
    content = f"张三\nPython 后端\n{marker}".encode("utf-8")

    first = client.post(
        "/resume/upload",
        files={"file": ("resume.txt", content)},
        data={"target_role": "Python 后端"},
    )
    second = client.post(
        "/resume/upload",
        files={"file": ("resume.txt", content)},
        data={"target_role": "Python 后端"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    first_report = client.get(f"/resume/{first.json()['resume_id']}/report")
    second_report = client.get(f"/resume/{second.json()['resume_id']}/report")
    assert first_report.status_code == 200
    assert second_report.status_code == 200
    assert second_report.json()["analysis_result"] == first_report.json()["analysis_result"]
    assert analyze_calls == [(content.decode("utf-8"), "Python 后端")]


def test_upload_empty_file_returns_error():
    """验证 空文件上传返回合理错误提示"""
    resp = client.post("/resume/upload", files={"file": ("empty.txt", b"")})

    assert resp.status_code == 400
    assert "空文件" in resp.json()["detail"]


def test_upload_chinese_and_special_filename_saves_original_name(
    mock_resume_task,
    isolated_session_factory,
):
    """验证 中文和特殊字符文件名可正常保存"""
    filename = f"张三 简历 @#{uuid.uuid4().hex}.txt"

    resp = client.post(
        "/resume/upload",
        files={"file": (filename, "张三\nPython".encode("utf-8"))},
    )

    assert resp.status_code == 202
    db = isolated_session_factory()
    try:
        record = db.query(ResumeRecord).filter_by(resume_id=resp.json()["resume_id"]).first()
        assert record.filename == filename
        assert mock_resume_task[-1][0] == resp.json()["resume_id"]
    finally:
        db.close()


def test_get_status_rejects_invalid_resume_id_format():
    """验证 非法 resume_id 格式按不存在记录返回 404"""
    resp = client.get("/resume/not-a-valid-id/status")

    assert resp.status_code == 404
