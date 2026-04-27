# 模拟面试模块（含面试安排）

本模块实现 AI 驱动的模拟面试系统：基于 Skill 定义结构化出题、多轮追问、评估引擎生成面试报告，以及面试安排管理（邀请解析 + 日历视图）。对标 interview-guide 的模拟面试 + 面试安排两个模块。

---

## 1. 概念学习

### 多轮对话管理

模拟面试的核心是多轮对话——面试官出题、候选人回答、面试官追问。需要解决：

- **上下文管理**：每轮对话都要带上之前的历史，LLM 才能做连贯追问
- **上下文长度控制**：历史过长会超出 token 限制或增加成本
- **会话状态**：面试进行中 / 暂停 / 结束 / 评估中

**常见策略：**

| 策略 | 描述 | 适用场景 |
|---|---|---|
| 全量历史 | 每次把所有对话都发给 LLM | 短对话（<10轮） |
| 滑动窗口 | 只保留最近 N 轮对话 | 长对话，防止超 token |
| 摘要压缩 | 定期用 LLM 压缩历史为摘要 | 超长对话 |
| 混合策略 | 最近 N 轮全量 + 更早的摘要 | 本项目推荐 |

**本项目选择：** 全量历史（面试通常 10-20 轮，在 token 限制内），配合 Redis 缓存。

### 结构化输出（Structured Output）

让 LLM 返回固定格式的 JSON，而非自由文本。对面试评估尤为重要——需要结构化的评分和评语。

```python
# OpenAI Structured Output 示例
from pydantic import BaseModel

class InterviewQuestion(BaseModel):
    question: str           # 面试题目
    category: str           # 考察方向（如"Python基础"、"系统设计"）
    difficulty: str         # 难度（easy/medium/hard）
    follow_up_hint: str     # 追问方向提示

# 使用 response_format 强制 JSON 输出
response = client.beta.chat.completions.parse(
    model="deepseek-chat",
    messages=[...],
    response_format=InterviewQuestion,
)
question = response.choices[0].message.parsed  # 直接得到 Pydantic 对象
```

### Skill 驱动出题

interview-guide 内置 10+ 面试方向，每个方向用 `SKILL.md` 定义考察范围。我们用同样的思路：

```markdown
# skill: python_backend.md

## 考察范围
- Python 基础：数据结构、装饰器、生成器、GIL
- Web 框架：FastAPI / Flask 路由、中间件、依赖注入
- 数据库：SQLAlchemy ORM、事务、连接池
- 异步编程：asyncio、协程、并发模式
- 系统设计：缓存策略、消息队列、微服务拆分

## 难度分布
- 基础题：40%
- 进阶题：40%
- 开放题：20%

## 参考知识库
- collection: python_docs
```

### 评估引擎

interview-guide 用"分批评估 + 结构化输出 + 二次汇总 + 降级兜底"架构。核心思路：

```
面试结束
  ↓
Step 1: 按题目分批评估（每 3-5 题一批，生成单题评分）
  ↓
Step 2: 汇总所有单题评分，生成总评报告
  ↓
Step 3: 如果某一步 LLM 调用失败，用降级策略（如简化 prompt 重试）
```

**为什么分批而非一次性评估？**
- 一次性评估 20 道题的回答，prompt 太长、质量不稳定
- 分批评估每次只处理 3-5 题，LLM 注意力更集中
- 可以并发调用多批次，加快评估速度

---

## 2. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| 结构化输出 | OpenAI Structured Output + Pydantic | 类型安全，解析零成本 |
| 会话缓存 | Redis（hash 或 string + JSON） | 支持 TTL，多 worker 共享 |
| 面试 Session | UUID + Redis | 轻量，不需要复杂的 session 框架 |
| 评估引擎 | 分批 LLM 调用 + Pydantic 输出 | 质量可控，可并发 |
| Skill 定义 | Markdown 文件 | 简单直观，与现有 prompt 管理一致 |

