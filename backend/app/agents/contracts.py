from typing import Literal
from pydantic import BaseModel, Field


AgentIntent = Literal["auto", "profile", "mistake", "local_qa", "tutor", "graph"]


class AgentRunInput(BaseModel):
    intent: AgentIntent = "auto"
    question: str = Field(default="", max_length=5000)
    session_id: str | None = Field(default=None, max_length=36)
    question_id: int | None = Field(default=None, ge=1)
    course_id: str | None = Field(default=None, max_length=80)


class AgentParallelInput(AgentRunInput):
    intents: list[Literal["profile", "graph"]] = Field(min_length=2, max_length=2)


class AgentTask(BaseModel):
    task_id: str
    user_id: str
    education_stage: str
    intent: str


class AgentError(BaseModel):
    code: str
    message: str


class AgentResult(BaseModel):
    task_id: str
    intent: str
    agent: str
    status: Literal["completed", "partial", "failed"]
    evidence: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    result: dict = Field(default_factory=dict)
    error: AgentError | None = None
    elapsed_ms: int = 0
