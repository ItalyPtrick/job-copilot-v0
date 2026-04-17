# 语音面试模块（进阶）

本模块为模拟面试添加语音交互能力：用户用麦克风回答，系统用语音出题。基于 WebSocket 实现全双工通信，集成 ASR（语音识别）和 TTS（语音合成）。对标 interview-guide 的语音面试模块。

> 这是进阶模块，建议在文字面试模块完成后再实现。

---

## 1. 概念学习

### WebSocket vs HTTP

| 特性 | HTTP | WebSocket |
|---|---|---|
| 通信方向 | 请求-响应（客户端发起） | 全双工（双方随时发送） |
| 连接 | 每次请求新建连接 | 一次握手，持久连接 |
| 延迟 | 较高（每次建连开销） | 低（持久连接） |
| 适用场景 | REST API、文件上传 | 实时聊天、语音流 |

语音面试需要实时传输音频流，HTTP 轮询延迟太高，WebSocket 是唯一合理选择。

### ASR（自动语音识别）

将语音转为文字。常见方案：

| 方案 | 优缺点 | 延迟 |
|---|---|---|
| **OpenAI Whisper API** | 质量好，支持中英文，付费 | 1-3秒（非实时） |
| **Whisper 本地部署** | 免费，但需要 GPU | 取决于硬件 |
| **阿里云语音识别** | 支持实时流式，中文优 | 200ms（实时） |
| **Google Speech-to-Text** | 质量好，支持流式 | 低 |

**本项目选择：** OpenAI Whisper API（简单可靠，与现有 OpenAI SDK 统一）。初期不做实时流式，用"录完一段 → 发送 → 识别"的模式。

### TTS（文字转语音）

将 AI 生成的文字读出来。常见方案：

| 方案 | 优缺点 | 费用 |
|---|---|---|
| **OpenAI TTS** | 质量最好，多种音色 | 付费 |
| **edge-tts** | 微软 Edge 的 TTS，质量不错 | 免费 |
| **gTTS** | Google TTS，简单 | 免费但音质一般 |
| **pyttsx3** | 完全离线 | 免费但音质差 |

**本项目选择：** edge-tts（免费 + 质量不错），后续可切换到 OpenAI TTS。

### VAD（语音活动检测）

检测用户是否在说话，用于自动断句：

- **服务端 VAD**：服务器分析音频流，检测静音段 → 自动切割
- **客户端 VAD**：浏览器端检测，只在说话时才发送音频
- interview-guide 用服务端 VAD + 手动提交按钮

**本项目选择：** 初期用手动提交（按住说话/松开发送），后续加 VAD。

---

## 2. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| WebSocket 框架 | FastAPI WebSocket | 框架内置，无需额外依赖 |
| ASR | OpenAI Whisper API | 与现有 SDK 统一 |
| TTS | edge-tts | 免费、质量好、支持中文 |
| 音频格式 | WebM/Opus（浏览器录制）→ WAV | Whisper 支持多种格式 |
| 前端录音 | MediaRecorder API | 浏览器原生 |

**新增依赖：**
```
edge-tts>=6.1
websockets>=12.0  # FastAPI 已内置，但确保版本
```

---

## 3. 与现有代码的集成点

### 新增文件

```
app/
├── modules/
│   └── voice_interview/
│       ├── __init__.py
│       ├── ws_handler.py       # WebSocket 处理器
│       ├── asr_service.py      # 语音识别封装
│       ├── tts_service.py      # 语音合成封装
│       └── audio_utils.py      # 音频格式转换工具
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 注册 WebSocket 端点 `/ws/voice-interview` |
| `app/modules/interview/` | 复用面试逻辑（出题、追问、评估） |

### 关键复用

语音面试的面试逻辑与文字面试完全一致（出题、追问、评估引擎），区别仅在于 I/O 层：

```
文字面试：HTTP POST → 文本 → LLM → 文本 → HTTP Response
语音面试：WebSocket → 音频 → ASR → 文本 → LLM → 文本 → TTS → 音频 → WebSocket
```

---

## 4. 分步实现方案

### Step 1：TTS 服务

```python
# app/modules/voice_interview/tts_service.py
import edge_tts
import asyncio
import os

VOICE = "zh-CN-XiaoxiaoNeural"  # 中文女声
OUTPUT_DIR = "./data/tts_cache"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def text_to_speech(text: str, output_path: str = None) -> str:
    """文字转语音，返回音频文件路径"""
    if not output_path:
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        output_path = os.path.join(OUTPUT_DIR, f"{text_hash}.mp3")

    # 如果已有缓存，直接返回
    if os.path.exists(output_path):
        return output_path

    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)
    return output_path

async def text_to_speech_stream(text: str):
    """流式 TTS，逐句返回音频数据"""
    communicate = edge_tts.Communicate(text, VOICE)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
```

### Step 2：ASR 服务

```python
# app/modules/voice_interview/asr_service.py
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def speech_to_text(audio_path: str, language: str = "zh") -> str:
    """语音转文字"""
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
        )
    return transcript.text

