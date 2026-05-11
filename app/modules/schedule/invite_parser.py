import re
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.llm_service import call_llm


class ParsedInvite(BaseModel):
    company: str | None = None        # 公司名
    position: str | None = None       # 职位名
    start_time: str | None = None     # 开始时间 (ISO 8601 格式)
    end_time: str | None = None       # 结束时间
    meeting_link: str | None = None   # 会议链接
    interviewer: str | None = None    # 面试官名字
    notes: str | None = None          # 备注（会议号、密码等）


_LINK_RE = re.compile(
    r"(?:https?://[^\s<>'\"（）()\[\]【】，,。；;、]*"
    r"(?:meeting\.tencent\.com|zoom\.us|feishu\.cn|teams\.microsoft\.com)"
    r"[^\s<>'\"（）()\[\]【】，,。；;、]*"
    r"|(?:meeting\.tencent\.com|zoom\.us|feishu\.cn|teams\.microsoft\.com)"
    r"[^\s<>'\"（）()\[\]【】，,。；;、]*)",
    re.IGNORECASE,
)

_TRAILING_LINK_CHARS = "。．.，,、；;：:!！?？）)]】>\"'"

_FULL_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})[-/.](?P<month>\d{1,2})[-/.](?P<day>\d{1,2})"
    r"\s*(?:[T ]\s*)?"
    r"(?P<start_hour>\d{1,2})(?::(?P<start_minute>\d{1,2}))?"
    r"\s*(?:[-~—–到至]\s*"
    r"(?P<end_hour>\d{1,2})(?::(?P<end_minute>\d{1,2}))?"
    r")?"
)

_SLASH_DATETIME_RE = re.compile(
    r"(?<!\d)(?P<month>\d{1,2})[/-](?P<day>\d{1,2})"
    r"\s+"
    r"(?P<start_hour>\d{1,2})(?::(?P<start_minute>\d{1,2}))?"
    r"\s*(?:[-~—–到至]\s*"
    r"(?P<end_hour>\d{1,2})(?::(?P<end_minute>\d{1,2}))?"
    r")?"
)

_CHINESE_DATETIME_RE = re.compile(
    r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*[日号]?\s*"
    r"(?P<start_period>上午|早上|下午|晚上|中午)?\s*"
    r"(?P<start_hour>\d{1,2})\s*(?:[:：点时]\s*(?P<start_minute>\d{1,2})?\s*(?:分)?)?"
    r"(?P<start_half>半)?"
    r"\s*(?:[-~—–到至]\s*"
    r"(?P<end_period>上午|早上|下午|晚上|中午)?\s*"
    r"(?P<end_hour>\d{1,2})\s*(?:[:：点时]\s*(?P<end_minute>\d{1,2})?\s*(?:分)?)?"
    r"(?P<end_half>半)?"
    r")?"
)

_MEETING_NUMBER_RE = re.compile(
    r"(?:腾讯会议|会议号|会议ID|Zoom)\s*[:：]?\s*(?P<number>\d[\d -]{5,}\d)",
    re.IGNORECASE,
)

_MEETING_PASSWORD_RE = re.compile(
    r"(?:会议密码|密码|passcode)\s*[:：]?\s*(?P<password>[A-Za-z0-9]{3,})",
    re.IGNORECASE,
)


def parse_invite_rule_based(text: str, base_date: date | None = None) -> ParsedInvite:
    """用本地规则提取高置信时间和会议链接。"""
    if not text or not text.strip():
        return ParsedInvite()

    anchor_date = base_date or date.today()
    start_time, end_time = _extract_time_range(text, anchor_date)
    meeting_link = _extract_meeting_link(text)
    notes = None if meeting_link else _extract_meeting_notes(text)

    return ParsedInvite(
        start_time=start_time,
        end_time=end_time,
        meeting_link=meeting_link,
        notes=notes,
    )


def parse_invite_ai(text: str) -> ParsedInvite:
    """调用 LLM 提取公司、岗位、面试官等软字段。"""
    if not text or not text.strip():
        return ParsedInvite()

    system_prompt = (
        "你是面试邀请解析器。请只输出 JSON，字段仅包含："
        "company、position、start_time、end_time、meeting_link、interviewer、notes。"
        "start_time 和 end_time 使用 ISO 8601 字符串；无法确定的字段返回 null。"
    )

    try:
        result = call_llm(system_prompt, {"invite_text": text})
    except Exception:
        return ParsedInvite()

    if not isinstance(result, dict) or result.get("error"):
        return ParsedInvite()

    allowed_values = {}
    for field in ParsedInvite.model_fields:
        raw_value = result.get(field)
        if field in {"start_time", "end_time"}:
            allowed_values[field] = _clean_optional_iso_datetime(raw_value)
        else:
            allowed_values[field] = _clean_optional_text(raw_value)

    try:
        return ParsedInvite(**allowed_values)
    except ValidationError:
        return ParsedInvite()


def parse_invite(text: str, base_date: date | None = None) -> ParsedInvite:
    """规则结果优先，AI 结果补充缺失字段。"""
    rule_result = parse_invite_rule_based(text, base_date=base_date)
    ai_result = parse_invite_ai(text)

    merged = {}
    for field in ParsedInvite.model_fields:
        rule_value = _clean_optional_text(getattr(rule_result, field))
        ai_value = _clean_optional_text(getattr(ai_result, field))
        merged[field] = rule_value or ai_value

    return ParsedInvite(**merged)


