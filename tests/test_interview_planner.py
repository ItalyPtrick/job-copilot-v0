from app.modules.interview.interview_planner import (
    _build_base_difficulty_sequence,
    _decide_next_action,
    _evaluate_performance_signal,
    _pick_next_difficulty,
    plan_next_interview_action,
)

# ── 难度序列生成 ──────────────────────────────────────────────────────────────


def test_build_base_difficulty_sequence_default_distribution():
    """默认分布 {easy:0.4, medium:0.4, hard:0.2} + 5 题 → [e, e, m, m, h]。"""
    dist = {"easy": 0.4, "medium": 0.4, "hard": 0.2}
    seq = _build_base_difficulty_sequence(5, dist)
    assert seq == ["easy", "easy", "medium", "medium", "hard"]


def test_build_base_difficulty_sequence_custom_distribution():
    """自定义分布产生的序列长度正确，且每个元素都是合法难度。"""
    dist = {"easy": 0.33, "medium": 0.34, "hard": 0.33}
    seq = _build_base_difficulty_sequence(3, dist)
    assert len(seq) == 3
    assert all(d in ("easy", "medium", "hard") for d in seq)


def test_build_base_difficulty_sequence_single_question():
    """单题场景只返回一个元素。"""
    dist = {"easy": 0.4, "medium": 0.4, "hard": 0.2}
    seq = _build_base_difficulty_sequence(1, dist)
    assert len(seq) == 1


# ── 性能信号评估 ──────────────────────────────────────────────────────────────


def test_evaluate_performance_signal_strong_for_high_scores():
    """平均分 >= 7 → strong。"""
    perf = [{"score": 8}, {"score": 7}, {"score": 9}]
    assert _evaluate_performance_signal(perf) == "strong"


def test_evaluate_performance_signal_weak_for_low_scores():
    """平均分 < 4 → weak。"""
    perf = [{"score": 2}, {"score": 3}, {"score": 3}]
    assert _evaluate_performance_signal(perf) == "weak"


def test_evaluate_performance_signal_normal_for_medium_scores():
    """平均分在 [4, 7) → normal。"""
    perf = [{"score": 5}, {"score": 6}]
    assert _evaluate_performance_signal(perf) == "normal"


def test_evaluate_performance_signal_normal_for_empty():
    """空列表 → normal。"""
    assert _evaluate_performance_signal([]) == "normal"


# ── 难度调节 ─────────────────────────────────────────────────────────────────


def test_pick_next_difficulty_strong_promotes():
    """easy + strong → medium。"""
    assert _pick_next_difficulty("easy", "strong") == "medium"


def test_pick_next_difficulty_strong_no_double_jump():
    """验证：strong 信号不跨级（easy 不能直接跳到 hard）。"""
    result = _pick_next_difficulty(
        base_difficulty="easy",
        performance_signal="strong",
    )
    assert result != "hard"


def test_pick_next_difficulty_weak_demotes():
    """hard + weak → medium。"""
    assert _pick_next_difficulty("hard", "weak") == "medium"


def test_pick_next_difficulty_normal_keeps_base():
    """medium + normal → medium。"""
    assert _pick_next_difficulty("medium", "normal") == "medium"


# ── 决策逻辑 ─────────────────────────────────────────────────────────────────


def test_decide_next_action_complete_when_all_questions_asked():
    """题目用完且追问额度也用完 → complete。"""
    assert _decide_next_action(
        questions_remaining=0,
        follow_up_count=2,
        max_follow_ups=2,
        performance_signal="normal",
    ) == "complete"


def test_decide_next_action_follow_up_when_under_limit():
    """还有题且追问额度未满、回答非 strong → follow_up。"""
    assert _decide_next_action(
        questions_remaining=3,
        follow_up_count=0,
        max_follow_ups=2,
        performance_signal="normal",
    ) == "follow_up"


def test_decide_next_action_next_question_when_follow_up_limit_reached():
    """追问额度用完 → next_question。"""
    assert _decide_next_action(
        questions_remaining=3,
        follow_up_count=2,
        max_follow_ups=2,
        performance_signal="normal",
    ) == "next_question"


def test_decide_next_action_next_question_when_answer_is_strong():
    """回答质量 strong → 跳过追问，直接下一题。"""
    assert _decide_next_action(
        questions_remaining=3,
        follow_up_count=0,
        max_follow_ups=2,
        performance_signal="strong",
    ) == "next_question"


# ── 集成测试 ─────────────────────────────────────────────────────────────────


def test_plan_next_interview_action_returns_complete_structure():
    """返回值必须包含四个关键字段。"""
    session = {
        "config": {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": 1,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
        },
        "current_question_index": 5,
        "current_follow_up_count": 1,
        "current_main_question": None,
        "recent_performance": [],
        "covered_topics": [],
    }
    result = plan_next_interview_action(session)

    assert result["next_action"] == "complete"
    assert "reason" in result
    assert "next_difficulty" in result
    assert "performance_signal" in result


def test_plan_next_interview_action_follow_up_scenario():
    """追问场景：追问额度未满 + 回答非 strong → 返回 follow_up 并附带 focus。"""
    session = {
        "config": {
            "skill": "python_backend",
            "total_questions": 5,
            "follow_up_count": 2,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
        },
        "current_question_index": 2,
        "current_follow_up_count": 0,
        "current_main_question": {
            "question": "请解释 Python GIL。",
            "question_id": "q1",
            "difficulty": "easy",
            "follow_up_hint": "追问多线程与多进程区别",
            "assessment_focus": "并发模型理解",
        },
        "recent_performance": [{"score": 5}],
        "covered_topics": [],
    }
    result = plan_next_interview_action(session)

    assert result["next_action"] == "follow_up"
    assert result["follow_up_focus"] == "追问多线程与多进程区别"
