from app.services.llm_service import call_llm


def analyze_jd_requirements(arguments: dict) -> dict:
    if "jd_text" not in arguments:
        return {"status": "error", "error": "缺少必填参数 jd_text"}

    jd_text = arguments["jd_text"]

    system_prompt = (
        "你是一个 JD 分析助手。"
        "分析用户提供的职位描述，返回 JSON 格式：{\"requirements\": [...], \"nice_to_have\": [...]}。"
        "只返回 JSON，不要多余文字。"
    )

    result = call_llm(system_prompt, {"jd_text": jd_text})

    if "error" in result:
        return {"status": "error", "error": "解析失败"}

    return {"status": "success", "result": result}
