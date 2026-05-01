import logging

from app.services.llm_service import call_llm

logger = logging.getLogger(__name__)

_BATCH_SIZE = 3  # 每批评审的主问题轮次上限

# 1-10 评分标准，写进 prompt 让 LLM 有锚点。
_SCORE_RUBRIC = """\
1-3：概念错误、答非所问、或完全不知道
4-5：知道概念但缺少原理，回答浅显或有明显遗漏
6-7：能解释原理并处理常见场景，回答基本完整
8-9：能结合经验、边界条件和权衡，回答有深度
10：回答完整且有结构化思考，近乎完美"""


def _extract_interview_turns(messages: list[dict]) -> list[dict]:
    """从 session messages 中提取结构化面试轮次。

    每个 turn 对应一道主问题，包含：
    - 主问题内容、category、difficulty、assessment_focus
    - 候选人对主问题的初答
    - 0~N 条追问及其回答
    """
    # 三遍扫描：主问题、追问、用户回答分别收集，最后按主问题组装。
    main_questions: dict[str, dict] = {}
    follow_ups: dict[str, list[dict]] = {}  # parent_question_id -> 追问列表
    answers: dict[str, str] = {}  # question_id -> 回答内容

    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        metadata = message.get("metadata") or {}

        if role == "assistant":
            question_type = metadata.get("question_type")
            question_id = metadata.get("question_id")
            if not question_id:
                continue

            if question_type == "main":
                main_questions[question_id] = {
                    "question_id": question_id,
                    "question": content,
                    "category": metadata.get("category", ""),
                    "difficulty": metadata.get("difficulty", ""),
                    "assessment_focus": metadata.get("assessment_focus", ""),
                }
            elif question_type == "follow_up":
                parent_id = metadata.get("parent_question_id")
                if parent_id:
                    follow_ups.setdefault(parent_id, []).append({
                        "question_id": question_id,
                        "question": content,
                    })

        elif role == "user":
            answer_to = metadata.get("answer_to_question_id")
            if answer_to:
                answers[answer_to] = content

    # 以主问题为单位组装 turn，追问按 parent_question_id 挂上去。
    turns: list[dict] = []
    for question_id, question_info in main_questions.items():
        turn = {
            **question_info,
            "answer": answers.get(question_id, ""),
            "follow_ups": [],
        }
        for follow_up in follow_ups.get(question_id, []):
            turn["follow_ups"].append({
                "question": follow_up["question"],
                "answer": answers.get(follow_up["question_id"], ""),
            })
        turns.append(turn)

    return turns


def _format_turn_for_prompt(turn: dict) -> str:
    """把一个 turn 格式化为 LLM 可读的评估文本。"""
    lines = [
        f"【主问题】{turn['question']}",
        f"考察方向：{turn['assessment_focus']}",
        f"难度：{turn['difficulty']}",
        f"类别：{turn['category']}",
        f"【候选人回答】{turn['answer']}",
    ]
    for index, follow_up in enumerate(turn["follow_ups"], 1):
        lines.append(f"【追问{index}】{follow_up['question']}")
        lines.append(f"【追问回答{index}】{follow_up['answer']}")
    return "\n".join(lines)


def evaluate_batch(turns: list[dict]) -> list[dict]:
    """对一批主问题轮次调用 LLM 评分，返回单题评估列表。

    每批评审 _BATCH_SIZE 个主问题轮次，综合主答和追问给分。
    LLM 解析失败时记录 warning，该批评分跳过（不静默吞掉全部）。
    """
    all_evaluations: list[dict] = []

    for batch_start in range(0, len(turns), _BATCH_SIZE):
        batch = turns[batch_start : batch_start + _BATCH_SIZE]
        turns_text = "\n\n".join(
            f"=== 题目 {index + 1} ===\n{_format_turn_for_prompt(turn)}"
            for index, turn in enumerate(batch)
        )

        system_prompt = "\n".join([
            "你是一名技术面试评估专家，请对以下面试轮次逐题评分。",
            "",
            "评分标准：",
            _SCORE_RUBRIC,
            "",
            "每道题的评分应综合主问题回答和追问回答（如果有）。",
            "请返回 JSON 数组，每个元素包含：",
            "- question_id: 对应题目 ID",
            "- score: 1-10 整数",
            "- feedback: 简短评价（说明扣分原因和亮点）",
            "",
            "只返回 JSON 数组，不要其他内容。",
            "",
            turns_text,
        ])

        result = call_llm(system_prompt, {})

        evaluations = _parse_evaluations(result, batch)
        if evaluations is None:
            logger.warning(
                "LLM 评估解析失败，跳过本批 %d 题。原始返回: %s",
                len(batch),
                str(result)[:200],
            )
            continue

        all_evaluations.extend(evaluations)

    return all_evaluations


