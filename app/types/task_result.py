# task_result.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .trace_event import TraceEvent


class ErrorDetail(BaseModel):
    error_type: str
    error_message: str


class TaskResult(BaseModel):
    status: str
    task_type: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorDetail] = None
    trace: Optional[list[TraceEvent]] = None