def speech_to_text_from_bytes(audio_bytes: bytes, language: str = "zh") -> str:
    """从字节流转文字"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        return speech_to_text(temp_path, language)
    finally:
        os.unlink(temp_path)
```

### Step 3：WebSocket 处理器

```python
# app/modules/voice_interview/ws_handler.py
from fastapi import WebSocket, WebSocketDisconnect
import json

async def voice_interview_handler(websocket: WebSocket):
    """语音面试 WebSocket 处理器"""
    await websocket.accept()

    # 初始化面试 session
    from app.modules.interview.session_manager import create_session, get_session, update_session
    session_id = None

    try:
        while True:
            # 接收消息（JSON 控制指令或二进制音频）
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                action = data.get("action")

                if action == "start":
                    # 创建面试 session
                    config = data.get("config", {"skill": "python_backend", "total_questions": 5})
                    session_id = create_session(config)

                    # 生成第一题
                    from app.modules.interview.question_engine import generate_question
                    skill_path = f"app/skills/{config['skill']}.md"
                    with open(skill_path, "r", encoding="utf-8") as f:
                        skill_content = f.read()
                    question = generate_question(skill_content, "easy", [])

                    # TTS 播放题目
                    from app.modules.voice_interview.tts_service import text_to_speech_stream
                    await websocket.send_json({"type": "question", "text": question["question"]})
                    async for audio_chunk in text_to_speech_stream(question["question"]):
                        await websocket.send_bytes(audio_chunk)
                    await websocket.send_json({"type": "tts_done"})

                elif action == "end":
                    # 结束面试
                    await websocket.send_json({"type": "interview_ended", "session_id": session_id})
                    break

            elif "bytes" in message:
                # 收到音频数据 → ASR 识别
                audio_data = message["bytes"]
                from app.modules.voice_interview.asr_service import speech_to_text_from_bytes
                text = speech_to_text_from_bytes(audio_data)

                # 发送识别结果（实时字幕）
                await websocket.send_json({"type": "transcript", "text": text})

                # 处理回答（复用文字面试逻辑）
                # ... 生成下一题或追问 ...

    except WebSocketDisconnect:
        pass  # 客户端断开
```

### Step 4：注册 WebSocket 路由

```python
# 添加到 app/main.py
from fastapi import WebSocket
from app.modules.voice_interview.ws_handler import voice_interview_handler

@app.websocket("/ws/voice-interview")
async def voice_interview_ws(websocket: WebSocket):
    await voice_interview_handler(websocket)
```

---

## 5. 测试方案

```python
# tests/test_voice.py
import pytest

@pytest.mark.asyncio
async def test_tts():
    """测试 TTS 生成"""
    from app.modules.voice_interview.tts_service import text_to_speech
    output = await text_to_speech("你好，这是一道面试题")
    assert output.endswith(".mp3")
    import os
    assert os.path.exists(output)

def test_asr_mock():
    """测试 ASR（Mock）"""
    from unittest.mock import patch, MagicMock
    with patch("app.modules.voice_interview.asr_service.client") as mock_client:
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="测试识别结果")
        from app.modules.voice_interview.asr_service import speech_to_text
        # 需要一个实际的音频文件来测试
```

### 验证命令

```bash
pytest tests/test_voice.py -v

# WebSocket 手动测试（用 websocat 工具）
# pip install websocket-client
python -c "
import websocket, json
ws = websocket.create_connection('ws://localhost:8000/ws/voice-interview')
ws.send(json.dumps({'action': 'start', 'config': {'skill': 'python_backend'}}))
print(ws.recv())
ws.close()
"
```

---

## 6. 面试要点

### 常见问题

**Q: 语音面试为什么用 WebSocket 而不是 HTTP？**
> 语音面试需要实时双向通信——用户说话时实时传输音频流，AI 回复时实时播放语音。HTTP 是请求-响应模式，无法满足这种实时性需求。WebSocket 一次握手后保持长连接，双方可以随时发消息，延迟更低。

**Q: 你的 TTS 延迟怎么优化？**
> 两个策略：(1) 缓存——相同文本的 TTS 结果用 MD5 哈希做缓存 key，避免重复合成；(2) 流式传输——edge-tts 支持流式输出，音频边生成边发送，不用等全部合成完。interview-guide 用"句子级并发 TTS"进一步优化，每个句子独立合成并行播放。

**Q: 语音面试和文字面试的评估怎么统一？**
> 核心设计：语音只是 I/O 层的变化，面试逻辑（出题、追问、评估）完全复用。语音通过 ASR 转为文字后，进入和文字面试相同的处理流程。评估引擎对文字面试和语音面试使用同一套评分标准。

### 能讲出的亮点

- **WebSocket 全双工**：实时音频流传输
- **I/O 与逻辑分离**：语音面试复用文字面试的出题和评估引擎
- **TTS 缓存**：MD5 哈希避免重复合成
- **流式 TTS**：边合成边播放，降低首包延迟
