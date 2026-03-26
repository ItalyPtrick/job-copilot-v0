from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RetrieverChunk(BaseModel):
    chunk_id: str
    source_title: str
    source_url: str = ""
    content: str
    range: str = ""


class RetrieverContext(BaseModel):
    context_id: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    chunks: list[RetrieverChunk] = Field(
        default_factory=list
    )  # 用工厂函数初始化空列表，避免默认值被共享的问题，且即使检索不到东西，也能不是 None
