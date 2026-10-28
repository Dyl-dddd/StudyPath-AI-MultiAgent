import json
import logging
import re
import uuid
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import (CourseProgress, KnowledgeBase, KnowledgeEdge, KnowledgeMastery, KnowledgeNode, LearningCourse,
                        LearningPathPreference, MistakeVariantSet, QuizQuestion, StudySession, User, UserCourseBinding, UserMistake, UserNotification, UserProfile, utcnow)
from app.schemas import CourseBindingInput, CourseProgressInput, MasteryInput, MistakeReviewInput, StudySessionStartInput
from app.rag.pipeline import _client
from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["learning-activity"])
logger = logging.getLogger(__name__)


class VariantSubmitInput(BaseModel):
    answers: dict[str, str]


@router.post("/mistakes/{question_id}/variants")
async def generate_mistake_variants(question_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    mistake = db.scalar(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id == question_id))
    question = db.get(QuizQuestion, question_id)
    if mistake is None or question is None or (question.owner_id is not None and question.owner_id != user.id):
        raise HTTPException(404, "错题不存在")

    node = db.get(KnowledgeNode, question.concept_id) if question.concept_id else None
    course = db.get(LearningCourse, question.course_id)
    concept = node.name if node else question.topic or "该题考查的知识点"
    concept_description = node.description if node else question.explanation
    profile = db.get(UserProfile, user.id)
    education_stage = profile.education_stage if profile else "大学"
    grade = profile.grade if profile else ""
    evidence = question.evidence or {}
    source_title = question.title.strip()
    source_normalized = re.sub(r"[\W_]+", "", source_title).lower()
    source_options = sorted(re.sub(r"[\W_]+", "", str(option)).lower() for option in (question.options or []))
    source_answer = re.sub(r"[\W_]+", "", str(question.answer)).lower()
    prompt_data = {
        "course": course.name if course else "",
        "concept": concept,
        "concept_description": concept_description,
        "source_question": source_title,
        "source_options": question.options or [],
        "source_answer": question.answer,
        "source_explanation": question.explanation,
        "evidence": evidence,
        "difficulty": question.difficulty,
        "education_stage": education_stage,
        "grade": grade,
    }
    system_prompt = (
        f"你是面向{education_stage}{f' {grade}' if grade else ''}学生的课程命题教师。请围绕给定考点设计恰好 3 道全新的单选题，用于举一反三。"
        "三题必须考查同一核心知识，但分别采用不同情境、条件或推理路径；不能照抄、换词复述或仅替换数字后复现原题。"
        "题干词汇、阅读长度、选项复杂度和推理步骤须符合给定学段与年级；不降低知识准确性。"
        "每题提供 4 个互不重复的选项，answer 必须与其中一个选项逐字相同，explanation 简洁说明依据。"
        "只使用给定的课程、知识点和解析信息，不补充无关事实。若信息不足以可靠命题，返回 {\"questions\": []}。"
        "只返回 JSON：{\"questions\":[{\"title\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"answer\":\"...\",\"explanation\":\"...\"}]}"
    )
    try:
        settings = get_settings()
        generation_options = {}
        llm_host = (urlparse(settings.llm_base_url).hostname or "").lower()
        if llm_host.endswith("aliyuncs.com") and settings.llm_model.lower().startswith("deepseek-v4"):
            # DeepSeek V4 enables lengthy chain-of-thought by default. These
            # questions are simple transfer exercises, so return the requested
            # JSON directly and keep the response bounded.
            generation_options = {
                "extra_body": {"enable_thinking": False},
                "max_tokens": 2048,
            }
        response = await _client().chat.completions.create(
            model=get_settings().llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            **generation_options,
        )
        content = (response.choices[0].message.content or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
        generated = json.loads(content).get("questions", [])
    except Exception as error:
        if isinstance(error, HTTPException):
            raise
        if isinstance(error, APIConnectionError):
            logger.warning("LLM connection failed while generating variants for question %s", question_id, exc_info=True)
            raise HTTPException(502, "大模型服务连接不稳定，系统已自动重试一次，请稍后点击重新生成") from None
        logger.exception("Failed to generate variants for question %s", question_id)
        raise HTTPException(502, f"变式题生成失败：{type(error).__name__}") from None

    if not isinstance(generated, list) or len(generated) != 3:
        raise HTTPException(502, "暂时无法生成 3 道可靠的变式题，请稍后重试")
    variants = []
    seen_titles = []
    for item in generated:
        if not isinstance(item, dict):
            raise HTTPException(502, "变式题格式无效，请稍后重试")
        title = str(item.get("title", "")).strip()
        title_normalized = re.sub(r"[\W_]+", "", title).lower()
        options = item.get("options")
        answer = item.get("answer")
        explanation = str(item.get("explanation", "")).strip()
        normalized_options = sorted(re.sub(r"[\W_]+", "", option).lower() for option in options) if isinstance(options, list) and all(isinstance(option, str) for option in options) else []
        repeats_source_content = title_normalized == source_normalized and normalized_options == source_options and re.sub(r"[\W_]+", "", str(answer)).lower() == source_answer
        if (not title or not title_normalized or title_normalized == source_normalized
                or SequenceMatcher(None, title_normalized, source_normalized).ratio() >= 0.9
                or any(SequenceMatcher(None, title_normalized, previous).ratio() >= 0.9 for previous in seen_titles)
                or repeats_source_content
                or not isinstance(options, list) or len(options) != 4
                or any(not isinstance(option, str) or not option.strip() for option in options)
                or len(set(options)) != 4 or answer not in options or not explanation):
            raise HTTPException(502, "生成题目与原题重复或格式不完整，请重新生成")
        seen_titles.append(title_normalized)
        variants.append({"id": len(variants) + 1, "title": title, "options": options, "answer": answer, "explanation": explanation})

    now = utcnow()
    db.query(MistakeVariantSet).filter(MistakeVariantSet.expires_at < now).delete(synchronize_session=False)
    variant_set = MistakeVariantSet(id=str(uuid.uuid4()), user_id=user.id, source_question_id=question_id,
                                    variants=variants, expires_at=now + timedelta(minutes=30), created_at=now)
    db.add(variant_set)
    db.commit()
    return {"setId": variant_set.id, "course": course.name if course else "课程练习", "topic": concept, "sourceTitle": source_title,
            "conceptDescription": concept_description, "difficulty": question.difficulty,
            "variants": [{key: value for key, value in item.items() if key not in {"answer", "explanation"}} for item in variants]}


def _record_mistake_review(row: UserMistake, correct: bool, selected_answer: str, note: str) -> dict:
    data = dict(row.payload)
    now = utcnow()
    attempts = list(data.get("attempts", []))
    attempts.append({"at": now.isoformat(), "correct": correct, "selectedAnswer": selected_answer,
                     "feedback": note or ("复习回答正确" if correct else "复习回答错误")})
    data["attempts"] = attempts[-100:]
    if correct:
        data["correctStreak"] = int(data.get("correctStreak", 0)) + 1
        data["lastCorrectAt"] = now.isoformat()
        data["mastered"] = data["correctStreak"] >= 2
        data["nextReviewAt"] = "" if data["mastered"] else (now + timedelta(days=3)).isoformat()
    else:
        data["wrong"] = int(data.get("wrong", 0)) + 1
        data["correctStreak"] = 0
        data["mastered"] = False
        data["misconception"] = note or "本次复习未答对，建议回看关联知识点。"
        data["lastWrongAt"] = now.isoformat()
        data["nextReviewAt"] = (now + timedelta(days=1)).isoformat()
    row.payload, row.updated_at = data, now
    return data


@router.post("/mistakes/{question_id}/variants/{set_id}/submit")
def submit_mistake_variants(question_id: int, set_id: str, payload: VariantSubmitInput,
                            db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id == question_id))
    variant_set = db.scalar(select(MistakeVariantSet).where(
        MistakeVariantSet.id == set_id, MistakeVariantSet.user_id == user.id,
        MistakeVariantSet.source_question_id == question_id, MistakeVariantSet.expires_at > utcnow(),
    ))
    if row is None or variant_set is None:
        raise HTTPException(404, "练习已失效，请重新生成")
    variants = variant_set.variants or []
    expected_ids = {str(item["id"]) for item in variants}
    if len(variants) != 3 or set(payload.answers) != expected_ids:
        raise HTTPException(422, "请提交三道题的完整答案")
    results = []
    for item in variants:
        selected = payload.answers[str(item["id"])]
        if selected not in item["options"]:
            raise HTTPException(422, "答案选项无效")
        results.append({"id": item["id"], "correct": selected == item["answer"], "answer": item["answer"],
                        "explanation": item["explanation"]})
    correct_count = sum(result["correct"] for result in results)
    missed = "、".join(f"第 {index + 1} 题" for index, result in enumerate(results) if not result["correct"])
    note = f"举一反三练习答对 {correct_count}/3。{f'需要巩固：{missed}。' if missed else '三道变式题全部答对。'}"
    updated_mistake = _record_mistake_review(row, correct_count == 3, f"{correct_count}/3", note)
    db.delete(variant_set)
    db.commit()
    return {"correctCount": correct_count, "total": 3, "results": results, "mistake": updated_mistake}


