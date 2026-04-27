import json
import uuid
from unittest.mock import patch

import pytest
import redis

from app.cache.redis_client import REDIS_URL
from app.modules.interview.schemas import InterviewStatus
from app.modules.interview.session_manager import (
    SESSION_PREFIX,
    SESSION_TTL,
    create_session,
    get_session,
    update_session,
)


_DEFAULT_DIFFICULTY_DISTRIBUTION = {
    "easy": 0.4,
    "medium": 0.4,
    "hard": 0.2,
}


def _build_session_payload(
    *,
    session_id: str = "session_123",
    status: str = InterviewStatus.CREATED.value,
    total_questions: int = 5,
    questions_asked: list[str] | None = None,
    current_question_index: int = 0,
) -> dict:
    """构造最小合法 session，便于测试读写时的规范化行为。"""
    return {
        "session_id": session_id,
        "config": {
            "skill": "python_backend",
            "total_questions": total_questions,
        },
        "status": status,
        "messages": [],
        "questions_asked": questions_asked or [],
        "current_question_index": current_question_index,
    }


def _is_redis_available() -> bool:
    """检查本地 Redis 是否可用，供 smoke test 决定是否跳过。"""
    client = None
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        return client.ping() is True
    except Exception:
        return False
    finally:
        if client is not None:
            client.close()


# 单元测试


def test_create_session_initializes_payload_and_prefixed_key():
    """验证：create_session 会补齐默认配置，并用 interview 前缀写入 Redis。"""
    fake_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with patch(
            "app.modules.interview.session_manager.uuid4", return_value=fake_uuid
        ):
            session_id = create_session(
                {"skill": "python_backend", "total_questions": 5}
            )

    assert session_id == str(fake_uuid)
    mock_redis.setex.assert_called_once()

    redis_key, ttl, raw_payload = mock_redis.setex.call_args.args
    payload = json.loads(raw_payload)

    assert redis_key == f"{SESSION_PREFIX}{session_id}"
    assert ttl == SESSION_TTL
    assert payload == {
        "session_id": session_id,
        "config": {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": 1,
            "difficulty_distribution": _DEFAULT_DIFFICULTY_DISTRIBUTION,
        },
        "status": InterviewStatus.CREATED.value,
        "messages": [],
        "questions_asked": [],
        "current_question_index": 0,
    }


@pytest.mark.parametrize(
    "config",
    [
        {"skill": "../not_a_skill", "total_questions": 5},  # 路径遍历攻击
        {"skill": "python_backend", "total_questions": 0},  # 题量不能为 0
        {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": -1,
        },  # 追问数不能负
        {
            "skill": "python_backend",
            "total_questions": 5,
            "difficulty_distribution": {"easy": 0.5, "medium": 0.5},
        },  # 缺少 hard
        {
            "skill": "python_backend",
            "total_questions": 5,
            "difficulty_distribution": {
                "easy": 0.4,
                "medium": 0.4,
                "hard": 0.2,
                "bonus": 0.0,
            },
        },  # 多余的 key
        {
            "skill": "python_backend",
            "total_questions": 5,
            "difficulty_distribution": {"easy": 1.2, "medium": -0.1, "hard": -0.1},
        },  # 权重超范围
        {
            "skill": "python_backend",
            "total_questions": 5,
            "difficulty_distribution": {"easy": 0.5, "medium": 0.4, "hard": 0.2},
        },  # 不加起来等于 1.0
    ],
)
def test_create_session_rejects_invalid_config(config: dict):
    """验证：非法 skill / 题量 / 难度配置不会被写进 Redis。"""
    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            create_session(config)
        mock_redis.setex.assert_not_called()


def test_get_session_returns_normalized_dict_or_none():
    """验证：get_session 会校验并规范化 session，不存在时返回 None。"""
    payload = _build_session_payload()
    expected_payload = {
        **payload,
        "config": {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": 1,
            "difficulty_distribution": _DEFAULT_DIFFICULTY_DISTRIBUTION,
        },
    }

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(payload, ensure_ascii=False)
        assert get_session("session_123") == expected_payload
        mock_redis.get.assert_called_once_with(f"{SESSION_PREFIX}session_123")

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = None
        assert get_session("session_456") is None
        mock_redis.get.assert_called_once_with(f"{SESSION_PREFIX}session_456")


