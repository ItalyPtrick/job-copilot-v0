import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
MODEL_NAME = os.getenv("OPENAI_MODEL")


# 调用 LLM 模型，返回模型生成的 JSON 字符串
def call_llm(system_prompt: str, user_input: dict) -> dict:
    user_content = json.dumps(
        user_input, ensure_ascii=False
    )  # 将用户输入的上下文转换为 JSON 字符串，使用 ASCII 编码

    # 调用 LLM 模型
    response = client.chat.completions.create(
        model=MODEL_NAME,  # 使用环境变量中指定的模型
        messages=[  # 消息列表，包含系统提示和用户输入
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    # 从模型响应中提取文本内容(假设只返回文本)
    raw_text = response.choices[0].message.content

    # 容错：清理可能的 markdown 代码块包裹
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "模型返回格式异常，请重试", "raw": cleaned}


# 调用 LLM 模型，支持工具调用，返回工具调用结果或文本结果
def call_llm_with_tools(
    system_prompt: str,
    user_input: dict,
    tools: list[dict],
    messages_history: list[dict] | None = None,
    tool_choice: dict | str | None = None,
) -> dict:
    # 将当前用户输入转换为 JSON 字符串
    user_content = json.dumps(user_input, ensure_ascii=False)

    # 组装消息列表：system + 历史消息 + 当前 user
    messages = [{"role": "system", "content": system_prompt}]
    if messages_history:
        messages.extend(messages_history)
    messages.append({"role": "user", "content": user_content})

    # 调用 LLM 模型，并把可用工具一并传给模型
    request_params = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": tools,
    }
    if tool_choice is not None:
        request_params["tool_choice"] = (
            tool_choice  # 如果指定了工具选择，则传递给模型，告诉模型只能调用哪个工具
        )

    response = client.chat.completions.create(**request_params)

    # 读取模型返回的消息对象
    message = response.choices[0].message
    # 如果模型决定调用工具，则返回可序列化的工具调用信息
    if message.tool_calls:
        serialized_tool_calls = []
        for tool_call in message.tool_calls:
            serialized_tool_calls.append(
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )
        return {
            "type": "tool_calls",
            "tool_calls": serialized_tool_calls,
            "assistant_message": {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": serialized_tool_calls,
            },
        }

    # 如果没有工具调用，则直接返回文本内容
    return {"type": "text", "content": message.content}


# 第二轮调用 LLM：传入完整消息列表，直接获取最终文本结果
def call_llm_with_tool_result(messages: list[dict]) -> str:
    # 使用已有 messages 直接调用模型
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
    )

    raw_text = response.choices[0].message.content or ""
    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]

    # 返回模型生成的最终文本
    return cleaned.strip()
