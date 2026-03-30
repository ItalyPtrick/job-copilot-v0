# schemas.py
ANALYZE_JD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_jd_requirements",
        "description": "从 JD 文本中提取岗位要求关键词，用于后续简历匹配",
        "parameters": {
            "type": "object",
            "properties": {
                "jd_text": {
                    "type": "string",
                    "description": "JD描述原文",
                },
            },
            "required": ["jd_text"],
        },
    },
}

SCORE_RESUME_MATCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "score_resume_match",
        "description": "根据 JD 提取的岗位要求和简历内容，评估简历与岗位要求的匹配度",
        "parameters": {
            "type": "object",
            "properties": {
                "resume_text": {
                    "type": "string",
                    "description": "简历内容原文",
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "从 JD 提取的岗位要求列表",
                },
            },
            "required": ["resume_text", "requirements"],
        },
    },
}
