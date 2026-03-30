# app/tools/registry.py
from typing import Callable

TOOL_REGISTRY: dict = {}


def register_tool(schema: dict, fn: Callable[[dict], dict]) -> None:
    name = schema["function"]["name"]
    TOOL_REGISTRY[name] = {"schema": schema["function"], "fn": fn}


def get_tools_for_llm() -> list[dict]:
    result = []
    for name, entry in TOOL_REGISTRY.items():
        result.append({"type": "function", "function": entry["schema"]})
    return result


def execute_tool(name: str, arguments: dict) -> dict:
    if name not in TOOL_REGISTRY:
        return {"status": "error", "error": f"工具 {name} 未注册"}
    try:
        return TOOL_REGISTRY[name]["fn"](arguments)
    except Exception as e:
        return {"status": "error", "error": str(e)}
