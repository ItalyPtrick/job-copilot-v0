# job_copilot_orchestrator.py
import json

import app.tools
from app.services.prompt_service import get_prompt
from app.services.llm_service import call_llm_with_tool_result, call_llm_with_tools
from app.tools.register import execute_tool, get_tools_for_llm
from app.types.task_result import TaskResult
from app.types.trace_event import TraceEvent, TraceNodeNames, TraceStatus

# 有效任务类型
VALID_TASK_TYPES: frozenset[str] = frozenset(
    ["jd_analyze", "resume_optimize", "self_intro_generate"]
)


# 记录任务执行轨迹
def trace(
    events: list[TraceEvent],
    node: TraceNodeNames,
    status: TraceStatus,
    remark: str = "",
) -> None:
    events.append(TraceEvent(node_name=node, status=status, remark=remark))


# 执行任务
def execute_task(task_type: str, payload: dict) -> TaskResult:
    trace_events: list[TraceEvent] = []
    current_node: TraceNodeNames | None = None

    try:
        # 1. 任务识别
        current_node = TraceNodeNames.TASK_RECOGNITION
        if task_type not in VALID_TASK_TYPES:
            trace(
                trace_events,
                TraceNodeNames.TASK_RECOGNITION,
                TraceStatus.ERROR,
                f"无效的任务类型: {task_type}",
            )
            return TaskResult.from_error(  # 直接返回错误结果
                task_type=task_type,
                error_type="InvalidTaskType",
                error_message=f"无效的任务类型: {task_type}",
                trace=trace_events,
            )
        trace(
            trace_events,
            TraceNodeNames.TASK_RECOGNITION,
            TraceStatus.SUCCESS,
            f"任务类型: {task_type}",
        )

        # 2. prompt 加载
        current_node = TraceNodeNames.PROMPT_LOAD
        system_prompt = get_prompt(task_type)
        trace(
            trace_events,
            TraceNodeNames.PROMPT_LOAD,
            TraceStatus.SUCCESS,
            f"加载 prompt: {task_type}.md 成功",
        )

        # 3. 调用 LLM
        current_node = TraceNodeNames.LLM_CALL
        tools = get_tools_for_llm()
        tool_choice = None
        if task_type == "jd_analyze":
            tool_choice = {
                "type": "function",
                "function": {"name": "analyze_jd_requirements"},
            }
        llm_result = call_llm_with_tools(
            system_prompt,
            payload,
            tools,
            tool_choice=tool_choice,
        )
        trace(
            trace_events,
            TraceNodeNames.LLM_CALL,
            TraceStatus.SUCCESS,
            f"LLM 调用成功，返回类型: {llm_result['type']}",
        )

        # 4. 结果汇总
        current_node = TraceNodeNames.RESULT_AGGREGATION
        if llm_result["type"] == "text":
            result = llm_result["content"]  # 直接使用文本结果，无需工具调用
            trace(
                trace_events,
                TraceNodeNames.RESULT_AGGREGATION,
                TraceStatus.SUCCESS,
                "进入普通文本分支，结果汇总成功",
            )
        elif (
            llm_result["type"] == "tool_calls"
        ):  # 需要执行工具并回填结果后再次调用 LLM 获取最终结果
            messages = [
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                llm_result["assistant_message"],
            ]
            # 依次执行工具调用，并将结果回填到消息列表中
            for tool_call in llm_result["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError as e:
                    raise ValueError(f"工具参数不是合法 JSON: {tool_name}") from e
                tool_result = execute_tool(tool_name, tool_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
                trace(
                    trace_events,
                    TraceNodeNames.RESULT_AGGREGATION,
                    TraceStatus.SUCCESS,
                    f"工具调用: {tool_name}, 入参: {tool_args}, 出参: {tool_result}",
                )
            result = call_llm_with_tool_result(messages)
            trace(
                trace_events,
                TraceNodeNames.RESULT_AGGREGATION,
                TraceStatus.SUCCESS,
                "进入工具调用分支，完成工具执行与结果回填",
            )
        else:
            raise ValueError(f"未知的 LLM 返回类型: {llm_result['type']}")

        return TaskResult.from_success(
            task_type=task_type, result=result, trace=trace_events
        )

    # 5. 异常处理
    except Exception as e:
        if current_node:
            trace(trace_events, current_node, TraceStatus.ERROR, f"错误: {str(e)}")
        return TaskResult.from_error(
            task_type=task_type,
            error_type=type(e).__name__,
            error_message=str(e),
            trace=trace_events,
        )
