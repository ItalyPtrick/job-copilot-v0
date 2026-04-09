# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.orchestrators.job_copilot_orchestrator import execute_task
from app.types.task_result import TaskResult

app = FastAPI()


class TaskRequest(BaseModel):
    task_type: str
    payload: dict


@app.get("/")
def index():
    return "The server is running"


@app.post("/task")
def handle_task(request: TaskRequest) -> JSONResponse:
    result = execute_task(request.task_type, request.payload)

    status_code = 200
    if result.status == "error":
        status_code = 400

    return JSONResponse(content=result.model_dump(mode="json"), status_code=status_code)
