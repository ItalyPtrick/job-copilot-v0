import json
import logging
from uuid import uuid4

from pydantic import ValidationError

from app.cache.redis_client import redis_client
from app.modules.interview.schemas import InterviewConfig, InterviewStatus

SESSION_PREFIX = "interview:session:"  # Redis key 前缀
SESSION_TTL = 7200  # TTL 2 小时

logger = logging.getLogger(__name__)


def _build_session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _normalize_session_data(data: object) -> dict:
    """校验并规范化 session 结构，避免坏数据继续在 Redis 中扩散。"""
    # 验证最外层是 dict
    if not isinstance(data, dict):
        raise ValueError("Interview session 必须是字典。")

    # 验证 session_id
    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("Interview session 缺少有效的 'session_id'。")

    # 验证config
    try:
        normalized_config = InterviewConfig(**data["config"]).model_dump()
    except KeyError as exc:
        raise ValueError("Interview session 缺少 'config'。") from exc
    except ValidationError as exc:
        raise ValueError("Interview session 包含无效的 'config'。") from exc

    # 验证 status
    try:
        status = InterviewStatus(data["status"]).value
    except KeyError as exc:
        raise ValueError("Interview session 缺少 'status'。") from exc
    except ValueError as exc:
        raise ValueError("Interview session 包含无效的 'status'。") from exc

    # 验证 messages
    messages = data.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Interview session 的 'messages' 必须是列表。")
    for message in messages:
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
        ):
            raise ValueError(
                "Interview session 的 'messages' 项必须是包含字符串 'role' 和 'content' 的字典。"
            )

    # 验证 questions_asked
    questions_asked = data.get("questions_asked")
    if not isinstance(questions_asked, list):
        raise ValueError("Interview session 的 'questions_asked' 必须是列表。")
    if any(not isinstance(question, str) for question in questions_asked):
        raise ValueError("Interview session 的 'questions_asked' 项必须是字符串。")

    # 验证 current_question_index
    current_question_index = data.get("current_question_index")
    # bool 是 int 的子类，必须显式排除，避免 True 被当成题号 1。
    if type(current_question_index) is not int or current_question_index < 0:
        raise ValueError(
            "Interview session 的 'current_question_index' 必须是非负整数。"
        )

    # 验证题目进度一致性
    total_questions = normalized_config["total_questions"]
    # 防止题号越界、进度跳跃，以及“状态看似完成但主问题还没走完”的伪完成 session。
    if len(questions_asked) > total_questions:
        raise ValueError(
            "Interview session 的 'questions_asked' 不能超过配置的总问题数。"
        )
    if current_question_index != len(questions_asked):
        raise ValueError(
            "Interview session 的 'current_question_index' 必须等于已出问题数。"
        )
    if current_question_index > total_questions:
        raise ValueError(
            "Interview session 的 'current_question_index' 不能超过配置的总问题数。"
        )

    # 验证状态进度一致性
    if status == InterviewStatus.CREATED.value:
        if current_question_index != 0 or questions_asked:
            raise ValueError(
                "Interview session 处于 'created' 状态时不能有面试进度。"
            )
    elif status == InterviewStatus.IN_PROGRESS.value:
        if current_question_index == 0:
            raise ValueError(
                "Interview session 处于 'in_progress' 状态时必须有面试进度。"
            )
    elif status in {
        InterviewStatus.COMPLETED.value,
        InterviewStatus.EVALUATING.value,
        InterviewStatus.EVALUATED.value,
    }:
        if current_question_index != total_questions:
            raise ValueError(
                "Interview session 处于终止状态时必须完成所有配置的问题。"
            )

    return {
        "session_id": session_id,
        "config": normalized_config,
        "status": status,
        "messages": messages,
        "questions_asked": questions_asked,
        "current_question_index": current_question_index,
    }


def create_session(config: dict) -> str:
    """创建面试 session，并以 Redis JSON 形式写入。"""
    session_id = str(uuid4())

    # 先走 Pydantic 规范化，确保默认题量配置在 Redis 里是完整形态。
    session_data = _normalize_session_data(
        {
            "session_id": session_id,
            "config": config,
            "status": InterviewStatus.CREATED.value,
            # messages 约定为 OpenAI message 结构，后续 D3/D5 会直接追加 role/content。
            "messages": [],
            "questions_asked": [],
            "current_question_index": 0,
        }
    )
    redis_client.setex(
        _build_session_key(session_id),
        SESSION_TTL,
        json.dumps(session_data, ensure_ascii=False),
    )
    return session_id


def get_session(session_id: str) -> dict | None:
    """读取面试 session；坏 JSON 或脏结构按缺失处理，避免直接炸成 500。"""
    raw = redis_client.get(_build_session_key(session_id))
    if raw is None:
        return None

    try:
        return _normalize_session_data(json.loads(raw))
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Skip invalid interview session '%s': %s", session_id, exc)
        return None


def update_session(session_id: str, data: dict) -> None:
    """覆盖写回整份 session，并刷新 TTL。调用方应基于最新完整对象写回。"""
    normalized_data = _normalize_session_data(data)
    if normalized_data["session_id"] != session_id:
        raise ValueError("Interview session_id 在 payload 中与目标 key 不匹配。")
    redis_client.setex(
        _build_session_key(session_id),
        SESSION_TTL,
        json.dumps(normalized_data, ensure_ascii=False),
    )
