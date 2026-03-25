# job_copilot_orchestrator.py
from app.services.prompt_service import get_prompt
from app.services.llm_service import call_llm
from app.types.task_result import TaskResult, ErrorDetail
from app.types.trace_event import TraceEvent, TraceNodeNames, TraceStatus


# 执行任务
def execute_task(task_type: str, payload: dict) -> TaskResult:
    trace_events = []
    current_node = None

    try:
        valid_task_types = ["jd_analyze", "resume_optimize", "self_intro_generate"]

        # 1. 任务识别
        current_node = TraceNodeNames.TASK_RECOGNITION
        if task_type not in valid_task_types:
            trace_events.append(
                TraceEvent(
                    node_name=TraceNodeNames.TASK_RECOGNITION,
                    status=TraceStatus.ERROR,
                    remark=f"无效的任务类型: {task_type}",
                )
            )
            return TaskResult(
                status="error",
                task_type=task_type,
                error=ErrorDetail(
                    error_type="InvalidTaskType",
                    error_message=f"无效的任务类型: {task_type}",
                ),
                trace=trace_events,
            )

        trace_events.append(
            TraceEvent(
                node_name=TraceNodeNames.TASK_RECOGNITION,
                status=TraceStatus.SUCCESS,
                remark=f"任务类型: {task_type}",
            )
        )

        # 2. prompt 加载
        current_node = TraceNodeNames.PROMPT_LOAD
        system_prompt = get_prompt(task_type)
        trace_events.append(
            TraceEvent(
                node_name=TraceNodeNames.PROMPT_LOAD,
                status=TraceStatus.SUCCESS,
                remark=f"加载 prompt: {task_type}.md 成功",
            )
        )

        # 3. 调用 LLM
        current_node = TraceNodeNames.LLM_CALL
        result = call_llm(system_prompt, payload)
        trace_events.append(
            TraceEvent(
                node_name=TraceNodeNames.LLM_CALL,
                status=TraceStatus.SUCCESS,
                remark="LLM 调用成功",
            )
        )

        # 4. 结果汇总
        current_node = TraceNodeNames.RESULT_AGGREGATION
        trace_events.append(
            TraceEvent(
                node_name=TraceNodeNames.RESULT_AGGREGATION, status=TraceStatus.SUCCESS
            )
        )

        return TaskResult(
            status="success", task_type=task_type, result=result, trace=trace_events
        )

    except Exception as e:
        if current_node:
            trace_events.append(
                TraceEvent(
                    node_name=current_node,
                    status=TraceStatus.ERROR,
                    remark=f"错误: {str(e)}",
                )
            )
        return TaskResult(
            status="error",
            task_type=task_type,
            error=ErrorDetail(error_type=type(e).__name__, error_message=str(e)),
            trace=trace_events,
        )
