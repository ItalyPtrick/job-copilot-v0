import sys
sys.path.insert(0, "C:/MyPython/job-copilot-v0")

import app.tools  # 触发 __init__.py，完成注册
from app.tools.register import execute_tool, get_tools_for_llm

# 测试1：正常调用
print("=== 测试1：正常调用 ===")
result = execute_tool("analyze_jd_requirements", {"jd_text": "我们需要一名熟悉 Python 和 FastAPI 的后端开发工程师，有 LLM 应用开发经验优先。"})
print(result)

# 测试2：工具不存在
print("\n=== 测试2：工具不存在 ===")
result = execute_tool("not_exist", {})
print(result)

# 测试3：缺少必填参数
print("\n=== 测试3：缺少必填参数 ===")
result = execute_tool("analyze_jd_requirements", {})
print(result)

# 测试4：get_tools_for_llm
print("\n=== 测试4：get_tools_for_llm ===")
tools = get_tools_for_llm()
print(f"工具数量：{len(tools)}")
print(f"格式检查：type={tools[0]['type']}, name={tools[0]['function']['name']}")
