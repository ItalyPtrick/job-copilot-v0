import json
import os

import redis

# 开发环境未配置时，回退到本地 Redis。
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 统一 Redis 客户端，供缓存封装函数复用。
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def set_session(session_id: str, data: dict, ttl: int = 3600) -> None:
    """缓存会话数据，并设置过期时间。"""
    redis_client.setex(session_id, ttl, json.dumps(data, ensure_ascii=False))


def get_session(session_id: str) -> dict | None:
    """获取会话数据，不存在时返回 None。"""
    raw = redis_client.get(session_id)
    if raw is None:
        return None
    return json.loads(raw)


def delete_session(session_id: str) -> None:
    """删除会话数据。"""
    redis_client.delete(session_id)
