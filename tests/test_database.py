# tests/test_database.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.models.task_record import TaskRecord


@pytest.fixture
def db_session():
    """使用内存 SQLite 做测试，每个测试用例独立"""
    # 创建仅用于当前测试的内存数据库
    engine = create_engine("sqlite:///:memory:")
    # 根据模型创建所有测试表
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # 把 session 提供给测试函数
    yield session
    # 测试结束后释放资源，避免连接泄漏
    session.close()
    engine.dispose()


def test_create_task_record(db_session):
    """验证：任务记录可写入并可读回关键字段"""
    record = TaskRecord(
        task_type="jd_analyze",
        payload={"jd_text": "test"},
        status="success",
        result={"key": "value"},
    )
    # 持久化到数据库
    db_session.add(record)
    db_session.commit()

    # 从数据库查询并断言结果
    saved = db_session.query(TaskRecord).first()
    assert saved is not None
    assert saved.id is not None
    assert saved.task_type == "jd_analyze"
    assert saved.status == "success"


def test_query_by_task_type(db_session):
    """验证：按 task_type 过滤查询能返回正确数量"""
    records = [
        TaskRecord(task_type="jd_analyze", payload={"idx": 1}, status="success"),
        TaskRecord(task_type="jd_analyze", payload={"idx": 2}, status="success"),
        TaskRecord(
            task_type="resume_optimize",
            payload={"idx": 3},
            status="success",
        ),
    ]
    db_session.add_all(records)
    db_session.commit()

    saved_records = (
        db_session.query(TaskRecord).filter(TaskRecord.task_type == "jd_analyze").all()
    )
    # 只应命中两条 jd_analyze
    assert len(saved_records) == 2


def test_task_record_json_fields(db_session):
    """验证：JSON 字段（payload/result）可正确保存与读取"""
    record = TaskRecord(
        task_type="jd_analyze",
        payload={"jd_text": "test", "list": [1, 2, 3]},
        status="success",
        result={"summary": "ok"},
    )
    db_session.add(record)
    db_session.commit()

    saved = db_session.query(TaskRecord).first()
    assert saved is not None
    # 校验 JSON 内部结构未丢失
    assert saved.payload["jd_text"] == "test"
    assert saved.payload["list"] == [1, 2, 3]


def test_created_at_auto_set(db_session):
    """验证：created_at 会在插入时自动写入"""
    record = TaskRecord(
        task_type="jd_analyze",
        payload={"jd_text": "test"},
        status="success",
    )
    db_session.add(record)
    db_session.commit()

    saved = db_session.query(TaskRecord).first()
    assert saved is not None
    assert saved.created_at is not None
