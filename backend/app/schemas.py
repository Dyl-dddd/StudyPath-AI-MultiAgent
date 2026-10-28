from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal


class AuthInput(BaseModel):
    username: str = Field(min_length=3, max_length=48, pattern=r"^[\w-]+$")
    password: str = Field(min_length=10, max_length=128)


class RegisterInput(AuthInput):
    password_confirm: str = Field(min_length=10, max_length=128)
    captcha_id: str = Field(min_length=36, max_length=36)
    captcha_code: str = Field(min_length=5, max_length=5, pattern=r"^[A-HJ-NP-Z2-9]{5}$")


class KnowledgeBaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    course_name: str = Field(default="", max_length=120)


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    course_name: str
    document_count: int = 0
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    knowledge_base_id: str
    file_name: str
    file_type: str
    file_size: int
    status: str
    error_message: str
    chunk_count: int
    created_at: datetime


class SessionInput(BaseModel):
    knowledge_base_id: str = ""
    course_id: str | None = Field(default=None, max_length=80)
    title: str = Field(default="新建学习对话", max_length=180)
    answer_mode: Literal["library", "model"] = "library"


class ChatInput(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=5000)


class CitationOut(BaseModel):
    citation_id: str
    document_id: str
    document_name: str
    chunk_id: str
    page_start: int | None
    page_end: int | None
    section_title: str
    snippet: str
    retrieval_score: float
    preview_url: str


class ChatOut(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[CitationOut]
    retrieval_mode: str


class ProfileInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str = Field(default="", max_length=80)
    school: str = Field(default="", max_length=160)
    major: str = Field(default="", max_length=120)
    grade: str = Field(default="", max_length=30)
    education_stage: str = Field(default="大学", max_length=24, alias="educationStage")
    learning_subjects: list[str] = Field(default_factory=list, max_length=20, alias="learningSubjects")
    learning_goal: str = Field(default="", max_length=500, alias="learningGoal")
    bio: str = Field(default="", max_length=2000)
    weekly_goal_hours: int = Field(default=18, ge=1, le=168, alias="weeklyGoalHours")
    daily_focus_hours: int = Field(default=2, ge=1, le=24, alias="dailyFocusHours")
    learning_reminders: bool = Field(default=True, alias="learningReminders")
    favorite_course_ids: list[str] = Field(default_factory=list, max_length=100, alias="favoriteCourseIds")

    @field_validator("education_stage")
    @classmethod
    def validate_education_stage(cls, value: str) -> str:
        allowed = {"小学", "初中", "高中", "大学", "其他"}
        normalized = value.strip()
        if normalized not in allowed:
            raise ValueError("学段请选择小学、初中、高中、大学或其他")
        return normalized

    @field_validator("learning_subjects")
    @classmethod
    def normalize_learning_subjects(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if any(len(value) > 40 for value in normalized):
            raise ValueError("单个学科名称不能超过 40 个字符")
        return normalized


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | None = None
    title: str = Field(min_length=1, max_length=240)
    course: str = Field(default="", max_length=160)
    date: str = Field(default="", max_length=80)
    priority: str = Field(default="中", pattern="^(高|中|低)$")
    done: bool = False


class StudyPlanInput(BaseModel):
    tasks: list[TaskInput] = Field(max_length=500)


class QuizAttemptInput(BaseModel):
    course_id: str = Field(default="", max_length=80)
    question_ids: list[int] = Field(min_length=1, max_length=100)
    answers: dict[str, str | list[str]]
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class CourseProgressInput(BaseModel):
    progress: int = Field(ge=0, le=100)
    last_node_id: str = Field(default="", max_length=100)


class MasteryInput(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    mastery: int = Field(ge=0, le=100)


class StudySessionStartInput(BaseModel):
    course_id: str | None = Field(default=None, max_length=80)


class StudySessionFinishInput(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=1, le=43200)


class MistakeReviewInput(BaseModel):
    correct: bool
    selected_answer: str = Field(default="", max_length=1000)
    note: str = Field(default="", max_length=1000)


class CourseBindingInput(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=36)


class FeedbackInput(BaseModel):
    rating: str = Field(pattern="^(helpful|unhelpful)$")
    comment: str = Field(default="", max_length=2000)


class MistakeInput(BaseModel):
    question_id: int
    payload: dict


class MistakeListInput(BaseModel):
    items: list[MistakeInput] = Field(max_length=1000)

