"""面试路由：/interview/start、/interview/answer、/interview/evaluate。"""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.modules.interview.evaluation import evaluate_answer_quality, evaluate_interview
from app.modules.interview.interview_planner import plan_next_interview_action
from app.modules.interview.question_engine import (
    build_skill_blueprint,
    generate_follow_up,
    generate_question,
    load_skill,
)
from app.modules.interview.session_manager import (
    create_session,
    get_session,
    update_session,
)
from app.modules.interview.schemas import InterviewConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["interview"])


# ============================================================
# Request / Response 模型
# ============================================================


class StartRequest(BaseModel):
    skill: str = "python_backend"
    total_questions: int = Field(default=10, ge=1)
    follow_up_count: int = Field(default=1, ge=0)
    difficulty_distribution: dict | None = None


class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1)


class EvaluateRequest(BaseModel):
    session_id: str


# ============================================================
# 辅助函数
# ============================================================

def _build_config_dict(request: StartRequest) -> dict:
    """把 StartRequest 转成 InterviewConfig 兼容的 dict。"""
    config: dict = {
        "skill": request.skill,
        "total_questions": request.total_questions,
        "follow_up_count": request.follow_up_count,
    }
    if request.difficulty_distribution is not None:
        config["difficulty_distribution"] = request.difficulty_distribution
    return config


def _generate_question_id() -> str:
    return f"q_{uuid4().hex[:8]}"


def _get_latest_assistant_question(messages: list[dict]) -> dict | None:
    """找到最近一条 assistant 问题，用来绑定用户回答。"""
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        metadata = message.get("metadata") or {}
        question_id = metadata.get("question_id")
        if question_id:
            return {
                "question_id": question_id,
                "question": message.get("content", ""),
                "assessment_focus": metadata.get("assessment_focus", ""),
            }
    return None


def _build_assistant_main_message(question_data: dict, question_id: str) -> dict:
    """把结构化题目转成可持久化的 assistant 主问题消息。"""
    return {
        "role": "assistant",
        "content": question_data["question"],
        "metadata": {
            "question_type": "main",
            "question_id": question_id,
            "parent_question_id": None,
            "category": question_data["category"],
            "difficulty": question_data["difficulty"],
            "assessment_focus": question_data["assessment_focus"],
        },
    }


def _build_current_main_question(question_data: dict, question_id: str) -> dict:
    """把结构化题目转成 planner 需要的当前主问题状态。"""
    return {
        "question": question_data["question"],
        "question_id": question_id,
        "difficulty": question_data["difficulty"],
        "follow_up_hint": question_data["follow_up_hint"],
        "assessment_focus": question_data["assessment_focus"],
    }


def _apply_main_question(session: dict, question_data: dict, question_id: str) -> None:
    """把一道主问题写入 session，并同步 planner 所需状态。"""
    session["messages"].append(
        _build_assistant_main_message(question_data, question_id)
    )
    session["questions_asked"].append(question_data["question"])
    session["current_question_index"] = len(session["questions_asked"])
    session["current_main_question"] = _build_current_main_question(
        question_data,
        question_id,
    )
    session["current_follow_up_count"] = 0
    if question_data["category"] not in session["covered_topics"]:
        session["covered_topics"].append(question_data["category"])


# ============================================================
# POST /interview/start
# ============================================================

@router.post("/start")
def start_interview(request: StartRequest):
    """创建 session，加载 Skill，出第一道主问题。"""
    try:
        config = InterviewConfig(**_build_config_dict(request)).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="面试配置无效。") from exc

    try:
        skill_content = load_skill(config["skill"])
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="面试 skill 无效。") from exc

    try:
        skill_blueprint = build_skill_blueprint(skill_content)
        # 生成第一道题：默认 easy，无已问题目、无已覆盖考点
        question_data = generate_question(
            skill_blueprint,
            difficulty="easy",
            asked_questions=[],
            covered_topics=[],
        )
    except (FileNotFoundError, RuntimeError, ValueError, ValidationError) as exc:
        logger.warning("面试启动出题失败: %s", exc)
        raise HTTPException(status_code=503, detail="面试服务暂时不可用。") from exc

    session_id = create_session(config)

    question_id = _generate_question_id()
    # 更新 session 状态：进入面试中
    session = get_session(session_id)
    session["status"] = "in_progress"
    _apply_main_question(session, question_data, question_id)
    update_session(session_id, session)

    return {
        "session_id": session_id,
        "question": question_data,
    }


