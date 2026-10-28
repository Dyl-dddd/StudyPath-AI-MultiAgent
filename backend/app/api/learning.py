from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import (
    KnowledgeEdge, KnowledgeNode, LearningCourse, QuizAttempt, QuizQuestion,
    CourseProgress, KnowledgeMastery, LearningPathPreference, StudySession, StudyTaskRecord, User, UserMistake, UserNotification, UserProfile, utcnow,
)
from app.schemas import MistakeListInput, ProfileInput, QuizAttemptInput, StudyPlanInput
from app.curriculum_defaults import DEFAULT_CURRICULA

router = APIRouter(tags=["learning"])


def _sync_course_progress(db: Session, user_id: str, course_id: str, last_node_id: str = "") -> int:
    """Keep the course summary aligned with mastered graph concepts."""
    node_ids = db.scalars(
        select(KnowledgeNode.id).where(
            KnowledgeNode.course_id == course_id,
            KnowledgeNode.type.in_(["concept", "application"]),
            or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user_id),
        )
    ).all()
    mastery_by_node = {
        row.node_id: row.mastery
        for row in db.scalars(
            select(KnowledgeMastery).where(
                KnowledgeMastery.user_id == user_id,
                KnowledgeMastery.node_id.in_(node_ids),
            )
        ).all()
    } if node_ids else {}
    progress = round(sum(mastery_by_node.get(node_id, 0) >= 80 for node_id in node_ids) / len(node_ids) * 100) if node_ids else 0
    row = db.scalar(select(CourseProgress).where(CourseProgress.user_id == user_id, CourseProgress.course_id == course_id))
    if row is None:
        row = CourseProgress(user_id=user_id, course_id=course_id)
        db.add(row)
    row.progress = progress
    if last_node_id:
        row.last_node_id = last_node_id
    return progress


def ensure_default_question_for_node(db: Session, node: KnowledgeNode) -> None:
    """Guarantee at least one selectable, answerable practice question per concept."""
    if node.owner_id is not None or node.type not in {"concept", "application"} or db.scalar(
        select(QuizQuestion.id).where(QuizQuestion.concept_id == node.id)
    ):
        return
    description = (node.description or f"{node.name}的基本定义与作用。").strip()
    distractors = [
        value.strip() for value in db.scalars(select(KnowledgeNode.description).where(
            KnowledgeNode.course_id == node.course_id,
            KnowledgeNode.owner_id.is_(None),
            KnowledgeNode.id != node.id,
            KnowledgeNode.type.in_(["concept", "application"]),
        )).all() if value and value.strip() and value.strip() != description
    ]
    options = [description]
    for item in distractors:
        if item not in options:
            options.append(item)
        if len(options) == 4:
            break
    while len(options) < 4:
        options.append(f"该知识点与{node.name}无关，不能作为其定义。")
    course = db.get(LearningCourse, node.course_id)
    db.add(QuizQuestion(
        course_id=node.course_id, type="单选题", difficulty="基础", topic=node.name,
        concept_id=node.id, title=f"关于“{node.name}”，下列哪项表述正确？",
        options=options, answer=description, explanation=description,
        evidence={"title": f"{course.name if course else '课程'}知识图谱", "section": node.name, "excerpt": description},
    ))


def _profile(db: Session, user: User) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            profile = db.get(UserProfile, user.id)
        db.refresh(profile)
    return profile


def _profile_dict(profile: UserProfile) -> dict:
    return {
        "name": profile.name, "school": profile.school, "major": profile.major,
        "grade": profile.grade, "educationStage": profile.education_stage,
        "learningSubjects": profile.learning_subjects or [], "learningGoal": profile.learning_goal,
        "bio": profile.bio,
        "weeklyGoalHours": profile.weekly_goal_hours,
        "dailyFocusHours": profile.daily_focus_hours,
        "learningReminders": profile.learning_reminders,
        "favoriteCourseIds": profile.favorite_course_ids or [],
    }


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _profile_dict(_profile(db, user))


