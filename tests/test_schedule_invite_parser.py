from datetime import date

from app.modules.schedule.invite_parser import (
    ParsedInvite,
    parse_invite,
    parse_invite_ai,
    parse_invite_rule_based,
)


def test_rule_based_parses_chinese_afternoon_range_and_trims_meeting_link():
    text = "面试时间：5月10日下午2点-4点，腾讯会议：https://meeting.tencent.com/dm/abc。"

    result = parse_invite_rule_based(text, base_date=date(2026, 1, 1))

    assert result.start_time == "2026-05-10T14:00:00"
    assert result.end_time == "2026-05-10T16:00:00"
    assert result.meeting_link == "https://meeting.tencent.com/dm/abc"


def test_rule_based_keeps_inherited_morning_noon_as_same_day_noon():
    text = "面试时间：5月10日上午10点-12点"

    result = parse_invite_rule_based(text, base_date=date(2026, 1, 1))

    assert result.start_time == "2026-05-10T10:00:00"
    assert result.end_time == "2026-05-10T12:00:00"


def test_rule_based_rolls_slash_date_without_year_to_next_year_when_past_base_date():
    text = "面试时间：1/5 10:00-11:00"

    result = parse_invite_rule_based(text, base_date=date(2026, 12, 20))

    assert result.start_time == "2027-01-05T10:00:00"
    assert result.end_time == "2027-01-05T11:00:00"


def test_rule_based_rolls_chinese_date_without_year_to_next_year_when_past_base_date():
    text = "面试时间：1月5日上午10点-11点"

    result = parse_invite_rule_based(text, base_date=date(2026, 12, 20))

    assert result.start_time == "2027-01-05T10:00:00"
    assert result.end_time == "2027-01-05T11:00:00"


def test_rule_based_parses_iso_datetime_range_and_trims_closing_parenthesis():
    text = "面试：2026-05-10 14:00-16:00 (Zoom: https://zoom.us/j/123456789?pwd=abc)"

    result = parse_invite_rule_based(text)

    assert result.start_time == "2026-05-10T14:00:00"
    assert result.end_time == "2026-05-10T16:00:00"
    assert result.meeting_link == "https://zoom.us/j/123456789?pwd=abc"


def test_rule_based_parses_feishu_link_before_following_chinese_text():
    text = "飞书会议：https://vc.feishu.cn/j/123，请准时参加。"

    result = parse_invite_rule_based(text)

    assert result.meeting_link == "https://vc.feishu.cn/j/123"


def test_rule_based_keeps_meeting_number_and_password_in_notes_without_url():
    text = "腾讯会议：123-456-789，密码：8888，请提前 5 分钟进入。"

    result = parse_invite_rule_based(text, base_date=date(2026, 1, 1))

    assert result.meeting_link is None
    assert result.notes is not None
    assert "123-456-789" in result.notes
    assert "8888" in result.notes


def test_parse_invite_ai_builds_schema_from_call_llm_dict(monkeypatch):
    from app.modules.schedule import invite_parser

    def fake_call_llm(system_prompt, user_input):
        assert "JSON" in system_prompt
        assert user_input == {"invite_text": "邀请文本"}
        return {
            "company": "示例科技",
            "position": "Python 后端工程师",
            "interviewer": "张三",
            "unexpected": "ignored",
        }

    monkeypatch.setattr(invite_parser, "call_llm", fake_call_llm)

    result = parse_invite_ai("邀请文本")

    assert result == ParsedInvite(
        company="示例科技",
        position="Python 后端工程师",
        interviewer="张三",
    )


def test_parse_invite_ai_returns_empty_invite_when_call_llm_returns_error(monkeypatch):
    from app.modules.schedule import invite_parser

    monkeypatch.setattr(
        invite_parser,
        "call_llm",
        lambda system_prompt, user_input: {"error": "模型返回格式异常", "raw": "not json"},
    )

    result = parse_invite_ai("邀请文本")

    assert result == ParsedInvite()


def test_parse_invite_ai_drops_non_iso_time_fields(monkeypatch):
    from app.modules.schedule import invite_parser

    monkeypatch.setattr(
        invite_parser,
        "call_llm",
        lambda system_prompt, user_input: {
            "company": "示例科技",
            "start_time": "明天下午三点",
            "end_time": "later",
        },
    )

    result = parse_invite_ai("邀请文本")

    assert result.company == "示例科技"
    assert result.start_time is None
    assert result.end_time is None


def test_parse_invite_keeps_rule_time_and_link_when_ai_conflicts(monkeypatch):
    from app.modules.schedule import invite_parser

    monkeypatch.setattr(
        invite_parser,
        "parse_invite_ai",
        lambda text: ParsedInvite(
            company="示例科技",
            position="Python 后端工程师",
            start_time="2099-01-01T09:00:00",
            end_time="2099-01-01T10:00:00",
            meeting_link="https://zoom.us/j/wrong",
            interviewer="李四",
            notes="携带简历",
        ),
    )

    text = "示例科技 Python 后端面试，时间 2026-05-10 14:00-16:00，链接 https://meeting.tencent.com/dm/right。"

    result = parse_invite(text, base_date=date(2026, 1, 1))

    assert result.company == "示例科技"
    assert result.position == "Python 后端工程师"
    assert result.start_time == "2026-05-10T14:00:00"
    assert result.end_time == "2026-05-10T16:00:00"
    assert result.meeting_link == "https://meeting.tencent.com/dm/right"
    assert result.interviewer == "李四"
    assert result.notes == "携带简历"
