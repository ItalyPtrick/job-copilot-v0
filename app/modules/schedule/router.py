"""日程路由：/schedule/parse-invite。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.schedule.invite_parser import ParsedInvite, parse_invite

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedule", tags=["schedule"])


class ParseInviteRequest(BaseModel):
    text: str


@router.post("/parse-invite", response_model=ParsedInvite)
def parse_invite_endpoint(request: ParseInviteRequest):
    """解析面试邀请文本，返回结构化字段。"""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="邀请文本不能为空。")

    try:
        result = parse_invite(request.text)
    except Exception as exc:
        logger.warning("面试邀请解析失败: %s", exc)
        raise HTTPException(status_code=503, detail="解析服务暂时不可用。") from exc

    return result
