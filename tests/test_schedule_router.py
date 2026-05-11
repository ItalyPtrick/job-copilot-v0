"""schedule 路由测试：POST /schedule/parse-invite。"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.modules.schedule.invite_parser import ParsedInvite

client = TestClient(app)


class TestParseInviteEndpoint:
    """POST /schedule/parse-invite 端点测试。"""

    def test_empty_text_returns_400(self):
        resp = client.post("/schedule/parse-invite", json={"text": "   "})
        assert resp.status_code == 400

    def test_missing_text_field_returns_422(self):
        resp = client.post("/schedule/parse-invite", json={})
        assert resp.status_code == 422

    @patch("app.modules.schedule.router.parse_invite")
    def test_successful_parse(self, mock_parse):
        mock_parse.return_value = ParsedInvite(
            company="字节跳动",
            position="后端开发",
            start_time="2026-05-10T14:00:00",
            end_time="2026-05-10T16:00:00",
            meeting_link="https://meeting.tencent.com/dm/abc123",
        )
        resp = client.post(
            "/schedule/parse-invite",
            json={"text": "字节跳动后端面试 2026-05-10 14:00-16:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["company"] == "字节跳动"
        assert data["start_time"] == "2026-05-10T14:00:00"
        assert data["meeting_link"] == "https://meeting.tencent.com/dm/abc123"

    @patch("app.modules.schedule.router.parse_invite")
    def test_parse_exception_returns_503(self, mock_parse):
        mock_parse.side_effect = RuntimeError("LLM 不可用")
        resp = client.post(
            "/schedule/parse-invite",
            json={"text": "面试邀请内容"},
        )
        assert resp.status_code == 503
