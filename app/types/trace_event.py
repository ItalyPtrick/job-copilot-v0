# trace_event.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# 跟踪事件模型
class TraceEvent(BaseModel):
    node_name: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    remark: Optional[str] = None


# 跟踪节点名称
class TraceNodeNames:
    TASK_RECOGNITION = "任务识别完成"
    PROMPT_LOAD = "prompt 加载完成"
    LLM_CALL = "调用 LLM"
    TOOL_CALL = "工具调用"
    TOOL_RESULT = "工具结果回填"
    RESULT_AGGREGATION = "结果汇总完成"


# 跟踪状态
class TraceStatus:
    START = "start"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
