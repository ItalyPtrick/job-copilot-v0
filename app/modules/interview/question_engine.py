from pathlib import Path
import re

from app.modules.interview.schemas import InterviewQuestion
from app.services.llm_service import call_llm

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
_ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
_DEFAULT_DIFFICULTY_RUBRIC = {
    "easy": "基础概念、定义、简单辨析",
    "medium": "原理解释、场景应用、常见坑",
    "hard": "系统设计、权衡、故障分析、性能与边界",
}


def load_skill(skill_name: str) -> str:
    """加载指定方向的 Skill Markdown。"""
    if not skill_name or skill_name != Path(skill_name).name:
        raise ValueError("非法的 skill_name。")

    skill_path = _SKILLS_DIR / f"{skill_name}.md"
    return skill_path.read_text(encoding="utf-8")


def build_skill_blueprint(skill_content: str) -> dict:
    """把 Markdown Skill 解析成当前阶段需要的轻量蓝图。"""
    topics: list[str] = []
    difficulty_distribution: dict[str, float] = {}
    reference_collections: list[str] = []
    difficulty_rubric = dict(_DEFAULT_DIFFICULTY_RUBRIC)
    current_section = ""

    for raw_line in skill_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if not line.startswith("- "):
            continue

        item = line[2:].strip()
        if current_section == "考察范围":
            topics.append(item.split("：", 1)[0].strip())
        elif current_section == "难度分布":
            match = re.match(r"(easy|medium|hard)：(\d+)%（(.+)）", item)
            if not match:
                continue
            difficulty, percent, rubric = match.groups()
            difficulty_distribution[difficulty] = int(percent) / 100
            difficulty_rubric[difficulty] = rubric.strip()
        elif current_section == "参考知识库" and item.startswith("collection:"):
            reference_collections.append(item.split(":", 1)[1].strip())

    if not difficulty_distribution:  # 难度降级处理
        difficulty_distribution = {"easy": 0.4, "medium": 0.4, "hard": 0.2}

    return {
        "topics": topics,
        "difficulty_distribution": difficulty_distribution,
        "reference_collections": reference_collections,
        "difficulty_rubric": difficulty_rubric,
    }


def generate_question(
    skill_blueprint: dict,
    difficulty: str,
    asked_questions: list[str],
    covered_topics: list[str] | None = None,
    candidate_context: str = "",
) -> dict:
    """根据 Skill 蓝图和当前覆盖情况生成下一道结构化面试题。"""
    if difficulty not in _ALLOWED_DIFFICULTIES:
        raise ValueError("非法的 difficulty。")

    covered_topics = covered_topics or []
    topics = skill_blueprint.get("topics", [])
    target_topics = [topic for topic in topics if topic not in covered_topics] or topics
    difficulty_rubric = skill_blueprint.get(
        "difficulty_rubric", _DEFAULT_DIFFICULTY_RUBRIC
    )

    system_prompt = "\n".join(
        [
            "你是一名技术面试官，请基于给定面试蓝图生成下一道面试题。",
            f"目标难度：{difficulty}",
            f"目标难度说明：{difficulty_rubric[difficulty]}",
            "已问题目：",
            *(asked_questions or ["- 无"]),
            "已覆盖考点：",
            *(covered_topics or ["- 无"]),
            "本题优先覆盖考点：",
            *(target_topics or ["- 无"]),
            "不要重复以上已问过的题目。",
            "当前面试蓝图摘要：",
            f"- topics: {topics}",
            f"- difficulty_distribution: {skill_blueprint.get('difficulty_distribution', {})}",
            f"- reference_collections: {skill_blueprint.get('reference_collections', [])}",
            "请只返回 JSON，对象必须包含字段：question、category、difficulty、difficulty_reason、follow_up_hint、assessment_focus。",
        ]
    )
    result = InterviewQuestion(
        **call_llm(system_prompt, {"candidate_context": candidate_context})
    ).model_dump()
    if result["difficulty"] != difficulty:
        raise ValueError("LLM 返回的 difficulty 与请求值不一致。")
    if result["question"] in asked_questions:
        raise ValueError("LLM 返回了重复的题目。")
    return result


def generate_follow_up(
    original_question: str,
    candidate_answer: str,
    follow_up_focus: str,
    recent_context: str = "",
) -> str:
    """根据候选人回答生成一条有针对性的追问。"""
    system_prompt = "\n".join(
        [
            "你是一名技术面试官，请基于候选人的回答继续追问。",
            f"原始问题：{original_question}",
            f"候选人回答：{candidate_answer}",
            f"追问焦点：{follow_up_focus or '结合回答中的薄弱点继续深挖'}",
            f"最近上下文：{recent_context or '无'}",
            "只返回一句自然的追问文本。",
        ]
    )
    result = call_llm(system_prompt, {})
    return result.get("raw") or result.get("question") or str(result)
