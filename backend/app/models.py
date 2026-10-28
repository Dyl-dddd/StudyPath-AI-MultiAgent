from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    course_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_base", cascade="all, delete-orphan")
    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("owner_id", "knowledge_base_id", "file_hash", name="uq_document_hash_per_kb"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    storage_name: Mapped[str] = mapped_column(String(80), unique=True)
    file_type: Mapped[str] = mapped_column(String(10))
    file_size: Mapped[int] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="UPLOADED", index=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str] = mapped_column(String(500), default="")
    chunk_index: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(180))
    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True, nullable=True)
    answer_mode: Mapped[str] = mapped_column(String(20), default="library")
    title: Mapped[str] = mapped_column(String(180), default="新建学习对话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    knowledge_base: Mapped[KnowledgeBase | None] = relationship(back_populates="sessions")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[ChatSession] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class MessageCitation(Base):
    __tablename__ = "message_citations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True)
    score: Mapped[float]
    message: Mapped[ChatMessage] = relationship(back_populates="citations")


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(Integer, index=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)


class CaptchaChallenge(Base):
    __tablename__ = "captcha_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    answer_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(Integer, index=True)


class IndexJob(Base):
    __tablename__ = "index_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    school: Mapped[str] = mapped_column(String(160), default="")
    major: Mapped[str] = mapped_column(String(120), default="")
    grade: Mapped[str] = mapped_column(String(30), default="")
    education_stage: Mapped[str] = mapped_column(String(24), default="大学")
    learning_subjects: Mapped[list] = mapped_column(JSON, default=list)
    learning_goal: Mapped[str] = mapped_column(Text, default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    weekly_goal_hours: Mapped[int] = mapped_column(Integer, default=18)
    daily_focus_hours: Mapped[int] = mapped_column(Integer, default=2)
    learning_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    favorite_course_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LearningCourse(Base):
    __tablename__ = "learning_courses"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="")
    points: Mapped[int] = mapped_column(Integer, default=0)
    chapter: Mapped[str] = mapped_column(String(240), default="")
    color: Mapped[str] = mapped_column(String(20), default="#7357dc")
    icon: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    type: Mapped[str] = mapped_column(String(24), default="concept")
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    __table_args__ = (UniqueConstraint("course_id", "source", "target", name="uq_knowledge_edge"),)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30), default="单选题")
    difficulty: Mapped[str] = mapped_column(String(30), default="基础")
    topic: Mapped[str] = mapped_column(String(160), default="")
    concept_id: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[object] = mapped_column(JSON, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    misconceptions: Mapped[dict] = mapped_column(JSON, default=dict)
    transfer_question_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class StudyTaskRecord(Base):
    __tablename__ = "study_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    course: Mapped[str] = mapped_column(String(160), default="")
    date: Mapped[str] = mapped_column(String(80), default="")
    priority: Mapped[str] = mapped_column(String(8), default="中")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(String(80), default="")
    score: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[list] = mapped_column(JSON, default=list)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UserMistake(Base):
    __tablename__ = "user_mistakes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_mistake"),)


class MistakeVariantSet(Base):
    __tablename__ = "mistake_variant_sets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_question_id: Mapped[int] = mapped_column(Integer, index=True)
    variants: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudySession(Base):
    __tablename__ = "study_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("learning_courses.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16), default="active", index=True)


class CourseProgress(Base):
    __tablename__ = "course_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    last_node_id: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_course_progress_user_course"),)


class KnowledgeMastery(Base):
    __tablename__ = "knowledge_mastery"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    mastery: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_knowledge_mastery_user_node"),)


class LearningPathPreference(Base):
    __tablename__ = "learning_path_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    ordered_node_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_learning_path_preference_user_course"),)


class UserCourseBinding(Base):
    __tablename__ = "user_course_bindings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("learning_courses.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_user_course_kb_binding"),)


class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True)
    rating: Mapped[str] = mapped_column(String(12))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "message_id", name="uq_message_feedback_user_message"),)


class UserNotification(Base):
    __tablename__ = "user_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