@router.post("/study-sessions", status_code=201)
def start_study_session(payload: StudySessionStartInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.course_id and not db.get(LearningCourse, payload.course_id):
        raise HTTPException(404, "课程不存在")
    if db.scalar(select(StudySession.id).where(StudySession.user_id == user.id, StudySession.state == "active")):
        raise HTTPException(409, "已有进行中的学习计时，请先结束或恢复计时")
    row = StudySession(id=str(uuid.uuid4()), user_id=user.id, course_id=payload.course_id, started_at=utcnow(), state="active")
    db.add(row)
    db.commit()
    return {"id": row.id, "courseId": row.course_id, "startedAt": row.started_at.isoformat(), "state": row.state}


@router.get("/study-sessions/active")
def get_active_study_session(db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(StudySession).where(StudySession.user_id == user.id, StudySession.state == "active").order_by(StudySession.started_at.desc()))
    return None if row is None else {"id": row.id, "courseId": row.course_id, "startedAt": row.started_at.isoformat(), "state": row.state}


@router.post("/study-sessions/{session_id}/finish")
def finish_study_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user.id))
    if row is None:
        raise HTTPException(404, "学习计时不存在")
    if row.state == "active":
        row.ended_at = utcnow()
        started_at = row.started_at if row.started_at.tzinfo else row.started_at.replace(tzinfo=timezone.utc)
        row.duration_seconds = max(1, min(43200, int((row.ended_at - started_at).total_seconds())))
        row.state = "completed"
        profile = db.get(UserProfile, user.id)
        if row.duration_seconds >= 300 and profile is not None and profile.learning_reminders:
            minutes = max(1, round(row.duration_seconds / 60))
            db.add(UserNotification(user_id=user.id, title="专注学习完成", body=f"本次专注学习 {minutes} 分钟，记录已保存到账户。"))
        db.commit()
    return {"id": row.id, "courseId": row.course_id, "startedAt": row.started_at.isoformat(),
            "endedAt": row.ended_at.isoformat() if row.ended_at else None, "durationSeconds": row.duration_seconds, "state": row.state}