def _parse_evaluations(result: dict, batch: list[dict]) -> list[dict] | None:
    """从 LLM 返回中解析评估结果，解析失败返回 None。"""
    if "error" in result:
        return None

    # call_llm 可能直接返回列表，也可能包在 dict 的某个字段里
    if isinstance(result, list):
        raw_items = result
    elif isinstance(result, dict) and "evaluations" in result:
        raw_items = result["evaluations"]
    else:
        return None

    if not isinstance(raw_items, list):
        return None

    # 按 question_id 关联回 batch，补齐 category / question / answer
    batch_map = {turn["question_id"]: turn for turn in batch}
    validated: list[dict] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        question_id = item.get("question_id")
        score = item.get("score")
        feedback = item.get("feedback", "")

        if not question_id or not isinstance(score, int):
            continue
        if not (1 <= score <= 10):
            continue

        if question_id not in batch_map:
            continue
        source_turn = batch_map[question_id]
        validated.append({
            "question_id": question_id,
            "question": source_turn.get("question", ""),
            "answer": source_turn.get("answer", ""),
            "score": score,
            "feedback": feedback,
            "category": source_turn.get("category", ""),
        })

    return validated if validated else None


def generate_report(all_evaluations: list[dict]) -> dict:
    """聚合所有批次的评估结果，生成面试总评报告。"""
    if not all_evaluations:
        return {
            "overall_score": 0.0,
            "summary": "无有效评估数据。",
            "strengths": [],
            "improvements": [],
            "items": [],
        }

    items = [
        {
            "question": evaluation["question"],
            "answer": evaluation["answer"],
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "category": evaluation["category"],
        }
        for evaluation in all_evaluations
    ]

    # 总分 = 所有题目平均分
    overall_score = round(
        sum(evaluation["score"] for evaluation in all_evaluations)
        / len(all_evaluations),
        1,
    )

    # 按 category 归类，识别强项和弱项
    category_scores: dict[str, list[int]] = {}
    for evaluation in all_evaluations:
        category = evaluation.get("category", "未分类")
        category_scores.setdefault(category, []).append(evaluation["score"])

    category_avg = {
        category: sum(scores) / len(scores)
        for category, scores in category_scores.items()
    }

    # 强项：平均分 >= 7，弱项：平均分 < 5
    strengths = [cat for cat, avg in category_avg.items() if avg >= 7]
    improvements = [cat for cat, avg in category_avg.items() if avg < 5]

    # 没有明显强项/弱项时，取最高/最低分的 category 兜底
    if not strengths and category_avg:
        best_category = max(category_avg, key=category_avg.get)
        strengths = [best_category]
    if not improvements and category_avg:
        worst_category = min(category_avg, key=category_avg.get)
        if category_avg[worst_category] < 7:
            improvements = [worst_category]

    summary = f"共评估 {len(all_evaluations)} 道题，总分 {overall_score}/10。"
    if strengths:
        summary += f" 强项：{'、'.join(strengths)}。"
    if improvements:
        summary += f" 薄弱：{'、'.join(improvements)}。"

    return {
        "overall_score": overall_score,
        "summary": summary,
        "strengths": strengths,
        "improvements": improvements,
        "items": items,
    }


def evaluate_interview(messages: list[dict]) -> dict:
    """面试评估入口：messages → 提取轮次 → 分批评估 → 汇总报告。"""
    turns = _extract_interview_turns(messages)
    if not turns:
        return generate_report([])

    all_evaluations = evaluate_batch(turns)
    return generate_report(all_evaluations)