def test_get_session_returns_none_for_invalid_json_or_invalid_shape():
    """验证：Redis 中的坏 JSON 或脏 session 不会直接炸成 500。"""
    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = "{bad json"
        assert get_session("session_789") is None

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            {"status": InterviewStatus.CREATED.value}
        )
        assert get_session("session_790") is None


def test_get_session_returns_none_for_invalid_nested_items():
    """验证：messages / questions_asked 的脏元素结构会被当作无效 session。"""
    invalid_message_payload = _build_session_payload()
    invalid_message_payload["messages"] = [{"role": "assistant"}]

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            invalid_message_payload, ensure_ascii=False
        )
        assert get_session("session_791") is None

    invalid_question_payload = _build_session_payload()
    invalid_question_payload["questions_asked"] = [{"q": "x"}]

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            invalid_question_payload, ensure_ascii=False
        )
        assert get_session("session_792") is None


def test_get_session_returns_none_for_invalid_progress_state():
    """验证：布尔题号、题序失配或越界索引会被当作无效 session。"""
    bool_index_payload = _build_session_payload()
    bool_index_payload["current_question_index"] = True

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(bool_index_payload, ensure_ascii=False)
        assert get_session("session_793") is None

    mismatched_progress_payload = _build_session_payload(
        status=InterviewStatus.IN_PROGRESS.value,
        questions_asked=["q1", "q2"],
        current_question_index=1,
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            mismatched_progress_payload,
            ensure_ascii=False,
        )
        assert get_session("session_794") is None

    skipped_index_payload = _build_session_payload()
    skipped_index_payload["current_question_index"] = 3

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            skipped_index_payload, ensure_ascii=False
        )
        assert get_session("session_795") is None

    overflow_index_payload = _build_session_payload(total_questions=2)
    overflow_index_payload["questions_asked"] = ["q1", "q2", "q3"]
    overflow_index_payload["current_question_index"] = 3

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            overflow_index_payload, ensure_ascii=False
        )
        assert get_session("session_796") is None

    overflow_questions_payload = _build_session_payload(total_questions=2)
    overflow_questions_payload["questions_asked"] = ["q1", "q2", "q3"]
    overflow_questions_payload["current_question_index"] = 2

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            overflow_questions_payload, ensure_ascii=False
        )
        assert get_session("session_797") is None