def _extract_meeting_link(text: str) -> str | None:
    match = _LINK_RE.search(text)
    if not match:
        return None

    link = match.group(0).strip().rstrip(_TRAILING_LINK_CHARS)
    if not link:
        return None
    if not link.startswith(("http://", "https://")):
        link = f"https://{link}"
    return link


def _extract_meeting_notes(text: str) -> str | None:
    parts: list[str] = []

    number_match = _MEETING_NUMBER_RE.search(text)
    if number_match:
        parts.append(f"会议号：{number_match.group('number').strip()}")

    password_match = _MEETING_PASSWORD_RE.search(text)
    if password_match:
        parts.append(f"密码：{password_match.group('password').strip()}")

    return "；".join(parts) if parts else None


def _extract_time_range(text: str, base_date: date) -> tuple[str | None, str | None]:
    for parser in (_parse_full_datetime, _parse_slash_datetime, _parse_chinese_datetime):
        parsed = parser(text, base_date)
        if parsed != (None, None):
            return parsed
    return None, None


def _parse_full_datetime(text: str, base_date: date) -> tuple[str | None, str | None]:
    match = _FULL_DATETIME_RE.search(text)
    if not match:
        return None, None

    start, end = _build_numeric_range(match, int(match.group("year")))
    return _format_range(start, end)


def _parse_slash_datetime(text: str, base_date: date) -> tuple[str | None, str | None]:
    match = _SLASH_DATETIME_RE.search(text)
    if not match:
        return None, None

    month = int(match.group("month"))
    day = int(match.group("day"))
    year = _resolve_year_for_no_year_date(month, day, base_date)
    start, end = _build_numeric_range(match, year)
    return _format_range(start, end)


def _parse_chinese_datetime(text: str, base_date: date) -> tuple[str | None, str | None]:
    match = _CHINESE_DATETIME_RE.search(text)
    if not match:
        return None, None

    try:
        month = int(match.group("month"))
        day = int(match.group("day"))
        year = _resolve_year_for_no_year_date(month, day, base_date)
        start_period = match.group("start_period")
        start_hour = _normalize_hour(int(match.group("start_hour")), start_period)
        start_minute = _parse_minute(match.group("start_minute"), match.group("start_half"))
        start = datetime(year, month, day, start_hour, start_minute)

        if not match.group("end_hour"):
            return start.isoformat(), None

        raw_end_hour = int(match.group("end_hour"))
        end_period = _resolve_end_period(
            start_period,
            match.group("end_period"),
            raw_end_hour,
        )
        end_hour = _normalize_hour(raw_end_hour, end_period)
        end_minute = _parse_minute(match.group("end_minute"), match.group("end_half"))
        end = datetime(year, month, day, end_hour, end_minute)
        if end <= start:
            end += timedelta(days=1)
        return start.isoformat(), end.isoformat()
    except ValueError:
        return None, None


def _build_numeric_range(match: re.Match[str], year: int) -> tuple[datetime | None, datetime | None]:
    try:
        month = int(match.group("month"))
        day = int(match.group("day"))
        start = datetime(
            year,
            month,
            day,
            int(match.group("start_hour")),
            _parse_numeric_minute(match.group("start_minute")),
        )

        if not match.group("end_hour"):
            return start, None

        end = datetime(
            year,
            month,
            day,
            int(match.group("end_hour")),
            _parse_numeric_minute(match.group("end_minute")),
        )
        if end <= start:
            end += timedelta(days=1)
        return start, end
    except ValueError:
        return None, None


def _format_range(start: datetime | None, end: datetime | None) -> tuple[str | None, str | None]:
    if start is None:
        return None, None
    return start.isoformat(), end.isoformat() if end else None


# 无年份日期默认取 base_date 所在年；若该日期已过，则按下一年处理。
def _resolve_year_for_no_year_date(month: int, day: int, base_date: date) -> int:
    year = base_date.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return year
    if candidate < base_date:
        return year + 1
    return year


def _resolve_end_period(
    start_period: str | None,
    end_period: str | None,
    end_hour: int,
) -> str | None:
    if end_period is not None:
        return end_period
    # 结束时间未显式写上午/下午时通常继承开始时段；但"上午10点-12点"的 12 应表示正午，不能按上午 12 点归零。
    if start_period in {"上午", "早上"} and end_hour == 12:
        return None
    return start_period


def _normalize_hour(hour: int, period: str | None) -> int:
    if period in {"下午", "晚上"} and 1 <= hour < 12:
        return hour + 12
    if period == "中午" and 1 <= hour < 11:
        return hour + 12
    if period in {"上午", "早上"} and hour == 12:
        return 0
    return hour


def _parse_minute(raw_minute: str | None, half: str | None) -> int:
    if half:
        return 30
    return _parse_numeric_minute(raw_minute)


def _parse_numeric_minute(raw_minute: str | None) -> int:
    if raw_minute in (None, ""):
        return 0
    return int(raw_minute)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_optional_iso_datetime(value: Any) -> str | None:
    cleaned = _clean_optional_text(value)
    if cleaned is None:
        return None
    try:
        datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return cleaned
