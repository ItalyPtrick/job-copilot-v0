# job_copilot_orchestrator.py
from app.services.prompt_service import get_prompt
from app.services.llm_service import call_llm
from app.types.task_result import TaskResult, ErrorDetail


# 执行任务
def execute_task(task_type: str, payload: dict) -> TaskResult:
    try:
        valid_task_types = ["jd_analyze", "resume_optimize", "self_intro_generate"]

        # 任务类型校验
        if task_type not in valid_task_types:
            return TaskResult(
                status="error",
                task_type=task_type,
                error=ErrorDetail(
                    error_type="InvalidTaskType",
                    error_message=f"无效的任务类型: {task_type}",
                ),
            )

        # 调用 LLM 模型
        system_prompt = get_prompt(task_type)
        result = call_llm(system_prompt, payload)

        return TaskResult(
            status="success", task_type=task_type, result=result
        )  # 返回成功结果

    except Exception as e:
        return TaskResult(
            status="error",
            task_type=task_type,
            error=ErrorDetail(
                error_type=type(e).__name__, error_message=str(e)
            ),  # 返回错误结果
        )