def test_get_session_returns_none_for_status_progress_mismatch():
    """验证：状态和进度对不上时，get_session 会把脏数据按缺失处理。"""
    created_progressed_payload = _build_session_payload(
        questions_asked=["q1"],
        current_question_index=1,
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            created_progressed_payload, ensure_ascii=False
        )
        assert get_session("session_797") is None

    idle_in_progress_payload = _build_session_payload(
        status=InterviewStatus.IN_PROGRESS.value
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        mock_redis.get.return_value = json.dumps(
            idle_in_progress_payload, ensure_ascii=False
        )
        assert get_session("session_798") is None

    for offset, terminal_status in enumerate(
        [
            InterviewStatus.COMPLETED.value,
            InterviewStatus.EVALUATING.value,
            InterviewStatus.EVALUATED.value,
        ],
        start=799,
    ):
        incomplete_terminal_payload = _build_session_payload(
            status=terminal_status,
            questions_asked=["q1", "q2", "q3", "q4"],
            current_question_index=4,
        )
        with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
            mock_redis.get.return_value = json.dumps(
                incomplete_terminal_payload,
                ensure_ascii=False,
            )
            assert get_session(f"session_{offset}") is None


def test_update_session_normalizes_payload_and_refreshes_ttl():
    """验证：update_session 只接受合法 session，并按统一结构写回 Redis。"""
    data = _build_session_payload(
        status=InterviewStatus.IN_PROGRESS.value,
        questions_asked=["q1"],
        current_question_index=1,
    )
    data["messages"] = [{"role": "assistant", "content": "你好"}]
    expected_payload = {
        **data,
        "config": {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": 1,
            "difficulty_distribution": _DEFAULT_DIFFICULTY_DISTRIBUTION,
        },
    }

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        update_session("session_123", data)
        mock_redis.setex.assert_called_once_with(
            f"{SESSION_PREFIX}session_123",
            SESSION_TTL,
            json.dumps(expected_payload, ensure_ascii=False),
        )


def test_update_session_rejects_invalid_shape():
    """验证：update_session 不会把半截 session 直接写进 Redis。"""
    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session(
                "session_123",
                {
                    "session_id": "session_123",
                    "status": InterviewStatus.IN_PROGRESS.value,
                },
            )
        mock_redis.setex.assert_not_called()


def test_update_session_rejects_mismatched_session_id():
    """验证：key 和 payload 的 session_id 不一致时必须拒绝写入。"""
    data = _build_session_payload(session_id="session_456")

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", data)
        mock_redis.setex.assert_not_called()


def test_update_session_rejects_invalid_nested_items():
    """验证：messages / questions_asked 的脏元素结构不会被写进 Redis。"""
    invalid_message_payload = _build_session_payload()
    invalid_message_payload["messages"] = [{"role": "assistant"}]

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", invalid_message_payload)
        mock_redis.setex.assert_not_called()

    invalid_question_payload = _build_session_payload()
    invalid_question_payload["questions_asked"] = [{"q": "x"}]

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", invalid_question_payload)
        mock_redis.setex.assert_not_called()


def test_update_session_rejects_invalid_progress_state():
    """验证：布尔题号、题序失配或越界索引不会被写进 Redis。"""
    bool_index_payload = _build_session_payload()
    bool_index_payload["current_question_index"] = True

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", bool_index_payload)
        mock_redis.setex.assert_not_called()

    mismatched_progress_payload = _build_session_payload(
        status=InterviewStatus.IN_PROGRESS.value,
        questions_asked=["q1", "q2"],
        current_question_index=1,
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", mismatched_progress_payload)
        mock_redis.setex.assert_not_called()

    skipped_index_payload = _build_session_payload()
    skipped_index_payload["current_question_index"] = 3

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", skipped_index_payload)
        mock_redis.setex.assert_not_called()

    overflow_index_payload = _build_session_payload(total_questions=2)
    overflow_index_payload["questions_asked"] = ["q1", "q2", "q3"]
    overflow_index_payload["current_question_index"] = 3

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", overflow_index_payload)
        mock_redis.setex.assert_not_called()

    overflow_questions_payload = _build_session_payload(total_questions=2)
    overflow_questions_payload["questions_asked"] = ["q1", "q2", "q3"]
    overflow_questions_payload["current_question_index"] = 2

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", overflow_questions_payload)
        mock_redis.setex.assert_not_called()


def test_update_session_rejects_status_progress_mismatch():
    """验证：状态和进度对不上时，update_session 会拒绝写回。"""
    created_progressed_payload = _build_session_payload(
        questions_asked=["q1"],
        current_question_index=1,
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", created_progressed_payload)
        mock_redis.setex.assert_not_called()

    idle_in_progress_payload = _build_session_payload(
        status=InterviewStatus.IN_PROGRESS.value
    )

    with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
        with pytest.raises(ValueError):
            update_session("session_123", idle_in_progress_payload)
        mock_redis.setex.assert_not_called()

    for terminal_status in [
        InterviewStatus.COMPLETED.value,
        InterviewStatus.EVALUATING.value,
        InterviewStatus.EVALUATED.value,
    ]:
        incomplete_terminal_payload = _build_session_payload(
            status=terminal_status,
            questions_asked=["q1", "q2", "q3", "q4"],
            current_question_index=4,
        )
        with patch("app.modules.interview.session_manager.redis_client") as mock_redis:
            with pytest.raises(ValueError):
                update_session("session_123", incomplete_terminal_payload)
            mock_redis.setex.assert_not_called()


# 集成测试


@pytest.mark.skipif(not _is_redis_available(), reason="Redis is not available")
def test_session_manager_smoke_create_get_update():
    """验证：真实 Redis 环境下，interview session 的 create/get/update 可正常工作。"""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    session_id = create_session({"skill": "python_backend", "total_questions": 5})
    redis_key = f"{SESSION_PREFIX}{session_id}"

    try:
        session = get_session(session_id)
        assert session is not None
        assert session["status"] == InterviewStatus.CREATED.value

        session["status"] = InterviewStatus.IN_PROGRESS.value
        session["questions_asked"] = ["q1"]
        session["current_question_index"] = 1
        update_session(session_id, session)

        updated_session = get_session(session_id)
        assert updated_session is not None
        assert updated_session["status"] == InterviewStatus.IN_PROGRESS.value

        ttl = client.ttl(redis_key)
        assert 0 < ttl <= SESSION_TTL
    finally:
        client.delete(redis_key)
        client.close()
