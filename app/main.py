# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.orchestrators.job_copilot_orchestrator import execute_task
from app.types.task_result import TaskResult
from contextlib import asynccontextmanager
from app.database.connection import engine, Base
from app.modules.knowledge_base.router import router as kb_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表（开发环境用，生产环境用 Alembic）
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(kb_router)


class TaskRequest(BaseModel):
    task_type: str
    payload: dict


@app.get("/")
def index():
    return "The server is running"


@app.post("/task")
def handle_task(request: TaskRequest) -> JSONResponse:
    result = execute_task(request.task_type, request.payload)

    # 这里沿用统一 TaskResult JSON 形状，把业务失败映射成 400，而不是抛出 FastAPI 异常页。
    status_code = 200
    if result.status == "error":
        status_code = 400

    return JSONResponse(content=result.model_dump(mode="json"), status_code=status_code)