@router.get("/analytics")
def get_learning_analytics(days: int = 7, db: Session = Depends(get_db), user: User = Depends(current_user)):
    days = min(90, max(1, days))
    start = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    rows = db.scalars(select(StudySession).where(StudySession.user_id == user.id, StudySession.started_at >= datetime.combine(start, datetime.min.time(), timezone.utc))).all()
    buckets = {(start + timedelta(days=i)).isoformat(): 0 for i in range(days)}
    for row in rows:
        started_at = row.started_at if row.started_at.tzinfo else row.started_at.replace(tzinfo=timezone.utc)
        seconds = row.duration_seconds if row.state == "completed" else max(0, min(43200, int((utcnow() - started_at).total_seconds())))
        key = row.started_at.date().isoformat()
        if key in buckets:
            buckets[key] += seconds
    return {"days": [{"date": day, "seconds": seconds, "hours": round(seconds / 3600, 2)} for day, seconds in buckets.items()],
            "totalSeconds": sum(buckets.values()), "totalHours": round(sum(buckets.values()) / 3600, 2)}


@router.get("/me/courses/{course_id}/progress")
def get_course_progress(course_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    row = db.scalar(select(CourseProgress).where(CourseProgress.user_id == user.id, CourseProgress.course_id == course_id))
    return {"courseId": course_id, "progress": row.progress if row else 0, "lastNodeId": row.last_node_id if row else ""}


@router.patch("/me/courses/{course_id}/progress")
def update_course_progress(course_id: str, payload: CourseProgressInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    if payload.last_node_id and db.scalar(select(KnowledgeNode.id).where(KnowledgeNode.id == payload.last_node_id, KnowledgeNode.course_id == course_id,
            or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user.id))) is None:
        raise HTTPException(422, "知识点不属于该课程")
    row = db.scalar(select(CourseProgress).where(CourseProgress.user_id == user.id, CourseProgress.course_id == course_id))
    if row is None:
        row = CourseProgress(user_id=user.id, course_id=course_id)
        db.add(row)
    row.progress, row.last_node_id = payload.progress, payload.last_node_id
    db.commit()
    return {"courseId": course_id, "progress": row.progress, "lastNodeId": row.last_node_id, "updatedAt": row.updated_at.isoformat()}


@router.get("/me/courses/{course_id}/learning-path")
def get_personalized_learning_path(course_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Recommend weak concepts with their graph prerequisites in prerequisite order."""
    course = db.get(LearningCourse, course_id)
    if course is None:
        raise HTTPException(404, "课程不存在")

    nodes = db.scalars(select(KnowledgeNode).where(KnowledgeNode.course_id == course_id,
        or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user.id))).all()
    if not nodes:
        return {"courseId": course_id, "courseName": course.name, "steps": [], "progress": 0}
    node_by_id = {node.id: node for node in nodes}
    edges = db.scalars(select(KnowledgeEdge).where(KnowledgeEdge.course_id == course_id,
        or_(KnowledgeEdge.owner_id.is_(None), KnowledgeEdge.owner_id == user.id))).all()
    prerequisites: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    for edge in edges:
        if edge.source in node_by_id and edge.target in node_by_id:
            prerequisites[edge.target].add(edge.source)

    mastery = {
        row.node_id: row.mastery
        for row in db.scalars(select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user.id,
            KnowledgeMastery.node_id.in_(list(node_by_id)),
        )).all()
    }
    mistake_stats: dict[str, dict] = {}
    mistake_rows = db.execute(
        select(QuizQuestion.concept_id, UserMistake.payload)
        .join(UserMistake, UserMistake.question_id == QuizQuestion.id)
        .where(UserMistake.user_id == user.id, QuizQuestion.course_id == course_id,
               or_(QuizQuestion.owner_id.is_(None), QuizQuestion.owner_id == user.id))
    ).all()
    now = utcnow()
    for concept_id, payload in mistake_rows:
        if not concept_id or concept_id not in node_by_id or not isinstance(payload, dict) or payload.get("mastered"):
            continue
        stats = mistake_stats.setdefault(concept_id, {"wrongCount": 0, "due": False})
        stats["wrongCount"] += max(0, int(payload.get("wrong", 0) or 0))
        due_at = payload.get("nextReviewAt")
        if due_at:
            try:
                parsed = datetime.fromisoformat(str(due_at).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                stats["due"] = stats["due"] or parsed <= now
            except ValueError:
                pass

    indegree_all = {node_id: len(parents) for node_id, parents in prerequisites.items()}
    children_all: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    for node_id, parents in prerequisites.items():
        for parent in parents:
            children_all[parent].add(node_id)
    depth = {node_id: 0 for node_id in node_by_id}
    ready_all = sorted(node_id for node_id, degree in indegree_all.items() if degree == 0)
    visited_all = 0
    while ready_all:
        parent = ready_all.pop(0)
        visited_all += 1
        for child in sorted(children_all[parent]):
            depth[child] = max(depth[child], depth[parent] + 1)
            indegree_all[child] -= 1
            if indegree_all[child] == 0:
                ready_all.append(child)
                ready_all.sort()

    learnable = [node for node in nodes if node.type in {"concept", "application"}]
    eligible = [node for node in learnable if mastery.get(node.id, 0) < 80]
    if not eligible:
        eligible = [node for node in nodes if node.type == "chapter" and mastery.get(node.id, 0) < 80]
    if not eligible:
        return {"courseId": course_id, "courseName": course.name, "steps": [], "progress": 100}
    # Prioritize due mistakes and repeated errors, while including each selected
    # concept's unfinished graph prerequisites before it.
    targets = sorted(
        eligible,
        key=lambda node: (
            not mistake_stats.get(node.id, {}).get("due", False),
            -mistake_stats.get(node.id, {}).get("wrongCount", 0),
            mastery.get(node.id, 0),
            depth.get(node.id, 0),
            node.name,
        ),
    )[:3]
    required = {node.id for node in targets}
    pending = list(required)
    while pending:
        node_id = pending.pop()
        for parent in prerequisites.get(node_id, set()):
            if parent != node_id and mastery.get(parent, 0) < 80 and parent not in required:
                required.add(parent)
                pending.append(parent)

    indegree = {node_id: 0 for node_id in required}
    children: dict[str, set[str]] = {node_id: set() for node_id in required}
    for node_id in required:
        for parent in prerequisites.get(node_id, set()) & required:
            indegree[node_id] += 1
            children[parent].add(node_id)
    ready = sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=lambda item: node_by_id[item].name)
    ordered: list[str] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for child in sorted(children[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda item: node_by_id[item].name)
    # Keep malformed/cyclic imported graphs visible instead of silently dropping concepts.
    ordered.extend(sorted(required - set(ordered), key=lambda item: node_by_id[item].name))

    steps = []
    for index, node_id in enumerate(ordered):
        node = node_by_id[node_id]
        score = mastery.get(node_id, 0)
        stats = mistake_stats.get(node_id, {"wrongCount": 0, "due": False})
        parents = sorted(prerequisites.get(node_id, set()))
        if stats.get("due"):
            reason = f"关联错题已到复习时间；当前掌握度 {score}%，建议先完成间隔复测。"
        elif stats.get("wrongCount", 0):
            reason = f"关联错题累计答错 {stats['wrongCount']} 次；先补齐该知识点，再做变式练习。"
        elif parents:
            parent_names = "、".join(node_by_id[parent].name for parent in parents if parent in node_by_id)
            reason = f"该知识点是薄弱目标的前置内容；先巩固 {parent_names or '前置知识'}。"
        else:
            reason = f"当前掌握度 {score}%，这是本轮优先补强的知识点。"
        steps.append({
            "nodeId": node.id,
            "name": node.name,
            "type": node.type,
            "mastery": score,
            "wrongCount": stats.get("wrongCount", 0),
            "due": bool(stats.get("due")),
            "prerequisites": parents,
            "state": "current" if index == 0 else "next",
            "reason": reason,
        })
    preference = db.scalar(select(LearningPathPreference).where(
        LearningPathPreference.user_id == user.id, LearningPathPreference.course_id == course_id))
    if preference and preference.ordered_node_ids:
        order = {node_id: index for index, node_id in enumerate(preference.ordered_node_ids)}
        steps.sort(key=lambda step: (order.get(step["nodeId"], len(order) + len(steps)), step["nodeId"]))
        for index, step in enumerate(steps):
            step["state"] = "current" if index == 0 else "next"
    done_count = sum(1 for node in learnable if mastery.get(node.id, 0) >= 80)
    return {"courseId": course_id, "courseName": course.name, "steps": steps,
            "progress": round(done_count / len(learnable) * 100) if learnable else 100,
            "customized": bool(preference and preference.ordered_node_ids)}


@router.put("/me/courses/{course_id}/learning-path")
def save_learning_path(course_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    ordered_ids = payload.get("orderedNodeIds", [])
    if not isinstance(ordered_ids, list) or len(ordered_ids) > 500 or any(not isinstance(item, str) for item in ordered_ids):
        raise HTTPException(422, "学习路径顺序格式无效")
    if len(ordered_ids) != len(set(ordered_ids)):
        raise HTTPException(422, "学习路径不能包含重复知识点")
    valid_ids = set(db.scalars(select(KnowledgeNode.id).where(
        KnowledgeNode.course_id == course_id,
        KnowledgeNode.id.in_(ordered_ids) if ordered_ids else KnowledgeNode.id == "",
        or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user.id),
    )).all())
    if valid_ids != set(ordered_ids):
        raise HTTPException(422, "学习路径包含不属于当前课程或账号的知识点")
    row = db.scalar(select(LearningPathPreference).where(
        LearningPathPreference.user_id == user.id, LearningPathPreference.course_id == course_id))
    if row is None:
        row = LearningPathPreference(user_id=user.id, course_id=course_id, ordered_node_ids=ordered_ids)
        db.add(row)
    else:
        row.ordered_node_ids = ordered_ids
        row.updated_at = utcnow()
    db.commit()
    return {"courseId": course_id, "orderedNodeIds": row.ordered_node_ids, "updatedAt": row.updated_at.isoformat()}


@router.put("/knowledge-mastery")
def update_knowledge_mastery(payload: MasteryInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    node = db.scalar(select(KnowledgeNode).where(KnowledgeNode.id == payload.node_id,
        or_(KnowledgeNode.owner_id.is_(None), KnowledgeNode.owner_id == user.id)))
    if node is None:
        raise HTTPException(404, "知识点不存在")
    row = db.scalar(select(KnowledgeMastery).where(KnowledgeMastery.user_id == user.id, KnowledgeMastery.node_id == node.id))
    if row is None:
        row = KnowledgeMastery(user_id=user.id, node_id=node.id)
        db.add(row)
    row.mastery = payload.mastery
    db.commit()
    return {"nodeId": row.node_id, "courseId": node.course_id, "mastery": row.mastery, "updatedAt": row.updated_at.isoformat()}


@router.get("/me/courses/{course_id}/knowledge-base")
def get_course_knowledge_base(course_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserCourseBinding).where(UserCourseBinding.user_id == user.id, UserCourseBinding.course_id == course_id))
    return {"courseId": course_id, "knowledgeBaseId": row.knowledge_base_id if row else None}


@router.put("/me/courses/{course_id}/knowledge-base")
def bind_course_knowledge_base(course_id: str, payload: CourseBindingInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(LearningCourse, course_id):
        raise HTTPException(404, "课程不存在")
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == payload.knowledge_base_id, KnowledgeBase.owner_id == user.id))
    if kb is None:
        raise HTTPException(404, "个人知识库不存在或无权访问")
    row = db.scalar(select(UserCourseBinding).where(UserCourseBinding.user_id == user.id, UserCourseBinding.course_id == course_id))
    if row is None:
        db.add(UserCourseBinding(user_id=user.id, course_id=course_id, knowledge_base_id=kb.id))
    else:
        row.knowledge_base_id = kb.id
    db.commit()
    return {"courseId": course_id, "knowledgeBaseId": kb.id}


@router.delete("/me/courses/{course_id}/knowledge-base", status_code=204)
def unbind_course_knowledge_base(course_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserCourseBinding).where(UserCourseBinding.user_id == user.id, UserCourseBinding.course_id == course_id))
    if row:
        db.delete(row)
        db.commit()


@router.patch("/mistakes/{question_id}")
def update_mistake(question_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id == question_id))
    if row is None:
        raise HTTPException(404, "错题记录不存在")
    allowed = {"saved", "mastered", "nextReviewAt", "misconception"}
    if not payload or set(payload) - allowed:
        raise HTTPException(422, "仅支持更新收藏、掌握状态、复习时间和错因")
    row.payload = {**row.payload, **payload}
    row.updated_at = utcnow()
    db.commit()
    return row.payload


@router.delete("/mistakes/{question_id}", status_code=204)
def delete_mistake(question_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id == question_id))
    if row:
        db.delete(row)
        db.commit()


@router.post("/mistakes/{question_id}/review")
def review_mistake(question_id: int, payload: MistakeReviewInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id == question_id))
    if row is None:
        raise HTTPException(404, "错题记录不存在")
    data = _record_mistake_review(row, payload.correct, payload.selected_answer, payload.note)
    db.commit()
    return data


@router.get("/notifications")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(UserNotification).where(UserNotification.user_id == user.id)
    if unread_only:
        query = query.where(UserNotification.read_at.is_(None))
    rows = db.scalars(query.order_by(UserNotification.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "title": row.title, "body": row.body, "read": row.read_at is not None,
             "createdAt": row.created_at.isoformat()} for row in rows]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(UserNotification).where(UserNotification.id == notification_id, UserNotification.user_id == user.id))
    if row is None:
        raise HTTPException(404, "通知不存在")
    row.read_at = row.read_at or utcnow()
    db.commit()
    return {"id": row.id, "read": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(UserNotification).where(UserNotification.user_id == user.id, UserNotification.read_at.is_(None))).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
    db.commit()
    return {"updated": len(rows)}
