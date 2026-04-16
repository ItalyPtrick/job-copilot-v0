"""
验证三种工具调用失败场景：
1. 调用不存在的工具名
2. tool_call.arguments 不是合法 JSON
3. 工具函数内部抛出 ValueError("测试")

验收标准：execute_task 不崩溃、trace 有 ERROR、status 为 success、result 为降级回答
"""
import sys

sys.path.insert(0, "C:/MyPython/job-copilot-v0")

from unittest.mock import patch, MagicMock

# mock 外部依赖，避免 import openai / dotenv 报错
sys.modules.setdefault("openai", MagicMock())
sys.modules.setdefault("dotenv", MagicMock())

from app.orchestrators.job_copilot_orchestrator import execute_task
from app.tools.register import TOOL_REGISTRY
from app.types.trace_event import TraceStatus

# 手动注册一个 dummy 工具，用于 Case 3（避免 import app.tools 触发 openai 导入链）
TOOL_REGISTRY["analyze_jd_requirements"] = {
    "schema": {
        "name": "analyze_jd_requirements",
        "description": "dummy",
        "parameters": {"type": "object", "properties": {}},
    },
    "fn": lambda args: {"status": "success", "result": {}},
}

PAYLOAD = {"jd_text": "需要 Python 后端开发工程师"}
DEGRADED_ANSWER = "由于工具调用失败，以下是基于已有信息的降级回答。"


def make_tool_calls_response(tool_name: str, arguments_str: str) -> dict:
    """构造 call_llm_with_tools 的 mock 返回值"""
    tool_call = {
        "id": "call_test_001",
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments_str},
    }
    return {
        "type": "tool_calls",
        "tool_calls": [tool_call],
        "assistant_message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [tool_call],
        },
    }


def assert_common(case_name: str, task_result) -> None:
    """统一断言 + 打印 trace 明细"""
    assert task_result.status == "success", (
        f"[{case_name}] status 应为 success，实际: {task_result.status}"
    )
    assert task_result.result == DEGRADED_ANSWER, (
        f"[{case_name}] result 应为降级回答，实际: {task_result.result}"
    )
    error_events = [e for e in task_result.trace if e.status == TraceStatus.ERROR]
    assert len(error_events) > 0, f"[{case_name}] trace 中应有 ERROR 节点"
    print(f"  PASSED [{case_name}]")
    for e in task_result.trace:
        print(f"    {e.node_name} | {e.status} | {e.remark}")


# ── Case 1：调用不存在的工具名 ──────────────────────────────────
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tool_result",
    return_value=DEGRADED_ANSWER,
)
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tools",
    return_value=make_tool_calls_response("nonexistent_tool", '{"jd_text":"test"}'),
)
def test_case1_tool_not_found(mock_llm_tools, mock_llm_result):
    print("\n=== Case 1：调用不存在的工具名 ===")
    result = execute_task("jd_analyze", PAYLOAD)
    assert_common("Case1-工具不存在", result)


# ── Case 2：arguments 不是合法 JSON ─────────────────────────────
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tool_result",
    return_value=DEGRADED_ANSWER,
)
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tools",
    return_value=make_tool_calls_response(
        "analyze_jd_requirements", "not valid json{{"
    ),
)
def test_case2_invalid_json(mock_llm_tools, mock_llm_result):
    print("\n=== Case 2：arguments 不是合法 JSON ===")
    result = execute_task("jd_analyze", PAYLOAD)
    assert_common("Case2-参数解析失败", result)


# ── Case 3：工具函数内部抛出 ValueError ─────────────────────────
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tool_result",
    return_value=DEGRADED_ANSWER,
)
@patch(
    "app.orchestrators.job_copilot_orchestrator.call_llm_with_tools",
    return_value=make_tool_calls_response(
        "analyze_jd_requirements", '{"jd_text":"test"}'
    ),
)
def test_case3_tool_raises(mock_llm_tools, mock_llm_result):
    print("\n=== Case 3：工具函数内部抛出 ValueError ===")

    def raising_tool(args):
        raise ValueError("测试")

    original_fn = TOOL_REGISTRY["analyze_jd_requirements"]["fn"]
    TOOL_REGISTRY["analyze_jd_requirements"]["fn"] = raising_tool
    try:
        result = execute_task("jd_analyze", PAYLOAD)
        assert_common("Case3-工具内部异常", result)
    finally:
        TOOL_REGISTRY["analyze_jd_requirements"]["fn"] = original_fn


if __name__ == "__main__":
    test_case1_tool_not_found()
    test_case2_invalid_json()
    test_case3_tool_raises()
    print("\n=== 全部三种失败场景验证通过 ===")
