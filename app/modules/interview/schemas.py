from enum import Enum
from math import isclose

from pydantic import BaseModel, Field, model_validator


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
    skill: str = Field(default="python_backend", pattern=r"^[a-z0-9][a-z0-9_-]*$")
    total_questions: int = Field(default=10, ge=1)  # 主问题数
    follow_up_count: int = Field(default=1, ge=0)  # 每题的追问数
    difficulty_distribution: dict[str, float] = Field(
        default_factory=lambda: {
            "easy": 0.4,
            "medium": 0.4,
            "hard": 0.2,
        }
    )

    # D3 会按 skill 名拼接 Markdown 路径、按难度分布分配题目，这里先把配置边界收紧。
    @model_validator(mode="after")
    def validate_difficulty_distribution(self) -> "InterviewConfig":
        expected_levels = {"easy", "medium", "hard"}
        actual_levels = set(self.difficulty_distribution)
        if actual_levels != expected_levels:
            raise ValueError(
                "difficulty_distribution 必须恰好包含 easy、medium、hard。"
            )
        if any(weight < 0 or weight > 1 for weight in self.difficulty_distribution.values()):
            raise ValueError("difficulty_distribution 中每个权重必须在 0 到 1 之间。")
        if not isclose(
            sum(self.difficulty_distribution.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise ValueError("difficulty_distribution 所有权重必须相加等于 1.0。")
        return self


# 单道题类：题干、类别、难度、难度原因、追问提示和考察重点。
class InterviewQuestion(BaseModel):
    question: str
    category: str
    difficulty: str
    difficulty_reason: str
    follow_up_hint: str
    assessment_focus: str


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
