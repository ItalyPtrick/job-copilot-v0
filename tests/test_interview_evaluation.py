"""evaluation.py 测试：轮次提取、分批评估、汇总报告、入口函数。"""

from unittest.mock import patch

import pytest

from app.modules.interview.evaluation import (
    _extract_interview_turns,
    evaluate_batch,
    evaluate_interview,
    generate_report,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _build_main_message(question_id: str, content: str, **extra) -> dict:
    """构造主问题 assistant 消息。"""
    metadata = {
        "question_type": "main",
        "question_id": question_id,
        "parent_question_id": None,
        "category": extra.pop("category", "Python 基础"),
        "difficulty": extra.pop("difficulty", "medium"),
        "assessment_focus": extra.pop("assessment_focus", "考察基础概念"),
        **extra,
    }
    return {"role": "assistant", "content": content, "metadata": metadata}


def _build_follow_up_message(question_id: str, parent_id: str, content: str) -> dict:
    """构造追问 assistant 消息。"""
    return {
        "role": "assistant",
        "content": content,
        "metadata": {
            "question_type": "follow_up",
            "question_id": question_id,
            "parent_question_id": parent_id,
        },
    }


def _build_answer_message(answer_to: str, content: str) -> dict:
    """构造用户回答消息。"""
    return {
        "role": "user",
        "content": content,
        "metadata": {"answer_to_question_id": answer_to},
    }


def _build_sample_messages() -> list[dict]:
    """构造含 2 道主问题、1 条追问的完整消息序列。"""
    return [
        _build_main_message("q_1", "什么是 GIL？", category="并发编程"),
        _build_answer_message("q_1", "GIL 是 Python 的全局解释器锁..."),
        _build_follow_up_message("q_1_fu_1", "q_1", "GIL 对多线程 IO 密集型任务有影响吗？"),
        _build_answer_message("q_1_fu_1", "IO 密集型任务影响不大，因为线程在等待 IO 时会释放 GIL..."),
        _build_main_message("q_2", "解释装饰器的工作原理", category="Python 基础"),
        _build_answer_message("q_2", "装饰器是一个接受函数作为参数的高阶函数..."),
    ]


# ── _extract_interview_turns ─────────────────────────────────────────────


class TestExtractInterviewTurns:
    def test_basic_extraction(self):
        messages = _build_sample_messages()
        turns = _extract_interview_turns(messages)

        assert len(turns) == 2

        # 第一题有追问
        first_turn = turns[0]
        assert first_turn["question_id"] == "q_1"
        assert first_turn["question"] == "什么是 GIL？"
        assert first_turn["category"] == "并发编程"
        assert first_turn["answer"] == "GIL 是 Python 的全局解释器锁..."
        assert len(first_turn["follow_ups"]) == 1
        assert first_turn["follow_ups"][0]["question"].startswith("GIL 对多线程")
        assert first_turn["follow_ups"][0]["answer"].startswith("IO 密集型")

        # 第二题无追问
        second_turn = turns[1]
        assert second_turn["question_id"] == "q_2"
        assert second_turn["follow_ups"] == []

    def test_empty_messages(self):
        assert _extract_interview_turns([]) == []

    def test_no_metadata_messages_skipped(self):
        messages = [
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "你好"},
        ]
        assert _extract_interview_turns(messages) == []

    def test_follow_up_without_parent_skipped(self):
        """孤立追问（parent 不存在）不出现在任何 turn 中。"""
        messages = [
            _build_follow_up_message("fu_orphan", "q_nonexist", "追问？"),
        ]
        assert _extract_interview_turns(messages) == []

    def test_multiple_follow_ups(self):
        """一道主问题带多条追问。"""
        messages = [
            _build_main_message("q_1", "问题一"),
            _build_answer_message("q_1", "回答一"),
            _build_follow_up_message("fu_1", "q_1", "追问 1？"),
            _build_answer_message("fu_1", "追问回答 1"),
            _build_follow_up_message("fu_2", "q_1", "追问 2？"),
            _build_answer_message("fu_2", "追问回答 2"),
        ]
        turns = _extract_interview_turns(messages)
        assert len(turns) == 1
        assert len(turns[0]["follow_ups"]) == 2

    def test_user_answer_without_metadata_ignored(self):
        """仅带 answer_to_question_id 的 user 消息才归入 turn。"""
        messages = [
            _build_main_message("q_1", "问题？"),
            {"role": "user", "content": "这是普通对话，不是回答"},
            _build_answer_message("q_1", "这才是正式回答"),
        ]
        turns = _extract_interview_turns(messages)
        assert turns[0]["answer"] == "这才是正式回答"


# ── evaluate_batch ───────────────────────────────────────────────────────