@router.patch("/profile")
def update_profile(payload: ProfileInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = _profile(db, user)
    mapping = {
        "name": "name", "school": "school", "major": "major", "grade": "grade", "bio": "bio",
        "education_stage": "education_stage", "learning_subjects": "learning_subjects", "learning_goal": "learning_goal",
        "weeklyGoalHours": "weekly_goal_hours", "dailyFocusHours": "daily_focus_hours",
        "learningReminders": "learning_reminders",
        "favoriteCourseIds": "favorite_course_ids",
    }
    for key, value in payload.model_dump(exclude_unset=True, by_alias=False).items():
        if key == "favorite_course_ids":
            valid_ids = set(db.scalars(select(LearningCourse.id).where(LearningCourse.id.in_(value))).all()) if value else set()
            if valid_ids != set(value):
                raise HTTPException(422, "收藏列表包含不存在的课程")
        setattr(profile, mapping.get(key, key), value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(profile)
    return _profile_dict(profile)


@router.get("/courses")
def list_courses(db: Session = Depends(get_db), user: User = Depends(current_user)):
    courses = db.scalars(select(LearningCourse).order_by(LearningCourse.name)).all()
    progress_rows = db.scalars(select(CourseProgress).where(CourseProgress.user_id == user.id)).all()
    progress = {row.course_id: row.progress for row in progress_rows}
    return [{
        "id": course.id, "name": course.name, "category": course.category,
        "progress": progress.get(course.id, 0),
        "points": course.points, "chapter": course.chapter, "color": course.color, "icon": course.icon,
    } for course in courses]


@router.get("/courses/{course_id}/graph")
def get_course_graph(course_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if db.get(LearningCourse, course_id) is None:
        raise HTTPException(404, "课程不存在")
    nodes = db.scalars(select(KnowledgeNode).where(KnowledgeNode.course_id == course_id,
        or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user.id)).order_by(KnowledgeNode.id)).all()
    edges = db.scalars(select(KnowledgeEdge).where(KnowledgeEdge.course_id == course_id,
        or_(KnowledgeEdge.owner_id.is_(None), KnowledgeEdge.owner_id == user.id))).all()
    mastery = {row.node_id: row.mastery for row in db.scalars(select(KnowledgeMastery).where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.node_id.in_([node.id for node in nodes]))).all()} if nodes else {}
    return {
        "nodes": [{"id": node.id, "name": node.name, "type": node.type, "mastery": mastery.get(node.id, 0), "description": node.description} for node in nodes],
        "links": [{"source": edge.source, "target": edge.target} for edge in edges],
    }


@router.get("/quizzes")
def list_quizzes(course_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(QuizQuestion).where((QuizQuestion.owner_id.is_(None)) | (QuizQuestion.owner_id == user.id)).order_by(QuizQuestion.id)
    if course_id:
        query = query.where(QuizQuestion.course_id == course_id)
    questions = db.scalars(query).all()
    return [{
        "id": question.id, "type": question.type, "difficulty": question.difficulty,
        "topic": question.topic, "course": db.get(LearningCourse, question.course_id).name,
        "courseId": question.course_id, "conceptId": question.concept_id,
        "title": question.title, "options": question.options,
        "transferQuestionIds": question.transfer_question_ids, "evidence": question.evidence,
    } for question in questions]


@router.post("/quiz-attempts", status_code=201)
def create_quiz_attempt(payload: QuizAttemptInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if len(payload.question_ids) != len(set(payload.question_ids)):
        raise HTTPException(422, "题目列表不能包含重复项")
    questions = db.scalars(select(QuizQuestion).where(
        QuizQuestion.id.in_(payload.question_ids),
        (QuizQuestion.owner_id.is_(None)) | (QuizQuestion.owner_id == user.id),
    )).all()
    by_id = {question.id: question for question in questions}
    if len(by_id) != len(set(payload.question_ids)):
        raise HTTPException(422, "题目不存在或已下架")
    objective = [by_id[qid] for qid in payload.question_ids if by_id[qid].type != "简答题"]
    correct = 0
    results = []
    for question in objective:
        selected = payload.answers.get(str(question.id))
        is_correct = (isinstance(selected, list) and sorted(selected) == sorted(question.answer)) if isinstance(question.answer, list) else selected == question.answer
        if is_correct:
            correct += 1
        results.append({"questionId": question.id, "correct": is_correct, "selectedAnswer": selected,
                        "answer": question.answer, "explanation": question.explanation,
                        "misconception": question.misconceptions.get(str(selected), "") if isinstance(question.misconceptions, dict) and isinstance(selected, str) else "",
                        "conceptId": question.concept_id, "courseId": question.course_id})
        if question.concept_id and db.get(KnowledgeNode, question.concept_id):
            mastery_row = db.scalar(select(KnowledgeMastery).where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.node_id == question.concept_id))
            if mastery_row is None:
                mastery_row = KnowledgeMastery(user_id=user.id, node_id=question.concept_id, mastery=0)
                db.add(mastery_row)
            mastery_row.mastery = min(100, mastery_row.mastery + 15) if is_correct else max(0, mastery_row.mastery - 20)
    score = round(correct / len(objective) * 100) if objective else 0
    course_id = payload.course_id or (by_id[payload.question_ids[0]].course_id if payload.question_ids else "")
    if any(question.course_id != course_id for question in by_id.values()):
        raise HTTPException(422, "一次测验只能提交同一课程的题目")
    last_node_id = next((by_id[qid].concept_id for qid in reversed(payload.question_ids)
                         if by_id[qid].concept_id and db.get(KnowledgeNode, by_id[qid].concept_id)), "")
    if course_id:
        _sync_course_progress(db, user.id, course_id, last_node_id)
    attempt = QuizAttempt(user_id=user.id, course_id=course_id, score=score,
                          question_count=len(objective), answers=payload.answers, results=results,
                          duration_seconds=payload.duration_seconds, at=utcnow())
    db.add(attempt)
    profile = db.get(UserProfile, user.id)
    if profile is not None and profile.learning_reminders:
        db.add(UserNotification(user_id=user.id, title="测验已完成", body=f"本次得分 {score} 分，共完成 {len(objective)} 道客观题。"))
    db.commit()
    db.refresh(attempt)
    return {"id": attempt.id, "at": attempt.at.isoformat(), "score": attempt.score,
            "questionCount": attempt.question_count, "courseId": attempt.course_id,
            "durationSeconds": attempt.duration_seconds, "results": results}


@router.get("/quiz-attempts")
def list_quiz_attempts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.at.desc())).all()
    courses = {course.id: course.name for course in db.scalars(select(LearningCourse)).all()}
    return [{"id": item.id, "at": item.at.isoformat(), "score": item.score, "questionCount": item.question_count,
             "courseId": item.course_id, "course": courses.get(item.course_id, item.course_id)} for item in attempts]


