# minimal_app.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.orchestrators.job_copilot_orchestrator import execute_task
import json
import streamlit as st

# 标题
st.title("任务执行Demo")

# 任务类型
value = st.selectbox(
    "请选择任务类型", ["jd_analyze", "resume_optimize", "self_intro_generate"]
)

# 文本框
text = st.text_area("请输入内容：")
st.caption('示例：{\'"jd_text": "我们需要一名Python工程师"}\'')

# 提交按钮
if st.button("提交"):
    try:
        payload = json.loads(text)
        # 调用execute_task
        result = execute_task(value, payload)
        st.write("任务执行结果")
        st.json(result.model_dump(mode="json"))  # 打印任务执行结果的 JSON 格式
    except json.JSONDecodeError:
        st.error("请输入有效的 JSON 格式")
