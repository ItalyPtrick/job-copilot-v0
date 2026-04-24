# tests/test_database.py
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.crud.task_crud import get_recent_tasks, get_tasks_by_type
from app.database.models.task_record import TaskRecord


@pytest.fixture
def db_session():
    """使用内存 SQLite 做测试，每个测试用例独立"""
    # 这层 fixture 负责给数据库测试提供一份“每例独立”的表结构基线。
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
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
    db_session.add(record)
    db_session.commit()

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


def test_get_tasks_by_type_returns_filtered_records(db_session):
    records = [
        TaskRecord(task_type="jd_analyze", payload={"idx": 1}, status="success"),
        TaskRecord(task_type="resume_optimize", payload={"idx": 2}, status="success"),
        TaskRecord(task_type="jd_analyze", payload={"idx": 3}, status="success"),
    ]
    db_session.add_all(records)
    db_session.commit()

    result = get_tasks_by_type(db_session, "jd_analyze", limit=10)

    assert len(result) == 2
    assert all(record.task_type == "jd_analyze" for record in result)


def test_get_recent_tasks_returns_latest_records_in_desc_order(db_session):
    base_time = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    records = [
        TaskRecord(
            task_type="jd_analyze",
            payload={"idx": 1},
            status="success",
            created_at=base_time,
        ),
        TaskRecord(
            task_type="jd_analyze",
            payload={"idx": 2},
            status="success",
            created_at=base_time + timedelta(minutes=1),
        ),
        TaskRecord(
            task_type="jd_analyze",
            payload={"idx": 3},
            status="success",
            created_at=base_time + timedelta(minutes=2),
        ),
    ]
    db_session.add_all(records)
    db_session.commit()

    result = get_recent_tasks(db_session, limit=2)

    assert len(result) == 2
    assert [record.payload["idx"] for record in result] == [3, 2]
    assert result[0].created_at > result[1].created_at



def _load_migration_module(filename: str, module_name: str):
    # 迁移测试直接加载 revision 脚本，再把 Alembic op 绑定到当前连接执行。
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module



def test_upgrade_add_knowledge_document_fields_keeps_existing_sqlite_rows():
    # 先造出旧占位表和旧数据，再跑补字段迁移，才能复现真实升级路径。
    engine = create_engine("sqlite:///:memory:")
    placeholder_migration = _load_migration_module(
        "97eaf6c6be6f_add_placeholder_tables.py",
        "placeholder_tables_migration",
    )
    target_migration = _load_migration_module(
        "8ec36703fa78_add_knowledge_document_fields.py",
        "knowledge_fields_migration",
    )

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        placeholder_migration.op = operations
        target_migration.op = operations

        placeholder_migration.upgrade()
        connection.execute(
            text(
                "INSERT INTO knowledge_documents (created_at) VALUES ('2026-04-22 00:00:00')"
            )
        )

        target_migration.upgrade()

        columns = {column["name"] for column in inspect(connection).get_columns("knowledge_documents")}
        row = connection.execute(
            text(
                "SELECT filename, collection_name, file_path, file_hash, chunks_count, status, file_size "
                "FROM knowledge_documents"
            )
        ).mappings().one()

    assert {
        "id",
        "created_at",
        "filename",
        "collection_name",
        "file_path",
        "file_hash",
        "chunks_count",
        "status",
        "file_size",
    }.issubset(columns)
    assert row == {
        "filename": "unknown",
        "collection_name": "default",
        "file_path": "",
        "file_hash": "",
        "chunks_count": 0,
        "status": "completed",
        "file_size": 0,
    }


def test_upgrade_unique_constraint_dedup_preserves_completed_and_legacy_hashes():
    # 验证 8cd951190b78 迁移：空 hash 填占位、优先保留 completed、唯一约束创建成功。
    engine = create_engine("sqlite:///:memory:")
    placeholder_migration = _load_migration_module(
        "97eaf6c6be6f_add_placeholder_tables.py",
        "placeholder_tables_migration",
    )
    fields_migration = _load_migration_module(
        "8ec36703fa78_add_knowledge_document_fields.py",
        "knowledge_fields_migration",
    )
    target_migration = _load_migration_module(
        "8cd951190b78_add_kb_upload_unique_constraint_and_.py",
        "unique_constraint_migration",
    )

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        placeholder_migration.op = operations
        fields_migration.op = operations
        target_migration.op = operations

        placeholder_migration.upgrade()
        fields_migration.upgrade()

        # 造脏数据：2 条空 hash（模拟旧逻辑回填）+ 1 组重复 hash（completed + failed）。
        connection.execute(
            text(
                "INSERT INTO knowledge_documents "
                "(filename, collection_name, file_path, file_hash, chunks_count, status, file_size, created_at) "
                "VALUES "
                "('a.txt', 'default', '/a1', '', 1, 'completed', 100, '2026-04-22 00:00:00'), "
                "('b.txt', 'default', '/b1', '', 2, 'completed', 200, '2026-04-22 01:00:00'), "
                "('c.txt', 'col2', '/c1', 'abc123', 3, 'completed', 300, '2026-04-22 02:00:00'), "
                "('c.txt', 'col2', '/c2', 'abc123', 0, 'failed', 300, '2026-04-22 03:00:00')"
            )
        )

        target_migration.upgrade()

        rows = connection.execute(
            text("SELECT id, filename, file_hash, status FROM knowledge_documents ORDER BY id")
        ).mappings().all()

    # 空 hash 应各自获得唯一占位，不被合并。
    assert len(rows) == 3
    assert rows[0]["file_hash"] == "legacy-1"
    assert rows[1]["file_hash"] == "legacy-2"
    # 重复 hash 组应保留 completed 而非 failed。
    assert rows[2]["filename"] == "c.txt"
    assert rows[2]["status"] == "completed"
    assert rows[2]["file_hash"] == "abc123"
