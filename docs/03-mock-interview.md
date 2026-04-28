# 模拟面试模块（含面试安排）

本模块实现 AI 驱动的模拟面试系统：基于 Skill 蓝图结构化出题、按回答质量自适应追问、按主问题轮次评估、生成面试报告，并提供面试邀请解析。当前 W3 的优先级是 **真实感 > 成本与稳定性 > 严格可控性**。

---

## 1. 概念学习

### 多轮对话管理

模拟面试的核心是“主问题 → 候选人回答 → 可选追问 → 下一题”。系统需要保存：

- `messages`：完整对话历史。
- `questions_asked`：已出主问题列表，用于去重。
- `current_question_index`：已出主问题数，追问不计入。
- `current_main_question`：当前主问题结构。
- `current_follow_up_count`：当前主问题已追问次数。
- `covered_topics`：已覆盖考点。
- `recent_performance`：最近回答质量摘要，供 planner 和难度递进使用。

短面试可以保存全量历史；如果后续面试轮次变长，再切换到“最近 N 轮 + 历史摘要”的混合策略。

### Message Contract

从评估引擎开始，面试消息统一使用 metadata 标记主问题、追问和回答归属：

```python
{
    "role": "assistant",
    "content": "...",
    "metadata": {
        "question_type": "main",
        "question_id": "q_1",
        "parent_question_id": None,
        "category": "Python 基础",
        "difficulty": "easy",
        "assessment_focus": "考察 GIL 的概念和影响",
    },
}
```

约束：

- 主问题：`question_type="main"`，`parent_question_id=None`
- 追问：`question_type="follow_up"`，`parent_question_id` 指向主问题 ID
- 用户回答：metadata 至少包含 `answer_to_question_id`
- `current_question_index` 只统计主问题，不统计追问

### 结构化输出

LLM 输出必须转成稳定 JSON，不能让路由层依赖自由文本。关键结构包括：

```python
class InterviewQuestion(BaseModel):
    question: str
    category: str
    difficulty: str
    difficulty_reason: str
    follow_up_hint: str
    assessment_focus: str
```

`difficulty_reason` 用来让模型解释“为什么这题属于当前难度”，`assessment_focus` 用来给后续 planner 和 evaluation 提供考察重点。

### Skill 蓝图化出题

Markdown Skill 仍是配置源，但不再每次原样全文塞进 prompt。运行时先把 Skill 解析成面试蓝图：

```python
{
    "topics": ["Python 基础", "Web 框架", "数据库", "异步编程", "系统设计"],
    "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
    "reference_collections": ["python_docs"],
    "difficulty_rubric": {
        "easy": "基础概念、定义、简单辨析",
        "medium": "原理解释、场景应用、常见坑",
        "hard": "系统设计、权衡、故障分析、性能与边界"
    }
}
```

每次出题只传当前需要的蓝图摘要、目标难度 rubric、已问列表、已覆盖考点和候选人上下文。这样比每次传整份 Markdown 更省 token，也能减少模型注意力被无关配置稀释。

### 难度控制

难度控制分三层：

1. **路由 / planner 决定目标难度**：根据题量、难度分布和最近表现决定 easy / medium / hard。
2. **prompt 注入难度 rubric**：告诉模型该难度对应什么能力要求。
3. **应用层校验返回契约**：返回的 `difficulty` 必须等于请求难度，题目不能重复。

系统不尝试用规则自动判断题目真实难度，而是要求模型给出 `difficulty_reason`，再由测试和人工验收检查质量。

难度序列生成采用最小规则：

- 根据 `total_questions` 和 `difficulty_distribution` 先生成基础主问题难度序列。
- 示例：`total_questions=5`、`{"easy": 0.4, "medium": 0.4, "hard": 0.2}` → `easy, easy, medium, medium, hard`。
- `performance_signal=strong` 时，下一题最多上调一档；`performance_signal=weak` 时，下一题最多下调一档；`normal` 时按基础序列。
- 保护约束：不连续出 3 道 hard；不在 easy 配额未消耗时直接从 easy 跳到 hard。

### 自适应追问 Planner

