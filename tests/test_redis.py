import json
from unittest.mock import patch

import pytest
import redis

from app.cache.redis_client import REDIS_URL, delete_session, get_session, set_session


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


def test_set_and_get_session():
    """验证：set/get 会正确调用 Redis，并完成 JSON 序列化与反序列化。"""
    session_id = "session_123"
    data = {"question": "你好"}

    with patch("app.cache.redis_client.redis_client") as mock_redis:
        set_session(session_id, data)
        mock_redis.setex.assert_called_once_with(
            session_id,
            3600,
            json.dumps(data, ensure_ascii=False),
        )

        mock_redis.get.return_value = json.dumps(data, ensure_ascii=False)
        result = get_session(session_id)

        assert result == data
        mock_redis.get.assert_called_once_with(session_id)


def test_delete_session():
    """验证：delete_session 会调用 Redis 删除指定 key。"""
    session_id = "session_123"

    with patch("app.cache.redis_client.redis_client") as mock_redis:
        delete_session(session_id)
        mock_redis.delete.assert_called_once_with(session_id)


@pytest.mark.skipif(not _is_redis_available(), reason="Redis is not available")
def test_redis_smoke():
    """验证：真实 Redis 环境下，set/get/delete 流程可正常工作。"""
    session_id = "test:redis_smoke_session"
    data = {"question": "smoke test", "step": 1}

    delete_session(session_id)
    set_session(session_id, data, ttl=60)
    assert get_session(session_id) == data

    delete_session(session_id)
    assert get_session(session_id) is None