# ============================================================
# POST /interview/answer
# ============================================================

@router.post("/answer")
def answer_question(request: AnswerRequest):
    """提交候选人回答，由 planner 决定追问/下一题/结束。"""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session 不存在。")
    if session["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Session 不在面试进行中。")

    current_main_question = session.get("current_main_question")
    if current_main_question is None:
        raise HTTPException(status_code=400, detail="当前没有进行中的主问题。")
    latest_question = _get_latest_assistant_question(session["messages"])
    if latest_question is None:
        raise HTTPException(status_code=400, detail="当前没有可回答的问题。")
    current_question_id = latest_question["question_id"]

    # 追加用户回答消息
    original_messages = list(session["messages"])
    original_recent_performance = list(session.get("recent_performance", []))
    user_message = {
        "role": "user",
        "content": request.answer,
        "metadata": {"answer_to_question_id": current_question_id},
    }
    session["messages"].append(user_message)

    try:
        answer_quality = evaluate_answer_quality(
            question=latest_question["question"],
            answer=request.answer,
            assessment_focus=(
                latest_question.get("assessment_focus")
                or current_main_question.get("assessment_focus", "")
            ),
        )
        performance_entry = {
            "question_id": current_question_id,
            "score": answer_quality["score"],
            "performance_signal": answer_quality["performance_signal"],
        }
        session.setdefault("recent_performance", [])
        session["recent_performance"].append(performance_entry)
        session["recent_performance"] = session["recent_performance"][-3:]

        # planner 决策
        plan = plan_next_interview_action(session)
        action = plan["next_action"]
        reason = plan["reason"]
        performance_signal = plan["performance_signal"]
        performance_entry["action"] = action

        response: dict = {
            "action": action,
            "reason": reason,
            "performance_signal": performance_signal,
        }

        if action == "follow_up":
            # 生成追问
            follow_up_text = generate_follow_up(
                original_question=current_main_question["question"],
                candidate_answer=request.answer,
                follow_up_focus=plan.get("follow_up_focus") or "",
            )
            follow_up_id = _generate_question_id()
            assistant_message = {
                "role": "assistant",
                "content": follow_up_text,
                "metadata": {
                    "question_type": "follow_up",
                    "question_id": follow_up_id,
                    "parent_question_id": current_main_question["question_id"],
                },
            }
            session["messages"].append(assistant_message)
            session["current_follow_up_count"] += 1
            response["follow_up"] = follow_up_text

        elif action == "next_question":
            # 出下一道主问题
            skill_blueprint = build_skill_blueprint(
                load_skill(session["config"]["skill"])
            )
            question_data = generate_question(
                skill_blueprint,
                difficulty=plan["next_difficulty"],
                asked_questions=session["questions_asked"],
                covered_topics=session["covered_topics"],
            )
            new_question_id = _generate_question_id()
            _apply_main_question(session, question_data, new_question_id)
            response["question"] = question_data

        elif action == "complete":
            session["status"] = "completed"
    except (FileNotFoundError, RuntimeError, ValueError, ValidationError) as exc:
        logger.warning("面试回答处理失败: %s", exc)
        session["messages"] = original_messages
        session["recent_performance"] = original_recent_performance
        update_session(request.session_id, session)
        raise HTTPException(status_code=503, detail="面试服务暂时不可用。") from exc

    update_session(request.session_id, session)
    return response


# ============================================================
# POST /interview/evaluate
# ============================================================

@router.post("/evaluate")
def evaluate_session(request: EvaluateRequest):
    """对已完成的面试 session 进行评估。"""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session 不存在。")
    if session["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="只能评估已完成（completed）的面试 session。",
        )

    # 调用评估引擎
    try:
        report = evaluate_interview(session["messages"])
    except RuntimeError as exc:
        logger.warning("面试评估失败: %s", exc)
        raise HTTPException(status_code=503, detail="评估服务暂时不可用。") from exc

    # 标记为已评估，把报告写回 session
    session["status"] = "evaluated"
    session["evaluation_report"] = report
    update_session(request.session_id, session)

    return report
