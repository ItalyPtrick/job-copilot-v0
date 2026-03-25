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


# 调用 LLM 模型，返回模型生成的 JSON 字符串
def call_llm(system_prompt: str, user_input: dict) -> dict:
    user_content = json.dumps(
        user_input, ensure_ascii=False
    )  # 将用户输入的上下文转换为 JSON 字符串，使用 ASCII 编码

    # 调用 LLM 模型
    response = client.chat.completions.create(
        model="deepseek-v3",  # 模型名称
        messages=[  # 消息列表，包含系统提示和用户输入
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    # 从模型响应中提取文本内容
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
