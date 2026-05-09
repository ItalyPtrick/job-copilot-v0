"""自适应追问 planner：根据 session 状态和最新回答决定下一步动作。"""

from __future__ import annotations

# 难度等级排序，索引用于升降级计算
_DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def _build_base_difficulty_sequence(
    total_questions: int,
    difficulty_distribution: dict[str, float],
) -> list[str]:
    """按比例生成难度序列：先计算各难度题数，余量优先补给 medium。"""
    # 按 easy→medium→hard 顺序计算各难度的原始题数
    raw_counts: dict[str, float] = {
        level: total_questions * difficulty_distribution[level]
        for level in _DIFFICULTY_ORDER
    }
    # 取整后分配余量：medium 优先，其次 easy，最后 hard
    int_counts: dict[str, int] = {level: int(raw_counts[level]) for level in _DIFFICULTY_ORDER}
    remainder = total_questions - sum(int_counts.values())
    for level in ["medium", "easy", "hard"]:
        if remainder <= 0:
            break
        int_counts[level] += 1
        remainder -= 1

    # 按 easy→medium→hard 顺序拼接
    seq: list[str] = []
    for level in _DIFFICULTY_ORDER:
        seq.extend([level] * int_counts[level])
    return seq


def _evaluate_performance_signal(recent_performance: list[dict]) -> str:
    """根据近期表现评分返回 strong / normal / weak 信号。"""
    if not recent_performance:
        return "normal"
    avg = sum(item.get("score", 5) for item in recent_performance) / len(recent_performance)
    if avg >= 7:
        return "strong"
    if avg < 4:
        return "weak"
    return "normal"


def _pick_next_difficulty(base_difficulty: str, performance_signal: str) -> str:
    """根据性能信号对基础难度做单级升降。"""
    idx = _DIFFICULTY_ORDER.index(base_difficulty)
    if performance_signal == "strong" and idx < len(_DIFFICULTY_ORDER) - 1:
        return _DIFFICULTY_ORDER[idx + 1]
    if performance_signal == "weak" and idx > 0:
        return _DIFFICULTY_ORDER[idx - 1]
    return base_difficulty


def _decide_next_action(
    questions_remaining: int,
    follow_up_count: int,
    max_follow_ups: int,
    performance_signal: str,
) -> str:
    """决策下一步动作：complete / follow_up / next_question。"""
    # 主问题出完 → 追问或结束
    if questions_remaining <= 0:
        if follow_up_count < max_follow_ups and performance_signal != "strong":
            return "follow_up"
        return "complete"
    # 追问次数未满且回答非 strong → 追问
    if follow_up_count < max_follow_ups and performance_signal != "strong":
        return "follow_up"
    return "next_question"


def plan_next_interview_action(session: dict) -> dict:
    """主入口：综合 session 状态返回下一步决策。"""
    config = session["config"]
    total_questions = config["total_questions"]
    max_follow_ups = config.get("follow_up_count", 1)
    difficulty_distribution = config.get(
        "difficulty_distribution", {"easy": 0.4, "medium": 0.4, "hard": 0.2}
    )

    current_question_index = session.get("current_question_index", 0)
    current_follow_up_count = session.get("current_follow_up_count", 0)
    recent_performance = session.get("recent_performance", [])
    current_main_question = session.get("current_main_question")

    # 1. 评估性能信号
    performance_signal = _evaluate_performance_signal(recent_performance)

    # 2. 决策下一步动作
    questions_remaining = total_questions - current_question_index
    next_action = _decide_next_action(
        questions_remaining=questions_remaining,
        follow_up_count=current_follow_up_count,
        max_follow_ups=max_follow_ups,
        performance_signal=performance_signal,
    )

    # 3. 确定下一题难度
    base_seq = _build_base_difficulty_sequence(total_questions, difficulty_distribution)
    # 下一题主问题在序列中的索引：已完成的主问题数
    next_main_idx = min(current_question_index, len(base_seq) - 1)
    base_difficulty = base_seq[next_main_idx]
    next_difficulty = _pick_next_difficulty(base_difficulty, performance_signal)

    # 4. 追问焦点（仅 follow_up 时有意义）
    follow_up_focus = None
    if next_action == "follow_up" and current_main_question:
        follow_up_focus = current_main_question.get("follow_up_hint")

    # 5. 构建决策理由
    if next_action == "complete":
        reason = "所有问题和追问已完成。"
    elif next_action == "follow_up":
        reason = f"追问候选人（追问 {current_follow_up_count + 1}/{max_follow_ups}）。"
    else:
        reason = f"进入下一题主问题（性能信号: {performance_signal}）。"

    return {
        "next_action": next_action,
        "reason": reason,
        "follow_up_focus": follow_up_focus,
        "next_difficulty": next_difficulty,
        "performance_signal": performance_signal,
    }
