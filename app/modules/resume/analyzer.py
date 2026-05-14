"""简历 AI 分析器 — 结构化 Prompt。"""

import hashlib

from app.services.llm_service import call_llm


def content_hash(text: str) -> str:
    """通用文本 SHA-256；任务级去重使用 tasks._resume_content_hash。"""
    if not text or not text.strip():
        raise ValueError("简历文本为空，无法计算哈希")
    return hashlib.sha256(text.encode()).hexdigest()


# 结构化 Prompt：要求 LLM 返回固定 JSON schema
ANALYSIS_SYSTEM_PROMPT = """你是专业的简历分析师。分析以下简历内容，返回 JSON 格式的结构化分析报告：
{
  "basic_info": {
    "name": "姓名",
    "education": "最高学历",
    "years_of_experience": "工作/项目年限",
    "skills": ["技能1", "技能2"]
  },
  "strengths": ["亮点1", "亮点2"],
  "weaknesses": ["不足1", "不足2"],
  "suggestions": ["优化建议1", "优化建议2"],
  "overall_score": 75,
  "match_analysis": "与目标岗位的匹配度分析（如果提供了目标岗位）"
}

要求：
1. overall_score 为 1-100 的整数评分
2. strengths/weaknesses/suggestions 各给出 2-5 条
3. 如果没有提供目标岗位，match_analysis 填写"未指定目标岗位"
4. 只返回 JSON，不要包含其他文字"""


def analyze_resume(resume_text: str, target_role: str = "") -> dict:
    """调用 LLM 分析简历，返回结构化结果"""
    payload = {"resume_text": resume_text}
    if target_role:
        payload["target_role"] = target_role

    return call_llm(ANALYSIS_SYSTEM_PROMPT, payload)
