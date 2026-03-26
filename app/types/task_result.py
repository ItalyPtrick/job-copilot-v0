# task_result.py
from typing import Any, Literal, Optional
from pydantic import BaseModel
from .trace_event import TraceEvent
from .retriever_context import RetrieverContext


# 错误详情
class ErrorDetail(BaseModel):
    error_type: str
    error_message: str


# 任务执行结果
class TaskResult(BaseModel):
    status: Literal["success", "error"]
    task_type: str
    result: dict[str, Any] | None = None
    error: ErrorDetail | None = None
    trace: list[TraceEvent] | None = None
    retriever_context: Optional[RetrieverContext] = None

    # 任务执行结果工厂类
    @classmethod
    def success(
        cls, task_type: str, result: dict, trace: list[TraceEvent]
    ) -> "TaskResult":
        return cls(status="success", task_type=task_type, result=result, trace=trace)

    # 错误任务执行结果工厂类
    @classmethod
    def error(
        cls,
        task_type: str,
        error_type: str,
        error_message: str,
        trace: list[TraceEvent],
    ) -> "TaskResult":
        return cls(
            status="error",
            task_type=task_type,
            error=ErrorDetail(error_type=error_type, error_message=error_message),
            trace=trace,
        )