@router.get("/quiz-attempts/{attempt_id}")
def get_quiz_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user.id))
    if not attempt:
        raise HTTPException(404, "测验记录不存在")
    return {"id": attempt.id, "at": attempt.at.isoformat(), "score": attempt.score,
            "questionCount": attempt.question_count, "courseId": attempt.course_id,
            "durationSeconds": attempt.duration_seconds, "results": attempt.results or []}


@router.get("/mistakes")
def list_mistakes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(UserMistake).where(UserMistake.user_id == user.id).order_by(UserMistake.updated_at.desc())).all()
    return [row.payload for row in rows]


@router.put("/mistakes")
def replace_mistakes(payload: MistakeListInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ids = {item.question_id for item in payload.items}
    if len(ids) != len(payload.items):
        raise HTTPException(422, "错题列表不能包含重复题目")
    if ids:
        unknown = db.scalars(select(QuizQuestion.id).where(QuizQuestion.id.in_(ids),
            or_(QuizQuestion.owner_id.is_(None), QuizQuestion.owner_id == user.id))).all()
        if set(unknown) != ids:
            raise HTTPException(422, "错题包含不存在的题目")
    existing = {row.question_id: row for row in db.scalars(select(UserMistake).where(UserMistake.user_id == user.id)).all()}
    for question_id, row in existing.items():
        if question_id not in ids:
            db.delete(row)
    for item in payload.items:
        row = existing.get(item.question_id)
        if row:
            row.payload = item.payload
            row.updated_at = utcnow()
        else:
            db.add(UserMistake(user_id=user.id, question_id=item.question_id, payload=item.payload))
    db.commit()
    return [item.payload for item in payload.items]


def _task_dict(task: StudyTaskRecord) -> dict:
    return {"id": task.id, "title": task.title, "course": task.course, "date": task.date,
            "priority": task.priority, "done": task.done}


@router.get("/study-plans")
def list_study_tasks(db: Session = Depends(get_db), user: User = Depends(current_user)):
    tasks = db.scalars(select(StudyTaskRecord).where(StudyTaskRecord.user_id == user.id).order_by(StudyTaskRecord.id)).all()
    return [_task_dict(task) for task in tasks]


@router.put("/study-plans")
def save_study_tasks(payload: StudyPlanInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    provided_ids = [task.id for task in payload.tasks if task.id is not None]
    if len(provided_ids) != len(set(provided_ids)):
        raise HTTPException(422, "学习计划不能包含重复任务")
    existing = {task.id: task for task in db.scalars(select(StudyTaskRecord).where(StudyTaskRecord.user_id == user.id)).all()}
    retained: set[int] = set()
    saved: list[StudyTaskRecord] = []
    for item in payload.tasks:
        values = item.model_dump(exclude={"id"})
        row = existing.get(item.id) if item.id is not None else None
        if row:
            for key, value in values.items():
                setattr(row, key, value)
            retained.add(row.id)
        else:
            row = StudyTaskRecord(user_id=user.id, **values)
            db.add(row)
        saved.append(row)
    for task_id, row in existing.items():
        if task_id not in retained:
            db.delete(row)
    db.flush()
    result = [_task_dict(task) for task in saved]
    db.commit()
    return result


@router.get("/dashboard")
def learning_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = datetime.now(timezone.utc)
    start = (now.date() - timedelta(days=6))
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.at >= datetime.combine(start, datetime.min.time(), timezone.utc)).order_by(QuizAttempt.at)).all()
    all_attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.at.desc())).all()
    tasks = db.scalars(select(StudyTaskRecord).where(StudyTaskRecord.user_id == user.id)).all()
    mistakes = db.scalars(select(UserMistake).where(UserMistake.user_id == user.id)).all()
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == user.id, StudySession.started_at >= datetime.combine(start, datetime.min.time(), timezone.utc))).all()
    day_scores: dict[str, list[int]] = {}
    active_days = {item.at.date() for item in all_attempts}
    for attempt in attempts:
        day_scores.setdefault(attempt.at.date().isoformat(), []).append(attempt.score)
    week_scores = [round(sum(day_scores[d.isoformat()]) / len(day_scores[d.isoformat()])) if d.isoformat() in day_scores else None
                   for d in (start + timedelta(days=i) for i in range(7))]
    cursor = now.date()
    if cursor not in active_days:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
    course_list = list_courses(db, user)
    week_seconds = [0] * 7
    today_seconds = 0
    for session in sessions:
        started_at = session.started_at if session.started_at.tzinfo else session.started_at.replace(tzinfo=timezone.utc)
        seconds = session.duration_seconds if session.state == "completed" else max(0, min(12 * 3600, int((now - started_at).total_seconds())))
        index = (session.started_at.date() - start).days
        if 0 <= index < 7:
            week_seconds[index] += seconds
        if session.started_at.date() == now.date():
            today_seconds += seconds
    mastered = db.scalar(select(func.count(KnowledgeMastery.id)).where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.mastery >= 80)) or 0
    return {"hoursToday": round(today_seconds / 3600, 1), "mastered": mastered,
            "weeklyTasks": sum(item.done for item in tasks), "streak": streak, "weekHours": [round(seconds / 3600, 1) for seconds in week_seconds],
            "weekScores": week_scores, "courses": course_list, "tasks": [_task_dict(item) for item in tasks]}