追问不再是“每题固定追问一次”。候选人回答后，planner 决定下一步：

```python
{
    "next_action": "follow_up" | "next_question" | "complete",
    "reason": "为什么这样决定",
    "follow_up_focus": "如果追问，追问什么",
    "next_difficulty": "easy|medium|hard",
    "performance_signal": "strong|normal|weak"
}
```

决策规则：

- 回答模糊、遗漏关键点、暴露误区，且追问次数未达上限 → `follow_up`
- 回答充分，或追问次数已达上限 → `next_question`
- 主问题数量达到 `total_questions` 且无需继续追问 → `complete`

`generate_follow_up` 只负责在“已经决定要追问”时生成一句追问，不负责判断是否追问。

### 评估引擎

新版评估以“主问题轮次”为单位，而不是把所有 assistant 问句等权评分：

```text
主问题
  ├─ 初答
  ├─ 追问 1
  ├─ 追问回答 1
  └─ 追问 2 ...
```

评分要综合主问题回答和追问回答，判断候选人最终是否掌握该考点。追问不作为独立主问题计数。

### 面试安排解析

面试邀请解析继续采用“规则 + AI 双引擎”：

- 规则引擎：提取标准时间和腾讯会议 / Zoom / 飞书链接。
- AI 引擎：补充公司、岗位、面试官、备注等字段。
- 合并策略：规则结果优先，AI 补充缺失字段。

---

## 2. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| 结构化输出 | Pydantic + JSON 解析 | 固定返回契约，便于测试和路由编排 |
| 会话缓存 | Redis string + JSON | 支持 TTL，多轮面试状态读写频繁 |
| 面试 Session | UUID + Redis | 轻量，适合短生命周期会话 |
| Skill 定义 | Markdown + 运行时蓝图 | 配置易读，同时避免每轮全文 prompt |
| 追问策略 | Planner 决策 + follow_up 生成 | 更像真人面试官，避免机械追问 |
| 评估引擎 | 按主问题轮次分批评估 | 主问题与追问聚合，评分更贴近真实面试 |

---

## 3. 与现有代码的集成点

### 新增或修改文件

