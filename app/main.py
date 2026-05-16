# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.orchestrators.job_copilot_orchestrator import execute_task
from app.types.task_result import TaskResult
from contextlib import asynccontextmanager
from app.database.connection import engine, Base, DATABASE_URL
from app.modules.knowledge_base.router import router as kb_router
from app.modules.interview.router import router as interview_router
from app.modules.schedule.router import router as schedule_router
from app.modules.resume.router import router as resume_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite 开发环境：启动时自动建表；
    # PostgreSQL 生产环境：交给 Alembic 管理，避免 create_all 与迁移冲突。
    if DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(kb_router)
app.include_router(interview_router)
app.include_router(schedule_router)
app.include_router(resume_router)


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
