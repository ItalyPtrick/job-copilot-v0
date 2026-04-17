# job_copilot_orchestrator.py
import json

import app.tools
from app.services.prompt_service import get_prompt
from app.services.llm_service import call_llm_with_tool_result, call_llm_with_tools
from app.tools.register import execute_tool, get_tools_for_llm
from app.types.task_result import TaskResult
from app.types.trace_event import TraceEvent, TraceNodeNames, TraceStatus
from app.database.connection import SessionLocal
from app.database.models.task_record import TaskRecord


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
            result = TaskResult.from_error(  # 直接返回错误结果
                task_type=task_type,
                error_type="InvalidTaskType",
                error_message=f"无效的任务类型: {task_type}",
                trace=trace_events,
            )
            _save_task_record(result, payload)
            return result
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                llm_result["assistant_message"],
            ]
            # 依次执行工具调用，并将结果回填到消息列表中
            for tool_call in llm_result["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                raw_arguments = tool_call["function"][
                    "arguments"
                ]  # 提取工具调用的原始参数（JSON字符串）
                trace(
                    trace_events,
                    TraceNodeNames.TOOL_CALL,
                    TraceStatus.START,
                    f"准备调用工具: {tool_name}, 原始参数: {raw_arguments}",
                )
                try:
                    tool_args = json.loads(raw_arguments)
                except (json.JSONDecodeError, TypeError) as e:
                    tool_result = {
                        "status": "error",
                        "error": f"工具参数不是合法 JSON: {e}",
                    }
                    trace(
                        trace_events,
                        TraceNodeNames.TOOL_CALL,
                        TraceStatus.ERROR,
                        (
                            f"工具调用失败: {tool_name}, 原始参数: {raw_arguments}, "
                            f"参数解析异常: {e}"
                        ),
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False),
                        }
                    )
                    continue  # 跳过当前工具调用，继续下一个
                tool_result = execute_tool(tool_name, tool_args)  # 执行工具调用
                # 记录工具调用结果
                if tool_result.get("status") == "error":
                    trace(
                        trace_events,
                        TraceNodeNames.TOOL_CALL,
                        TraceStatus.ERROR,
                        f"工具调用失败: {tool_name}, 入参: {tool_args}, 出参: {tool_result}",
                    )
                else:
                    trace(
                        trace_events,
                        TraceNodeNames.TOOL_RESULT,
                        TraceStatus.SUCCESS,
                        f"工具调用成功: {tool_name}, 入参: {tool_args}, 出参: {tool_result}",
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
            result = call_llm_with_tool_result(messages)  # 调用 LLM 获取最终结果
            trace(
                trace_events,
                TraceNodeNames.RESULT_AGGREGATION,
                TraceStatus.SUCCESS,
                "进入工具调用分支，完成工具执行与结果回填",
            )
        else:
            raise ValueError(f"未知的 LLM 返回类型: {llm_result['type']}")

        # 返回任务执行结果
        result = TaskResult.from_success(
            task_type=task_type, result=result, trace=trace_events
        )
        _save_task_record(result, payload)  # 保存任务记录到数据库
        return result

    # 5. 异常处理
    except Exception as e:
        if current_node:
            trace(trace_events, current_node, TraceStatus.ERROR, f"错误: {str(e)}")
        result = TaskResult.from_error(
            task_type=task_type,
            error_type=type(e).__name__,
            error_message=str(e),
            trace=trace_events,
        )
        _save_task_record(result, payload)
        return result


# 将任务执行结果保存到数据库
def _save_task_record(result: TaskResult, payload: dict) -> None:
    db = SessionLocal()
    try:
        record = TaskRecord(
            task_type=result.task_type,
            payload=payload,
            status=result.status,
            result=result.result if result.status == "success" else None,
            error_type=result.error.error_type if result.error else None,
            error_message=result.error.error_message if result.error else None,
            trace=[t.model_dump(mode="json") for t in (result.trace or [])],
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
