import hmac
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import current_user
from app.models import KnowledgeEdge, KnowledgeNode, LearningCourse, QuizQuestion, User
from app.api.learning import ensure_default_question_for_node

router = APIRouter(prefix="/api/admin", tags=["content-admin"])


def require_content_admin(x_content_admin_token: str | None = Header(default=None), user: User = Depends(current_user)):
    settings = get_settings()
    configured = settings.content_admin_token
    if not configured:
        raise HTTPException(503, "课程内容管理未启用，请在服务端配置 CONTENT_ADMIN_TOKEN")
    admin_usernames = {
        username.strip()
        for username in getattr(settings, "content_admin_usernames", "").split(",")
        if username.strip()
    }
    if user.username not in admin_usernames:
        raise HTTPException(403, "当前账号不是课程内容管理员")
    if not x_content_admin_token or not hmac.compare_digest(x_content_admin_token, configured):
        raise HTTPException(403, "无权管理课程内容")
    return user


class CourseBody(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="", max_length=80)
    points: int = Field(default=0, ge=0, le=100000)
    chapter: str = Field(default="", max_length=240)
    color: str = Field(default="#7357dc", max_length=20)
    icon: str = Field(default="", max_length=20)


class NodeBody(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    type: str = Field(default="concept", max_length=24)
    description: str = Field(default="", max_length=5000)


class EdgeBody(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)


class QuestionBody(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    type: str = Field(default="单选题", max_length=30)
    difficulty: str = Field(default="基础", max_length=30)
    topic: str = Field(default="", max_length=160)
    concept_id: str = Field(default="", max_length=100)
    title: str = Field(min_length=1, max_length=10000)
    options: list[str] = Field(default_factory=list, max_length=20)
    answer: str | list[str]
    explanation: str = Field(default="", max_length=10000)
    misconceptions: dict = Field(default_factory=dict)
    transfer_question_ids: list[int] = Field(default_factory=list, max_length=20)
    evidence: dict | None = None


def _course_out(row: LearningCourse):
    return {"id": row.id, "name": row.name, "category": row.category, "points": row.points,
            "chapter": row.chapter, "color": row.color, "icon": row.icon}


@router.post("/courses", status_code=201)
def create_course(payload: CourseBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    if db.get(LearningCourse, payload.id):
        raise HTTPException(409, "课程 ID 已存在")
    row = LearningCourse(**payload.model_dump())
    db.add(row)
    db.commit()
    return _course_out(row)


@router.patch("/courses/{course_id}")
def update_course(course_id: str, payload: CourseBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.get(LearningCourse, course_id)
    if row is None:
        raise HTTPException(404, "课程不存在")
    if payload.id != course_id:
        raise HTTPException(422, "课程 ID 不允许修改")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return _course_out(row)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.get(LearningCourse, course_id)
    if row is None:
        raise HTTPException(404, "课程不存在")
    db.delete(row)
    db.commit()


@router.get("/courses/{course_id}/graph")
def get_admin_graph(course_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    nodes = db.scalars(select(KnowledgeNode).where(KnowledgeNode.course_id == course_id, KnowledgeNode.owner_id.is_(None)).order_by(KnowledgeNode.id)).all()
    edges = db.scalars(select(KnowledgeEdge).where(KnowledgeEdge.course_id == course_id, KnowledgeEdge.owner_id.is_(None))).all()
    return {"nodes": [{"id": item.id, "name": item.name, "type": item.type, "description": item.description} for item in nodes],
            "edges": [{"source": item.source, "target": item.target} for item in edges]}


@router.post("/courses/{course_id}/nodes", status_code=201)
def create_node(course_id: str, payload: NodeBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    if db.get(KnowledgeNode, payload.id):
        raise HTTPException(409, "知识点 ID 已存在")
    row = KnowledgeNode(course_id=course_id, **payload.model_dump())
    db.add(row)
    db.flush()
    ensure_default_question_for_node(db, row)
    db.commit()
    return {"id": row.id, "courseId": row.course_id, "name": row.name, "type": row.type, "description": row.description}


@router.patch("/courses/{course_id}/nodes/{node_id}")
def update_node(course_id: str, node_id: str, payload: NodeBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.scalar(select(KnowledgeNode).where(KnowledgeNode.id == node_id, KnowledgeNode.course_id == course_id, KnowledgeNode.owner_id.is_(None)))
    if row is None:
        raise HTTPException(404, "知识点不存在")
    if payload.id != node_id:
        raise HTTPException(422, "知识点 ID 不允许修改")
    row.name, row.type, row.description = payload.name, payload.type, payload.description
    ensure_default_question_for_node(db, row)
    db.commit()
    return {"id": row.id, "courseId": row.course_id, "name": row.name, "type": row.type, "description": row.description}


@router.delete("/courses/{course_id}/nodes/{node_id}", status_code=204)
def delete_node(course_id: str, node_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.scalar(select(KnowledgeNode).where(KnowledgeNode.id == node_id, KnowledgeNode.course_id == course_id, KnowledgeNode.owner_id.is_(None)))
    if row is None:
        raise HTTPException(404, "知识点不存在")
    db.delete(row)
    db.commit()


@router.put("/courses/{course_id}/edges")
def replace_course_edges(course_id: str, edges: list[EdgeBody], db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    if len(edges) > 2000:
        raise HTTPException(422, "关系数量超出限制")
    node_ids = set(db.scalars(select(KnowledgeNode.id).where(KnowledgeNode.course_id == course_id, KnowledgeNode.owner_id.is_(None))).all())
    pairs = [(edge.source, edge.target) for edge in edges]
    if len(pairs) != len(set(pairs)) or any(source not in node_ids or target not in node_ids or source == target for source, target in pairs):
        raise HTTPException(422, "图谱关系重复、指向无效节点或形成自环")
    db.query(KnowledgeEdge).filter(KnowledgeEdge.course_id == course_id, KnowledgeEdge.owner_id.is_(None)).delete(synchronize_session=False)
    db.add_all([KnowledgeEdge(course_id=course_id, source=source, target=target) for source, target in pairs])
    db.commit()
    return {"courseId": course_id, "edgeCount": len(pairs)}


@router.post("/questions", status_code=201)
def create_question(payload: QuestionBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    if not db.get(LearningCourse, payload.course_id):
        raise HTTPException(404, "课程不存在")
    row = QuizQuestion(**payload.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id, "courseId": row.course_id}


@router.get("/questions")
def list_admin_questions(course_id: str | None = None, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    query = select(QuizQuestion).where(QuizQuestion.owner_id.is_(None)).order_by(QuizQuestion.id)
    if course_id:
        query = query.where(QuizQuestion.course_id == course_id)
    return [{"id": row.id, "courseId": row.course_id, "type": row.type, "difficulty": row.difficulty,
             "topic": row.topic, "conceptId": row.concept_id, "title": row.title, "options": row.options,
             "answer": row.answer, "explanation": row.explanation, "misconceptions": row.misconceptions,
             "transferQuestionIds": row.transfer_question_ids, "evidence": row.evidence}
            for row in db.scalars(query).all()]


@router.patch("/questions/{question_id}")
def update_question(question_id: int, payload: QuestionBody, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.get(QuizQuestion, question_id)
    if row is None:
        raise HTTPException(404, "题目不存在")
    if not db.get(LearningCourse, payload.course_id):
        raise HTTPException(404, "课程不存在")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return {"id": row.id, "courseId": row.course_id}


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_content_admin)):
    row = db.get(QuizQuestion, question_id)
    if row is None:
        raise HTTPException(404, "题目不存在")
    db.delete(row)
    db.commit()
