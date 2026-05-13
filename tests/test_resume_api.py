"""简历模块 API 测试。"""

import hashlib
import uuid

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.database.connection import SessionLocal
from app.modules.resume.service import create_resume_record

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_resume_task(monkeypatch):
    """API 测试只验证入队参数，不依赖 Redis/Celery worker。"""
    queued = []

    def fake_delay(*args):
        queued.append(args)

    monkeypatch.setattr("app.modules.resume.router.analyze_resume_task.delay", fake_delay)
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


def test_upload_does_not_reuse_file_hash_record_before_analysis(mock_resume_task):
    """上传接口不使用文件字节 hash 复用旧记录，去重统一交给分析任务。"""
    marker = uuid.uuid4().hex
    content = f"same resume bytes {marker}".encode()
    file_hash = hashlib.sha256(content).hexdigest()
    existing_resume_id = f"existing-file-hash-record-{marker}"
    db = SessionLocal()
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
    """列表接口返回分页数据"""
    resp = client.get("/resume/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