class TestEvaluateBatch:
    def _mock_call_llm(self, system_prompt: str, user_input: dict) -> dict:
        """模拟 LLM 返回标准评分结果。"""
        return [
            {"question_id": "q_1", "score": 8, "feedback": "回答清晰有深度"},
            {"question_id": "q_2", "score": 6, "feedback": "基本正确但缺少细节"},
        ]

    def test_evaluate_batch_success(self):
        turns = _extract_interview_turns(_build_sample_messages())

        with patch(
            "app.modules.interview.evaluation.call_llm",
            side_effect=self._mock_call_llm,
        ):
            evaluations = evaluate_batch(turns)

        assert len(evaluations) == 2
        assert evaluations[0]["question_id"] == "q_1"
        assert evaluations[0]["score"] == 8
        assert evaluations[0]["category"] == "并发编程"
        assert evaluations[1]["question_id"] == "q_2"

    def test_evaluate_batch_llm_parse_failure(self):
        """LLM 返回不可解析数据时，该批被跳过，不崩溃。"""
        turns = _extract_interview_turns(_build_sample_messages())

        with patch(
            "app.modules.interview.evaluation.call_llm",
            return_value={"error": "模型返回格式异常", "raw": "not json"},
        ):
            evaluations = evaluate_batch(turns)

        assert evaluations == []

    def test_evaluate_batch_partial_invalid_items(self):
        """LLM 返回部分有效、部分无效的混合数据。"""
        turns = _extract_interview_turns(_build_sample_messages())

        def mixed_return(system_prompt: str, user_input: dict) -> dict:
            return [
                {"question_id": "q_1", "score": 7, "feedback": "还行"},
                {"question_id": "q_2", "score": 99, "feedback": "分数越界"},  # 无效
                {"question_id": "q_3", "score": "abc", "feedback": "类型错误"},  # 无效
            ]

        with patch(
            "app.modules.interview.evaluation.call_llm",
            side_effect=mixed_return,
        ):
            evaluations = evaluate_batch(turns)

        # 只有 q_1 的评分被保留
        assert len(evaluations) == 1
        assert evaluations[0]["question_id"] == "q_1"


# ── generate_report ──────────────────────────────────────────────────────


class TestGenerateReport:
    def test_full_report(self):
        evaluations = [
            {"question_id": "q_1", "question": "Q1", "answer": "A1",
             "score": 8, "feedback": "好", "category": "并发"},
            {"question_id": "q_2", "question": "Q2", "answer": "A2",
             "score": 4, "feedback": "弱", "category": "基础"},
        ]
        report = generate_report(evaluations)

        assert report["overall_score"] == 6.0
        assert len(report["items"]) == 2
        assert "并发" in report["strengths"]
        assert "基础" in report["improvements"]
        assert "6.0/10" in report["summary"]

    def test_empty_evaluations(self):
        report = generate_report([])
        assert report["overall_score"] == 0.0
        assert report["items"] == []

    def test_single_high_score(self):
        evaluations = [
            {"question_id": "q_1", "question": "Q1", "answer": "A1",
             "score": 9, "feedback": "优秀", "category": "设计"},
        ]
        report = generate_report(evaluations)
        assert report["overall_score"] == 9.0
        assert "设计" in report["strengths"]
        # 高分不应出现在改进项
        assert "设计" not in report["improvements"]

    def test_same_category_multiple_scores(self):
        """同类别多题取平均来判断强弱。"""
        evaluations = [
            {"question_id": "q_1", "question": "Q1", "answer": "A1",
             "score": 8, "feedback": "", "category": "基础"},
            {"question_id": "q_2", "question": "Q2", "answer": "A2",
             "score": 3, "feedback": "", "category": "基础"},
        ]
        report = generate_report(evaluations)
        # 平均 5.5，不 >= 7 也不 < 5，取最高分的作为强项
        assert report["overall_score"] == 5.5


# ── evaluate_interview ───────────────────────────────────────────────────


class TestEvaluateInterview:
    def test_full_pipeline(self):
        messages = _build_sample_messages()

        def mock_llm(system_prompt: str, user_input: dict) -> dict:
            return [
                {"question_id": "q_1", "score": 8, "feedback": "好"},
                {"question_id": "q_2", "score": 6, "feedback": "一般"},
            ]

        with patch(
            "app.modules.interview.evaluation.call_llm",
            side_effect=mock_llm,
        ):
            report = evaluate_interview(messages)

        assert report["overall_score"] == 7.0
        assert len(report["items"]) == 2
        assert isinstance(report["summary"], str)

    def test_empty_messages(self):
        report = evaluate_interview([])
        assert report["overall_score"] == 0.0
        assert "无有效评估数据" in report["summary"]

    def test_no_valid_turns(self):
        """消息里没有带 metadata 的 assistant 消息。"""
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
        ]
        report = evaluate_interview(messages)
        assert report["overall_score"] == 0.0


# ── schemas import check ────────────────────────────────────────────────


class TestSchemaImport:
    def test_import_metadata(self):
        """验证 InterviewMessageMetadata 可正常导入。"""
        from app.modules.interview.schemas import InterviewMessageMetadata

        metadata = InterviewMessageMetadata(
            question_type="main",
            question_id="q_1",
            parent_question_id=None,
            category="基础",
            difficulty="easy",
            assessment_focus="概念",
        )
        assert metadata.question_type == "main"
        assert metadata.answer_to_question_id is None

    def test_evaluate_interview_importable(self):
        """验收标准：直接 import 能跑通。"""
        from app.modules.interview.evaluation import evaluate_interview as fn

        assert callable(fn)