---

## 3. 与现有代码的集成点

### 新增文件

```
app/
├── modules/
│   └── interview/
│       ├── __init__.py
│       ├── router.py           # FastAPI 路由（/interview）
│       ├── service.py          # 面试业务逻辑
│       ├── session_manager.py  # 面试 session 管理（Redis）
│       ├── question_engine.py  # Skill 出题引擎
│       ├── evaluation.py       # 评估引擎
│       └── schemas.py          # Pydantic 请求/响应模型
│   └── schedule/
│       ├── __init__.py
│       ├── router.py           # 面试安排路由（/schedule）
│       ├── service.py          # 安排业务逻辑
│       └── invite_parser.py    # 面试邀请解析（规则 + AI）
├── skills/                     # Skill 定义文件
│   ├── python_backend.md
│   ├── ai_application.md
│   ├── system_design.md
│   └── frontend.md
├── database/models/
│   ├── interview.py            # 面试记录 SQLAlchemy 模型
│   └── schedule.py             # 面试安排 SQLAlchemy 模型
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 注册 `/interview` 和 `/schedule` 路由 |
| `app/cache/redis_client.py` | 添加面试 session 专用的缓存操作 |
| `requirements.txt` | 可能需要 `apscheduler`（定时任务，面试提醒） |

### 与现有 Tool Calling 的关系

你已有的 Tool Registry（`app/tools/register.py`）可以扩展——评估引擎可以注册为工具，让 Orchestrator 在需要时调用评估功能。

---

## 4. 分步实现方案

### Step 1：数据模型

```python
# app/modules/interview/schemas.py
from pydantic import BaseModel
from enum import Enum

class InterviewStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"

class InterviewConfig(BaseModel):
    skill: str = "python_backend"       # Skill 名称
    total_questions: int = 10           # 总题数
    follow_up_count: int = 1            # 每题追问次数
    difficulty_distribution: dict = {   # 难度分布
        "easy": 0.4,
        "medium": 0.4,
        "hard": 0.2,
    }

class InterviewQuestion(BaseModel):
    question: str
    category: str
    difficulty: str
    follow_up_hint: str

class InterviewEvalItem(BaseModel):
    question: str
    answer: str
    score: int              # 1-10
    feedback: str           # 评语
    category: str

class InterviewReport(BaseModel):
    overall_score: float    # 总分
    summary: str            # 总评
    strengths: list[str]    # 亮点
    improvements: list[str] # 待改进
    items: list[InterviewEvalItem]
```

### Step 2：Session 管理

```python
# app/modules/interview/session_manager.py
import uuid, json
from app.cache.redis_client import redis_client

SESSION_PREFIX = "interview:session:"
SESSION_TTL = 7200  # 2小时

def create_session(config: dict) -> str:
    """创建面试 session"""
    session_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "config": config,
        "status": "created",
        "messages": [],         # 完整对话历史
        "questions_asked": [],  # 已问过的题目（用于去重）
        "current_question_index": 0,
    }
    redis_client.setex(
        f"{SESSION_PREFIX}{session_id}",
        SESSION_TTL,
        json.dumps(session_data, ensure_ascii=False),
    )
    return session_id

def get_session(session_id: str) -> dict | None:
    raw = redis_client.get(f"{SESSION_PREFIX}{session_id}")
    return json.loads(raw) if raw else None

def update_session(session_id: str, data: dict):
    redis_client.setex(
        f"{SESSION_PREFIX}{session_id}",
        SESSION_TTL,
        json.dumps(data, ensure_ascii=False),
    )
```

### Step 3：Skill 出题引擎

```python
# app/modules/interview/question_engine.py
from app.services.llm_service import call_llm
from app.services.prompt_service import get_prompt