```text
app/modules/interview/
├── schemas.py              # 面试配置、题目、评估报告等结构
├── session_manager.py      # Redis session CRUD
├── question_engine.py      # Skill 蓝图、出题、追问生成
├── interview_planner.py    # 回答后决定 follow_up / next_question / complete
├── evaluation.py           # 主问题轮次提取、分批评估、汇总报告
└── router.py               # /interview/start /answer /evaluate

app/modules/schedule/
├── invite_parser.py        # 规则 + AI 双引擎解析邀请
└── router.py               # /schedule/parse-invite

app/skills/python_backend.md
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 注册 `/interview` 和 `/schedule` 路由 |
| `app/modules/interview/schemas.py` | 为题目、session metadata、评估项补充必要字段 |
| `tests/` | 增加 question_engine、planner、evaluation、invite_parser 测试 |

---

## 4. 分步实现方案

### Step 1：数据模型

创建基础 schema：`InterviewStatus`、`InterviewConfig`、`InterviewQuestion`、`InterviewEvalItem`、`InterviewReport`。`InterviewConfig` 保留 `follow_up_count` 与 `difficulty_distribution`，后续 planner 使用。

### Step 2：Session 管理

用 Redis 保存面试 session，key 前缀 `interview:session:`，TTL 7200 秒。session 至少保存 config、status、messages、questions_asked、current_question_index；D5 起扩展 current_main_question、current_follow_up_count、covered_topics、recent_performance。

### Step 3：Skill 蓝图 + 出题引擎

`question_engine.py` 提供：

- `load_skill(skill_name)`
- `build_skill_blueprint(skill_content)`
- `generate_question(skill_blueprint, difficulty, asked_questions, covered_topics, candidate_context="")`
- `generate_follow_up(original_question, candidate_answer, follow_up_focus, recent_context="")`

边界要求：非法 difficulty 拒绝；返回 difficulty 必须一致；重复题拒绝；追问函数兼容 `call_llm` 的 `raw` 兜底。

### Step 4：评估引擎

`evaluation.py` 提供：

- `_extract_interview_turns(messages)`：把主问题与追问聚合成 turn。
- `evaluate_batch(turns)`：每批评估 2-3 个主问题轮次。
- `generate_report(all_evaluations)`：汇总总评。
- `evaluate_interview(messages)`：完整入口。

### Step 5：面试路由 + Planner

`/interview/start` 创建 session、构建 Skill 蓝图、生成第一题。

`/interview/answer` 记录回答后调用 `interview_planner.plan_next_interview_action(...)`：

- `follow_up`：调用 `generate_follow_up`
- `next_question`：调用 `generate_question`
- `complete`：更新 session 为 completed

`/interview/evaluate` 调用评估引擎并写回报告。

### Step 6：面试安排模块 + 测试

实现 `invite_parser.py` 与 `/schedule/parse-invite`。补齐 question_engine、planner、evaluation、invite_parser 测试。

### Step 7：端到端验收 + 面试复习

跑通：start → 多轮 answer（含追问或下一题）→ completed → evaluate。复盘 Skill 蓝图、难度 rubric、自适应追问、主追问聚合评估、双引擎解析。

---

## 5. 测试方案

推荐测试拆分。除已在 D3 落地的 `tests/test_question_engine.py` 外，其余测试文件在对应实现步骤补齐后运行。

- `tests/test_question_engine.py`
  - Skill 蓝图构建
  - prompt 包含难度 rubric 和已问列表
  - 非法难度、返回难度不一致、重复题拒绝
  - follow_up raw 兜底

- `tests/test_interview_planner.py`
  - 从 `app.modules.interview.interview_planner` 导入 `plan_next_interview_action`
  - 回答模糊 → follow_up
  - 追问达到上限 → next_question
  - 主问题达到总数 → complete
  - `total_questions=5` 默认生成 `easy, easy, medium, medium, hard`
  - `strong / weak` 最多让下一题上下浮动一档

- `tests/test_interview_evaluation.py`
  - 主问题与追问归入同一 turn
  - 追问不被当作独立主问题
  - report 包含 items / strengths / improvements

- `tests/test_schedule_invite_parser.py`
  - 规则解析时间和会议链接
  - mock AI 解析结果，验证 `parse_invite` 保留规则提取的时间和会议链接，只用 AI 补充 company / position 等缺失字段

验证命令：

```bash
pytest tests/ -v
```

---

## 6. 面试要点

**Q1: 模拟面试的多轮对话上下文是怎么管理的？**
> Redis 保存 session，messages 记录完整历史，assistant metadata 标记 main / follow_up。session 还保存当前主问题、追问次数、已问主问题、已覆盖考点和最近表现。短面试用全量历史，长面试可切换滑动窗口 + 摘要。

**Q2: Skill 出题为什么要蓝图化？**
> Markdown Skill 易维护，但每轮全文传入会浪费 token 并稀释注意力。蓝图化后只传当前相关考点、难度 rubric、已覆盖维度和已问列表，既保留可配置性，又让 prompt 更聚焦。

**Q3: 难度如何控制？**
> 路由或 planner 决定目标难度，prompt 注入 easy / medium / hard 的 rubric，模型返回题目和 difficulty_reason，应用层校验返回 difficulty 与请求一致。

**Q4: 为什么追问要用 planner？**
> 真人面试不会机械追问。planner 根据回答质量、追问次数上限和进度决定追问、下一题或结束，让节奏更自然。

**Q5: 评估为什么按主问题轮次？**
> 追问是主问题的一部分，不能等权当作独立题。按 turn 聚合后，能评价候选人经过追问后是否真正掌握该考点。

**Q6: 面试邀请解析为什么用规则 + AI 双引擎？**
> 规则处理标准格式稳定、零成本；AI 处理非标准文本灵活。规则优先，AI 补充缺失字段。

### 能讲出的亮点

- Skill 蓝图化
- 难度 rubric 控制
- 自适应追问 planner
- 主问题与追问聚合评估
- Redis TTL 会话管理
- 规则 + AI 双引擎邀请解析
