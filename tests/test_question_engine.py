from unittest.mock import patch

import pytest

SAMPLE_SKILL = """## 考察范围
- Python 基础：数据结构、装饰器、生成器、GIL
- Web 框架：FastAPI / Flask 路由、中间件、依赖注入

## 难度分布
- easy：40%（基础概念、定义、简单辨析）
- medium：40%（原理解释、场景应用、常见坑）
- hard：20%（系统设计、权衡、故障分析、性能与边界）

## 参考知识库
- collection: python_docs
"""


def test_load_skill_reads_markdown_content():
    """验证：load_skill 会读取 app/skills 下的 Markdown 内容。"""
    from app.modules.interview.question_engine import load_skill

    content = load_skill("python_backend")

    assert "## 考察范围" in content
    assert "Python 基础" in content


@pytest.mark.parametrize("skill_name", ["missing_skill", "../python_backend"])
def test_load_skill_rejects_missing_or_invalid_skill_name(skill_name: str):
    """验证：不存在或非法的 skill 名不会被静默吞掉。"""
    from app.modules.interview.question_engine import load_skill

    with pytest.raises((FileNotFoundError, ValueError)):
        load_skill(skill_name)


def test_build_skill_blueprint_extracts_topics_distribution_collections_and_rubric():
    """验证：build_skill_blueprint 会把 Markdown Skill 转成结构化蓝图。"""
    from app.modules.interview.question_engine import build_skill_blueprint

    blueprint = build_skill_blueprint(SAMPLE_SKILL)

    assert blueprint["topics"] == ["Python 基础", "Web 框架"]
    assert blueprint["difficulty_distribution"] == {"easy": 0.4, "medium": 0.4, "hard": 0.2}
    assert blueprint["reference_collections"] == ["python_docs"]
    assert blueprint["difficulty_rubric"] == {
        "easy": "基础概念、定义、简单辨析",
        "medium": "原理解释、场景应用、常见坑",
        "hard": "系统设计、权衡、故障分析、性能与边界",
    }


def test_generate_question_returns_structured_question_and_passes_context():
    """验证：generate_question 会基于蓝图摘要调用 LLM，并返回结构化题目。"""
    from app.modules.interview.question_engine import build_skill_blueprint, generate_question

    blueprint = build_skill_blueprint(SAMPLE_SKILL)
    llm_result = {
        "question": "请解释 Python 的 GIL 及其影响。",
        "category": "Python 基础",
        "difficulty": "easy",
        "difficulty_reason": "该题只要求解释概念与直接影响，符合 easy rubric。",
        "follow_up_hint": "可追问多线程与多进程的区别。",
        "assessment_focus": "是否能准确说明 GIL 对 CPU 密集型任务的影响。",
    }

    with patch("app.modules.interview.question_engine.call_llm", return_value=llm_result) as mock_call:
        result = generate_question(
            blueprint,
            "easy",
            ["请解释什么是装饰器？"],
            covered_topics=["Web 框架"],
            candidate_context="候选人有 3 年 FastAPI 经验",
        )

    assert result == llm_result

    system_prompt, user_input = mock_call.call_args.args
    assert "easy" in system_prompt
    assert "基础概念、定义、简单辨析" in system_prompt
    assert "请解释什么是装饰器？" in system_prompt
    assert "Web 框架" in system_prompt
    assert "Python 基础" in system_prompt
    assert SAMPLE_SKILL not in system_prompt
    assert user_input == {"candidate_context": "候选人有 3 年 FastAPI 经验"}


def test_generate_question_rejects_mismatched_difficulty():
    """验证：模型返回的难度和请求值不一致时必须拒绝。"""
    from app.modules.interview.question_engine import build_skill_blueprint, generate_question

    blueprint = build_skill_blueprint(SAMPLE_SKILL)

    with patch(
        "app.modules.interview.question_engine.call_llm",
        return_value={
            "question": "请解释 Python 的 GIL 及其影响。",
            "category": "Python 基础",
            "difficulty": "hard",
            "difficulty_reason": "更偏系统设计。",
            "follow_up_hint": "可追问多线程与多进程的区别。",
            "assessment_focus": "是否理解并发模型。",
        },
    ):
        with pytest.raises(ValueError, match="difficulty"):
            generate_question(blueprint, "easy", [])


def test_generate_question_rejects_repeated_question():
    """验证：模型返回已问过的题目时必须拒绝。"""
    from app.modules.interview.question_engine import build_skill_blueprint, generate_question

    blueprint = build_skill_blueprint(SAMPLE_SKILL)

    with patch(
        "app.modules.interview.question_engine.call_llm",
        return_value={
            "question": "请解释什么是装饰器？",
            "category": "Python 基础",
            "difficulty": "easy",
            "difficulty_reason": "这是基础概念题。",
            "follow_up_hint": "继续追问闭包。",
            "assessment_focus": "是否理解装饰器与闭包。",
        },
    ):
        with pytest.raises(ValueError, match="重复"):
            generate_question(blueprint, "easy", ["请解释什么是装饰器？"])


def test_generate_question_rejects_missing_required_return_fields():
    """验证：模型缺少 difficulty_reason 或 assessment_focus 时必须拒绝。"""
    from app.modules.interview.question_engine import build_skill_blueprint, generate_question

    blueprint = build_skill_blueprint(SAMPLE_SKILL)

    with patch(
        "app.modules.interview.question_engine.call_llm",
        return_value={
            "question": "请解释 Python 的 GIL 及其影响。",
            "category": "Python 基础",
            "difficulty": "easy",
            "follow_up_hint": "可追问多线程与多进程的区别。",
        },
    ):
        with pytest.raises(Exception):
            generate_question(blueprint, "easy", [])


@pytest.mark.parametrize("difficulty", ["eazy", "基础", ""])
def test_generate_question_rejects_invalid_requested_difficulty(difficulty: str):
    """验证：非法请求难度会在调用 LLM 前被拒绝。"""
    from app.modules.interview.question_engine import build_skill_blueprint, generate_question

    blueprint = build_skill_blueprint(SAMPLE_SKILL)

    with patch("app.modules.interview.question_engine.call_llm") as mock_call:
        with pytest.raises(ValueError, match="difficulty"):
            generate_question(blueprint, difficulty, [])

    mock_call.assert_not_called()


def test_generate_follow_up_prefers_raw_text_when_llm_returns_non_json():
    """验证：追问生成遇到纯文本返回时，优先取 call_llm 的 raw 字段。"""
    from app.modules.interview.question_engine import generate_follow_up

    with patch(
        "app.modules.interview.question_engine.call_llm",
        return_value={"error": "模型返回格式异常，请重试", "raw": "你刚才提到 asyncio，那事件循环具体负责什么？"},
    ):
        result = generate_follow_up(
            "请解释 asyncio 的核心概念。",
            "我了解协程，但事件循环部分不太确定。",
            "继续深挖事件循环。",
        )

    assert result == "你刚才提到 asyncio，那事件循环具体负责什么？"
