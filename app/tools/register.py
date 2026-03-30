# app/tools/registry.py
from typing import Callable

TOOL_REGISTRY: dict = {}


# 注册工具
def register_tool(schema: dict, fn: Callable[[dict], dict]) -> None:
    name = schema["function"]["name"]
    TOOL_REGISTRY[name] = {"schema": schema["function"], "fn": fn}


# 获取工具列表
def get_tools_for_llm() -> list[dict]:
    result = []
    for name, entry in TOOL_REGISTRY.items():
        result.append({"type": "function", "function": entry["schema"]})
    return result


# 执行工具
def execute_tool(name: str, arguments: dict) -> dict:
    if name not in TOOL_REGISTRY:
        return {"status": "error", "error": f"工具 {name} 未注册"}
    try:
        return TOOL_REGISTRY[name]["fn"](arguments)
    except Exception as e:
        return {"status": "error", "error": str(e)}
