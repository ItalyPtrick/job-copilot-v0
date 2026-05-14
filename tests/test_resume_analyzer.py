"""简历分析器测试。"""

import pytest


def test_content_hash_returns_stable_sha256():
    """验证 相同简历文本生成稳定哈希"""
    from app.modules.resume.analyzer import content_hash

    first = content_hash("张三\nPython")
    second = content_hash("张三\nPython")

    assert first == second
    assert len(first) == 64


def test_content_hash_rejects_empty_text():
    """验证 空简历文本拒绝计算哈希"""
    from app.modules.resume.analyzer import content_hash

    with pytest.raises(ValueError, match="简历文本为空"):
        content_hash("  \n")


def test_analyze_resume_calls_llm_with_target_role(monkeypatch):
    """验证 分析器将简历文本和目标岗位传给 LLM"""
    from app.modules.resume import analyzer

    expected = {
        "basic_info": {
            "name": "张三",
            "education": "本科",
            "years_of_experience": 3,
            "skills": ["Python"],
        },
        "strengths": ["项目经验完整"],
        "weaknesses": ["缺少量化成果"],
        "suggestions": ["补充指标"],
        "overall_score": 80,
        "match_analysis": "匹配 Python 后端岗位",
    }
    calls = []

    def fake_call_llm(system_prompt, payload):
        calls.append((system_prompt, payload))
        return expected

    monkeypatch.setattr(analyzer, "call_llm", fake_call_llm)

    result = analyzer.analyze_resume("张三\nPython", "Python 后端")

    assert result == expected
    assert calls[0][1] == {"resume_text": "张三\nPython", "target_role": "Python 后端"}
    assert "JSON" in calls[0][0]


def test_analyze_resume_omits_empty_target_role(monkeypatch):
    """验证 未指定岗位时不传空 target_role 字段"""
    from app.modules.resume import analyzer

    payloads = []
    monkeypatch.setattr(
        analyzer,
        "call_llm",
        lambda system_prompt, payload: payloads.append(payload) or {"overall_score": 70},
    )

    result = analyzer.analyze_resume("张三\nPython")

    assert result == {"overall_score": 70}
    assert payloads == [{"resume_text": "张三\nPython"}]
