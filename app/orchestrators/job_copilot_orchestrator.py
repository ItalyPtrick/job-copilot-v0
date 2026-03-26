# job_copilot_orchestrator.py
from app.services.prompt_service import get_prompt
from app.services.llm_service import call_llm
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
            return TaskResult.error(  # 直接返回错误结果
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
        result = call_llm(system_prompt, payload)
        trace(
            trace_events,
            TraceNodeNames.LLM_CALL,
            TraceStatus.SUCCESS,
            "LLM 调用成功",
        )

        # 4. 结果汇总
        current_node = TraceNodeNames.RESULT_AGGREGATION
        trace(
            trace_events,
            TraceNodeNames.RESULT_AGGREGATION,
            TraceStatus.SUCCESS,
            "结果汇总成功",
        )

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
