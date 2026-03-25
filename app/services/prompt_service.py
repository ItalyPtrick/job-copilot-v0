# prompt_service.py
import os


def get_prompt(task_type: str) -> str:
    # 根据任务类型动态加载对应的 Prompt 模板文件（面向ai）
    prompt_file = os.path.join(
        os.path.dirname(__file__), "..", "prompts", f"{task_type}.md"
    )
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt
