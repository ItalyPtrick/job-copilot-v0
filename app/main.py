from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TaskRequest(BaseModel):
    task_type: str


@app.get("/")
def index():
    return "The server is running"


@app.post("/task")
def handle_task(request: TaskRequest):
    valid_task_types = ["jd_analyze", "resume_optimize", "self_intro_generate"]
    if request.task_type in valid_task_types:
        return {"status": "success", "task_type": request.task_type}
    else:
        raise HTTPException(
            status_code=400, detail=f"Invalid task_type: {request.task_type}"
        )