def generate_question(
    skill_content: str,
    difficulty: str,
    asked_questions: list[str],
    context: str = "",
) -> dict:
    """基于 Skill 定义生成面试题"""
    system_prompt = f"""你是一位专业的技术面试官。根据以下 Skill 定义出一道面试题。

Skill 定义：
{skill_content}

要求：
- 难度级别：{difficulty}
- 不要重复以下已问过的题目：{asked_questions}
- 返回 JSON 格式：{{"question": "...", "category": "...", "difficulty": "...", "follow_up_hint": "..."}}
"""
    result = call_llm(system_prompt, {"context": context})
    return result

def generate_follow_up(
    original_question: str,
    candidate_answer: str,
    follow_up_hint: str,
) -> str:
    """根据候选人回答生成追问"""
    system_prompt = f"""你是一位技术面试官，正在进行追问。

原始问题：{original_question}
候选人回答：{candidate_answer}
追问方向提示：{follow_up_hint}

请根据候选人的回答生成一个有针对性的追问。如果候选人回答得好，可以深入追问细节；如果回答不好，可以换个角度引导。
只返回追问的问题文本，不要返回其他内容。"""

    result = call_llm(system_prompt, {})
    return result if isinstance(result, str) else result.get("question", str(result))
```

### Step 4：评估引擎

```python
# app/modules/interview/evaluation.py
import json
from app.services.llm_service import call_llm

def evaluate_batch(qa_pairs: list[dict]) -> list[dict]:
    """分批评估（每次 3-5 道题）"""
    system_prompt = """你是面试评估专家。对以下面试问答进行评分。

对每道题返回 JSON 数组：
[
  {
    "question": "原题",
    "score": 1-10 的评分,
    "feedback": "简短评语（50字以内）",
    "category": "考察方向"
  }
]

评分标准：
- 1-3: 回答错误或完全不相关
- 4-5: 了解概念但不够深入
- 6-7: 回答正确，有一定深度
- 8-9: 回答出色，有实际经验
- 10: 完美回答，有独到见解
"""
    result = call_llm(system_prompt, {"qa_pairs": qa_pairs})
    return result if isinstance(result, list) else []

def generate_report(all_evaluations: list[dict]) -> dict:
    """汇总生成总评报告"""
    system_prompt = """你是面试评估专家。根据各题的评分结果生成总评报告。

返回 JSON 格式：
{
  "overall_score": 总分（所有题目平均分，保留1位小数）,
  "summary": "100字以内的总评",
  "strengths": ["亮点1", "亮点2", ...],
  "improvements": ["待改进1", "待改进2", ...]
}
"""
    result = call_llm(system_prompt, {"evaluations": all_evaluations})
    return result

def evaluate_interview(messages: list[dict]) -> dict:
    """完整评估流程：分批 → 汇总"""
    # 1. 提取问答对
    qa_pairs = _extract_qa_pairs(messages)

    # 2. 分批评估（每 3 题一批）
    batch_size = 3
    all_evals = []
    for i in range(0, len(qa_pairs), batch_size):
        batch = qa_pairs[i:i + batch_size]
        evals = evaluate_batch(batch)
        all_evals.extend(evals)

    # 3. 汇总报告
    report = generate_report(all_evals)
    report["items"] = all_evals
    return report

def _extract_qa_pairs(messages: list[dict]) -> list[dict]:
    """从对话历史中提取问答对"""
    pairs = []
    current_q = None
    for msg in messages:
        if msg["role"] == "assistant" and "?" in msg["content"]:
            current_q = msg["content"]
        elif msg["role"] == "user" and current_q:
            pairs.append({"question": current_q, "answer": msg["content"]})
            current_q = None
    return pairs
```

### Step 5：面试路由

```python
# app/modules/interview/router.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/interview", tags=["模拟面试"])

class StartInterviewRequest(BaseModel):
    skill: str = "python_backend"
    total_questions: int = 10

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

