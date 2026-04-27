from enum import Enum

from pydantic import BaseModel, Field


# 这组模型既给 FastAPI 做边界校验，也会给后续 LLM structured output 复用。
class InterviewStatus(str, Enum):
    # 状态字面量会被后续 session / 路由直接持久化和判断，尽量保持稳定。
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"


# 面试配置类：技能方向、主问题数、追问次数和难度分布。
class InterviewConfig(BaseModel):
    skill: str = "python_backend"
    total_questions: int = 10  # 主问题数
    follow_up_count: int = 1  # 每题的追问数
    difficulty_distribution: dict[str, float] = Field(
        default_factory=lambda: {
            "easy": 0.4,
            "medium": 0.4,
            "hard": 0.2,
        }
    )


# 单道题类：题干、类别、难度和追问提示。
class InterviewQuestion(BaseModel):
    question: str
    category: str
    difficulty: str
    follow_up_hint: str


# 单题评估类：题目、回答、分数、反馈和分类。
class InterviewEvalItem(BaseModel):
    question: str
    answer: str
    score: int
    feedback: str
    category: str


# 总评报告类：总分、总结、亮点、改进项和逐题结果。
class InterviewReport(BaseModel):
    overall_score: float
    summary: str
    strengths: list[str]
    improvements: list[str]
    items: list[InterviewEvalItem]
