"""面试路由测试：/interview/start、/interview/answer、/interview/evaluate。"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------- Redis 内存模拟 ----------

class _FakeRedis:
    """用 dict 模拟 Redis 的 setex / get，供 session_manager 单测使用。"""

    def __init__(self):
        self._store: dict[str, str] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)


# ---------- Fixtures ----------

@pytest.fixture()
def fake_redis():
    return _FakeRedis()


@pytest.fixture()
def client(fake_redis):
    """构造 FastAPI TestClient，把 session_manager 的 redis_client 替换成内存模拟。"""
    # 每次新建 app，避免路由重复注册
    from fastapi import FastAPI

    from app.modules.interview.router import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.modules.interview.session_manager.redis_client", fake_redis):
        with TestClient(app) as c:
            yield c


# ---------- Mock 数据 ----------

_SAMPLE_SKILL_CONTENT = """## 考察范围
- Python 基础：数据结构、装饰器、生成器、GIL

## 难度分布
- easy：40%（基础概念、定义、简单辨析）
- medium：40%（原理解释、场景应用、常见坑）
- hard：20%（系统设计、权衡、故障分析、性能与边界）

## 参考知识库
- collection: python_docs
"""

_SAMPLE_BLUEPRINT = {
    "topics": ["Python 基础"],
    "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
    "reference_collections": ["python_docs"],
    "difficulty_rubric": {
        "easy": "基础概念",
        "medium": "原理解释",
        "hard": "系统设计",
    },
}

_SAMPLE_QUESTION = {
    "question": "请解释 Python 装饰器的工作原理。",
    "category": "Python 基础",
    "difficulty": "easy",
    "difficulty_reason": "基础概念",
    "follow_up_hint": "能否举例说明装饰器嵌套？",
    "assessment_focus": "装饰器",
}


# ---------- /interview/start ----------

@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.load_skill")
def test_start_returns_session_id_and_first_question(
    mock_load_skill, mock_build_blueprint, mock_generate_question, client
):
    """验证：/interview/start 返回 session_id 和第一道题。"""
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    mock_generate_question.return_value = _SAMPLE_QUESTION

    response = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "question" in data
    assert data["question"]["question"] == _SAMPLE_QUESTION["question"]


@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.load_skill")
def test_start_returns_503_without_orphan_session_when_question_generation_fails(
    mock_load_skill,
    mock_build_blueprint,
    mock_generate_question,
    fake_redis,
    client,
):
    """验证：出题失败时不创建孤儿 session。"""
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    mock_generate_question.side_effect = RuntimeError("LLM 出题失败")

    response = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 1},
    )

    assert response.status_code == 503
    assert fake_redis._store == {}


def test_start_returns_400_for_invalid_config_without_session(fake_redis, client):
    """验证：配置无效时返回 400，且不创建 session。"""
    response = client.post(
        "/interview/start",
        json={
            "skill": "python_backend",
            "total_questions": 1,
            "difficulty_distribution": {"easy": 0.5, "medium": 0.5},
        },
    )

    assert response.status_code == 400
    assert fake_redis._store == {}


# ---------- /interview/answer ----------

@patch("app.modules.interview.router.generate_follow_up")
@patch("app.modules.interview.router.plan_next_interview_action")
@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.load_skill")
def test_answer_returns_follow_up_when_planner_decides(
    mock_load_skill,
    mock_build_blueprint,
    mock_generate_question,
    mock_plan,
    mock_follow_up,
    client,
):
    """验证：planner 决定 follow_up 时，接口返回 action=follow_up 及追问内容。"""
    # 启动 session
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    mock_generate_question.return_value = _SAMPLE_QUESTION
    start_resp = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 2, "follow_up_count": 2},
    )
    session_id = start_resp.json()["session_id"]

    # planner 返回 follow_up
    mock_plan.return_value = {
        "next_action": "follow_up",
        "reason": "追问候选人。",
        "follow_up_focus": "装饰器嵌套",
        "next_difficulty": "easy",
        "performance_signal": "normal",
    }
    mock_follow_up.return_value = "你能再深入讲讲嵌套装饰器吗？"

    with patch(
        "app.modules.interview.router.evaluate_answer_quality",
        return_value={"score": 5, "performance_signal": "normal", "feedback": ""},
    ):
        answer_resp = client.post(
            "/interview/answer",
            json={"session_id": session_id, "answer": "装饰器是高阶函数。"},
        )

    assert answer_resp.status_code == 200
    data = answer_resp.json()
    assert data["action"] == "follow_up"
    assert "follow_up" in data


@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.plan_next_interview_action")
@patch("app.modules.interview.router.load_skill")
def test_answer_returns_next_question_after_follow_up_exhausted(
    mock_load_skill,
    mock_plan,
    mock_build_blueprint,
    mock_generate_question,
    fake_redis,
    client,
):
    """验证：planner 决定 next_question 时，返回 action=next_question 和新题目。"""
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    mock_generate_question.return_value = _SAMPLE_QUESTION

    # follow_up_count=0，直接进 next_question
    start_resp = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 2, "follow_up_count": 0},
    )
    session_id = start_resp.json()["session_id"]

    # 第二题用不同的返回
    second_question = {
        **_SAMPLE_QUESTION,
        "question": "GIL 是什么？",
        "category": "Python 基础",
    }
    mock_generate_question.return_value = second_question

    mock_plan.return_value = {
        "next_action": "next_question",
        "reason": "进入下一题主问题。",
        "follow_up_focus": None,
        "next_difficulty": "medium",
        "performance_signal": "normal",
    }

    with patch(
        "app.modules.interview.router.evaluate_answer_quality",
        return_value={"score": 5, "performance_signal": "normal", "feedback": ""},
    ):
        answer_resp = client.post(
            "/interview/answer",
            json={"session_id": session_id, "answer": "装饰器是高阶函数。"},
        )

    assert answer_resp.status_code == 200
    data = answer_resp.json()
    assert data["action"] == "next_question"
    assert "question" in data
    assert data["question"]["question"] == second_question["question"]

    session = json.loads(fake_redis.get(f"interview:session:{session_id}"))
    assert session["covered_topics"] == ["Python 基础"]


@patch("app.modules.interview.router.evaluate_answer_quality")
@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.load_skill")
def test_answer_strong_score_skips_follow_up_and_promotes_difficulty(
    mock_load_skill,
    mock_build_blueprint,
    mock_generate_question,
    mock_evaluate_answer,
    client,
):
    """验证：单答评分 strong 会进入下一题，并影响下一题难度。"""
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    second_question = {**_SAMPLE_QUESTION, "question": "GIL 是什么？", "difficulty": "hard"}
    mock_generate_question.side_effect = [_SAMPLE_QUESTION, second_question]
    mock_evaluate_answer.return_value = {
        "score": 8,
        "performance_signal": "strong",
        "feedback": "回答有深度",
    }

    start_resp = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 2, "follow_up_count": 1},
    )
    session_id = start_resp.json()["session_id"]

    answer_resp = client.post(
        "/interview/answer",
        json={"session_id": session_id, "answer": "装饰器是高阶函数。"},
    )

    assert answer_resp.status_code == 200
    assert answer_resp.json()["action"] == "next_question"
    assert mock_generate_question.call_args_list[1].kwargs["difficulty"] == "hard"


@patch("app.modules.interview.router.evaluate_answer_quality")
@patch("app.modules.interview.router.generate_follow_up")
@patch("app.modules.interview.router.generate_question")
@patch("app.modules.interview.router.build_skill_blueprint")
@patch("app.modules.interview.router.load_skill")
def test_follow_up_answer_attaches_to_latest_question_id(
    mock_load_skill,
    mock_build_blueprint,
    mock_generate_question,
    mock_follow_up,
    mock_evaluate_answer,
    fake_redis,
    client,
):
    """验证：追问后的回答绑定到追问 question_id，而不是主问题 ID。"""
    mock_load_skill.return_value = _SAMPLE_SKILL_CONTENT
    mock_build_blueprint.return_value = _SAMPLE_BLUEPRINT
    mock_generate_question.return_value = _SAMPLE_QUESTION
    mock_follow_up.return_value = "你能再深入讲讲嵌套装饰器吗？"
    mock_evaluate_answer.side_effect = [
        {"score": 5, "performance_signal": "normal", "feedback": ""},
        {"score": 8, "performance_signal": "strong", "feedback": ""},
    ]

    start_resp = client.post(
        "/interview/start",
        json={"skill": "python_backend", "total_questions": 1, "follow_up_count": 1},
    )
    session_id = start_resp.json()["session_id"]

    first_answer = client.post(
        "/interview/answer",
        json={"session_id": session_id, "answer": "装饰器是高阶函数。"},
    )
    assert first_answer.status_code == 200
    assert first_answer.json()["action"] == "follow_up"

    session_key = f"interview:session:{session_id}"
    session = json.loads(fake_redis.get(session_key))
    follow_up_id = session["messages"][-1]["metadata"]["question_id"]

    second_answer = client.post(
        "/interview/answer",
        json={"session_id": session_id, "answer": "嵌套装饰器按从内到外组合。"},
    )
    assert second_answer.status_code == 200

    session = json.loads(fake_redis.get(session_key))
    assert session["messages"][-1]["metadata"]["answer_to_question_id"] == follow_up_id


def test_answer_returns_404_for_missing_session(client):
    """验证：不存在的 session 返回 404。"""
    response = client.post(
        "/interview/answer",
        json={"session_id": "nonexistent", "answer": "test"},
    )
    assert response.status_code == 404


def test_evaluate_returns_404_for_missing_session(client):
    """验证：不存在的 session 返回 404。"""
    response = client.post(
        "/interview/evaluate",
        json={"session_id": "nonexistent"},
    )
    assert response.status_code == 404


# ---------- /interview/evaluate ----------

@patch("app.modules.interview.router.evaluate_interview")
def test_evaluate_rejects_non_completed_session(mock_evaluate, fake_redis, client):
    """验证：非 completed 状态的 session 调用 evaluate 返回 400。"""
    # 手动注入一个 in_progress 状态的 session
    session_data = {
        "session_id": "test-session-1",
        "config": {
            "skill": "python_backend",
            "total_questions": 1,
            "follow_up_count": 1,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
        },
        "status": "in_progress",
        "messages": [
            {
                "role": "assistant",
                "content": "请解释装饰器。",
                "metadata": {
                    "question_type": "main",
                    "question_id": "q_001",
                    "parent_question_id": None,
                    "category": "Python 基础",
                    "difficulty": "easy",
                    "assessment_focus": "装饰器",
                },
            },
            {
                "role": "user",
                "content": "装饰器是高阶函数。",
                "metadata": {"answer_to_question_id": "q_001"},
            },
        ],
        "questions_asked": ["请解释装饰器。"],
        "current_question_index": 1,
        "current_main_question": None,
        "current_follow_up_count": 0,
        "covered_topics": ["Python 基础"],
        "recent_performance": [],
    }
    fake_redis.setex(
        "interview:session:test-session-1", 7200, json.dumps(session_data)
    )

    response = client.post(
        "/interview/evaluate",
        json={"session_id": "test-session-1"},
    )

    assert response.status_code == 400
    mock_evaluate.assert_not_called()


@patch("app.modules.interview.router.evaluate_interview")
def test_evaluate_returns_report_for_completed_session(
    mock_evaluate, fake_redis, client
):
    """验证：completed 状态的 session 调用 evaluate 返回评估报告。"""
    mock_evaluate.return_value = {
        "overall_score": 7.5,
        "summary": "表现不错。",
        "strengths": ["Python 基础"],
        "improvements": [],
        "items": [
            {
                "question": "请解释装饰器。",
                "answer": "装饰器是高阶函数。",
                "score": 8,
                "feedback": "回答准确。",
                "category": "Python 基础",
            }
        ],
    }

    session_data = {
        "session_id": "test-session-2",
        "config": {
            "skill": "python_backend",
            "total_questions": 1,
            "follow_up_count": 1,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
        },
        "status": "completed",
        "messages": [
            {
                "role": "assistant",
                "content": "请解释装饰器。",
                "metadata": {
                    "question_type": "main",
                    "question_id": "q_001",
                    "parent_question_id": None,
                    "category": "Python 基础",
                    "difficulty": "easy",
                    "assessment_focus": "装饰器",
                },
            },
            {
                "role": "user",
                "content": "装饰器是高阶函数。",
                "metadata": {"answer_to_question_id": "q_001"},
            },
        ],
        "questions_asked": ["请解释装饰器。"],
        "current_question_index": 1,
        "current_main_question": None,
        "current_follow_up_count": 0,
        "covered_topics": ["Python 基础"],
        "recent_performance": [],
    }
    fake_redis.setex(
        "interview:session:test-session-2", 7200, json.dumps(session_data)
    )

    response = client.post(
        "/interview/evaluate",
        json={"session_id": "test-session-2"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["overall_score"] == 7.5
    assert "summary" in data
    assert "strengths" in data
    assert "improvements" in data
    assert "items" in data
    mock_evaluate.assert_called_once()

    stored_session = json.loads(fake_redis.get("interview:session:test-session-2"))
    assert stored_session["status"] == "evaluated"
    assert stored_session["evaluation_report"] == mock_evaluate.return_value


def test_evaluate_returns_503_when_all_llm_batches_fail(fake_redis, client):
    """验证：评估批次全部失败时返回 503，不返回 200 空报告。"""
    session_data = {
        "session_id": "test-session-3",
        "config": {
            "skill": "python_backend",
            "total_questions": 1,
            "follow_up_count": 1,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
        },
        "status": "completed",
        "messages": [
            {
                "role": "assistant",
                "content": "请解释装饰器。",
                "metadata": {
                    "question_type": "main",
                    "question_id": "q_001",
                    "parent_question_id": None,
                    "category": "Python 基础",
                    "difficulty": "easy",
                    "assessment_focus": "装饰器",
                },
            },
            {
                "role": "user",
                "content": "装饰器是高阶函数。",
                "metadata": {"answer_to_question_id": "q_001"},
            },
        ],
        "questions_asked": ["请解释装饰器。"],
        "current_question_index": 1,
        "current_main_question": None,
        "current_follow_up_count": 0,
        "covered_topics": ["Python 基础"],
        "recent_performance": [],
    }
    fake_redis.setex(
        "interview:session:test-session-3", 7200, json.dumps(session_data)
    )

    with patch(
        "app.modules.interview.evaluation.call_llm",
        return_value={"error": "模型返回格式异常", "raw": ""},
    ):
        response = client.post(
            "/interview/evaluate",
            json={"session_id": "test-session-3"},
        )

    assert response.status_code == 503