def seed_learning_catalog(db: Session) -> None:
    catalog_path = Path(__file__).resolve().parents[1] / "learning_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for item in catalog["courses"]:
        if db.get(LearningCourse, item["id"]) is None:
            db.add(LearningCourse(id=item["id"], name=item["name"], category=item["category"], points=item["points"],
                                  chapter=item["chapter"], color=item["color"], icon=item["icon"]))
    db.flush()
    for item in catalog["graphNodes"]:
        if db.get(KnowledgeNode, item["id"]) is None:
            db.add(KnowledgeNode(id=item["id"], course_id="ds", name=item["name"], type=item["type"], description=item["description"]))
    for course_id, items in DEFAULT_CURRICULA.items():
        if db.get(KnowledgeNode, course_id) is None:
            course = db.get(LearningCourse, course_id)
            if course:
                db.add(KnowledgeNode(id=course_id, course_id=course_id, name=course.name, type="course", description=f"{course.name}课程的核心概念与先修关系。"))
        for node_id, name, node_type, description, _parent in items:
            if db.get(KnowledgeNode, node_id) is None:
                db.add(KnowledgeNode(id=node_id, course_id=course_id, name=name, type=node_type, description=description))
    db.flush()
    existing_edges = {(edge.course_id, edge.source, edge.target) for edge in db.scalars(select(KnowledgeEdge)).all()}
    for item in catalog["graphLinks"]:
        key = ("ds", item["source"], item["target"])
        if key not in existing_edges:
            db.add(KnowledgeEdge(course_id=key[0], source=key[1], target=key[2]))
            existing_edges.add(key)
    for course_id, items in DEFAULT_CURRICULA.items():
        for node_id, _name, _node_type, _description, parent_id in items:
            key = (course_id, parent_id, node_id)
            if key not in existing_edges and db.get(KnowledgeNode, parent_id) and db.get(KnowledgeNode, node_id):
                db.add(KnowledgeEdge(course_id=course_id, source=parent_id, target=node_id))
                existing_edges.add(key)
    db.flush()
    for item in catalog["questions"]:
        if db.get(QuizQuestion, item["id"]) is None:
            db.add(QuizQuestion(id=item["id"], course_id=next((c["id"] for c in catalog["courses"] if c["name"] == item.get("course")), "ds"),
                                type=item["type"], difficulty=item["difficulty"], topic=item["topic"], concept_id=item.get("conceptId", ""),
                                title=item["title"], options=item.get("options", []), answer=item.get("answer", ""),
                                explanation=item["explanation"], misconceptions=item.get("misconceptions", {}),
                                transfer_question_ids=item.get("transferQuestionIds", []), evidence=item.get("evidence")))
    db.flush()
    for node in db.scalars(select(KnowledgeNode).where(KnowledgeNode.type.in_(["concept", "application"]), KnowledgeNode.owner_id.is_(None))).all():
        ensure_default_question_for_node(db, node)
    db.commit()