@router.post("/start")
async def start_interview(req: StartInterviewRequest):
    """创建面试并出第一题"""
    from app.modules.interview.session_manager import create_session
    from app.modules.interview.question_engine import generate_question

    session_id = create_session(req.model_dump())

    # 加载 skill 定义
    skill_path = f"app/skills/{req.skill}.md"
    with open(skill_path, "r", encoding="utf-8") as f:
        skill_content = f.read()

    # 生成第一题
    question = generate_question(skill_content, "easy", [])

    # 更新 session
    from app.modules.interview.session_manager import get_session, update_session
    session = get_session(session_id)
    session["status"] = "in_progress"
    session["messages"].append({"role": "assistant", "content": question["question"]})
    session["questions_asked"].append(question["question"])
    session["current_question_index"] = 1
    update_session(session_id, session)

    return {"session_id": session_id, "question": question}

@router.post("/answer")
async def submit_answer(req: AnswerRequest):
    """提交回答，获取追问或下一题"""
    from app.modules.interview.session_manager import get_session, update_session
    from app.modules.interview.question_engine import generate_question, generate_follow_up

    session = get_session(req.session_id)
    if not session:
        return {"error": "session 不存在或已过期"}

    # 记录回答
    session["messages"].append({"role": "user", "content": req.answer})

    config = session["config"]
    idx = session["current_question_index"]

    # 判断是否结束
    if idx >= config.get("total_questions", 10):
        session["status"] = "completed"
        update_session(req.session_id, session)
        return {"status": "completed", "message": "面试结束，正在生成评估报告..."}

    # 生成下一题（简化逻辑，实际可加追问判断）
    skill_path = f"app/skills/{config['skill']}.md"
    with open(skill_path, "r", encoding="utf-8") as f:
        skill_content = f.read()

    question = generate_question(
        skill_content, "medium", session["questions_asked"]
    )
    session["messages"].append({"role": "assistant", "content": question["question"]})
    session["questions_asked"].append(question["question"])
    session["current_question_index"] = idx + 1
    update_session(req.session_id, session)

    return {"question": question, "progress": f"{idx + 1}/{config.get('total_questions', 10)}"}

@router.post("/evaluate")
async def evaluate(session_id: str):
    """评估面试结果"""
    from app.modules.interview.session_manager import get_session, update_session
    from app.modules.interview.evaluation import evaluate_interview

    session = get_session(session_id)
    if not session or session["status"] != "completed":
        return {"error": "面试未结束或 session 不存在"}

    session["status"] = "evaluating"
    update_session(session_id, session)

    report = evaluate_interview(session["messages"])

    session["status"] = "evaluated"
    session["report"] = report
    update_session(session_id, session)

    return report
```

### Step 6：面试安排模块

```python
# app/modules/schedule/invite_parser.py
import re
from app.services.llm_service import call_llm

def parse_invite_rule_based(text: str) -> dict | None:
    """规则引擎解析面试邀请（飞书/腾讯会议/Zoom 格式）"""
    result = {}

    # 时间提取
    time_pattern = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*\d{1,2}:\d{2})"
    times = re.findall(time_pattern, text)
    if times:
        result["start_time"] = times[0]

    # 会议链接提取
    link_patterns = [
        r"(https?://meeting\.tencent\.com/\S+)",
        r"(https?://\S*zoom\S*)",
        r"(https?://\S*feishu\S*)",
    ]
    for pattern in link_patterns:
        match = re.search(pattern, text)
        if match:
            result["meeting_link"] = match.group(1)
            break

    return result if result else None

def parse_invite_ai(text: str) -> dict:
    """AI 引擎解析面试邀请"""
    system_prompt = """从面试邀请文本中提取信息，返回 JSON：
{
  "company": "公司名",
  "position": "岗位名",
  "start_time": "YYYY-MM-DD HH:MM",
  "end_time": "YYYY-MM-DD HH:MM（如果有）",
  "meeting_link": "会议链接",
  "interviewer": "面试官姓名（如果有）",
  "notes": "其他备注"
}
缺少的字段填 null。"""
    return call_llm(system_prompt, {"invite_text": text})

def parse_invite(text: str) -> dict:
    """双引擎解析：先规则，再 AI 补充"""
    rule_result = parse_invite_rule_based(text) or {}
    ai_result = parse_invite_ai(text)

    # 规则结果优先（更可靠），AI 补充缺失字段
    if isinstance(ai_result, dict):
        for key, value in ai_result.items():
            if key not in rule_result or rule_result[key] is None:
                rule_result[key] = value

    return rule_result
```

---

## 5. 测试方案

```python
# tests/test_interview.py
import pytest

def test_session_create_and_get():
    """测试面试 session 创建和获取"""
    from app.modules.interview.session_manager import create_session, get_session

    session_id = create_session({"skill": "python_backend", "total_questions": 5})
    assert session_id is not None

    session = get_session(session_id)
    assert session["status"] == "created"
    assert session["config"]["skill"] == "python_backend"

def test_evaluation_batch():
    """测试分批评估"""
    from app.modules.interview.evaluation import evaluate_batch

    qa_pairs = [
        {"question": "Python 的 GIL 是什么？", "answer": "GIL 是全局解释器锁，限制同一时刻只有一个线程执行字节码。"},
    ]
    result = evaluate_batch(qa_pairs)
    assert isinstance(result, list)

def test_invite_parser_rule():
    """测试规则引擎解析面试邀请"""
    from app.modules.schedule.invite_parser import parse_invite_rule_based

    text = "面试时间：2025-04-20 14:00，腾讯会议链接：https://meeting.tencent.com/dm/abc123"
    result = parse_invite_rule_based(text)
    assert result["start_time"] == "2025-04-20 14:00"
    assert "tencent" in result["meeting_link"]
```

### 验证命令

```bash
pytest tests/test_interview.py -v

# 手动验证：启动服务后
# 创建面试
curl -X POST http://localhost:8000/interview/start \
  -H "Content-Type: application/json" \
  -d '{"skill": "python_backend", "total_questions": 5}'

# 提交回答
curl -X POST http://localhost:8000/interview/answer \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<id>", "answer": "GIL 是全局解释器锁..."}'
```

---

## 6. 面试要点

### 常见问题

**Q: 模拟面试的多轮对话上下文是怎么管理的？**
> 用 Redis 存储面试 session，包含完整的 messages 数组。每次用户回答后更新 session，下一次出题/追问时带上全量历史。设置 2 小时 TTL 自动过期。对于超长面试，可以切换到滑动窗口 + 摘要压缩策略。

**Q: Skill 出题是怎么保证不重复的？**
> 每次出题时把已问过的题目列表传给 LLM，在 prompt 中明确要求不要重复。同时在 session 中维护 `questions_asked` 数组做本地去重。

**Q: 评估引擎为什么分批而不是一次性评估？**
> 一次性评估 10-20 道题的问答，prompt 会很长，LLM 的注意力会分散，评分质量不稳定。分批每次处理 3 题，LLM 能更专注。分批还可以并发调用，加快评估速度。最后再做一次汇总生成总评报告。

**Q: 面试邀请解析为什么用"规则 + AI 双引擎"？**
> 规则引擎处理标准格式（如固定的时间/链接模式）非常可靠且零成本。AI 引擎处理非标准文本更灵活。双引擎结合：规则结果优先（可靠），AI 补充缺失字段（灵活）。

### 能讲出的亮点

- **Skill 驱动出题**：面试方向可配置，通过 Markdown 文件定义考察范围和难度分布
- **评估引擎架构**：分批评估 + 结构化输出 + 二次汇总，质量可控
- **历史题目去重**：prompt 级 + 应用级双重去重
- **会话缓存**：Redis + TTL，支持断点续面
- **双引擎解析**：规则 + AI 互补，兼顾可靠性和灵活性
