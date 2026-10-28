import asyncio
import logging
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.agents.contracts import AgentRunInput, AgentResult, AgentTask
from app.agents.roles import ROLE_HANDLERS, resolve_intent
from app.models import User, UserProfile

logger = logging.getLogger("studypath.agents.orchestrator")
_user_calls: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = asyncio.Lock()
_run_semaphore = asyncio.Semaphore(4)
_parallel_slots = threading.BoundedSemaphore(4)
_READ_ONLY_PARALLEL = {"profile", "graph"}


async def _check_limit(user_id: str) -> None:
    now = time.monotonic()
    async with _rate_lock:
        calls = _user_calls[user_id]
        while calls and now - calls[0] >= 60:
            calls.popleft()
        if len(calls) >= 12:
            raise HTTPException(429, "智能学习请求较频繁，请稍后再试")
        calls.append(now)


async def _run_one(db: Session, user: User, payload: AgentRunInput, intent: str) -> AgentResult:
    task_id = str(uuid.uuid4())
    profile = db.get(UserProfile, user.id)
    task = AgentTask(task_id=task_id, user_id=user.id, education_stage=profile.education_stage if profile else "未设置", intent=intent)
    started = time.perf_counter()
    async with _run_semaphore:
        try:
            timeout = 90 if intent == "mistake" else 60
            result = await asyncio.wait_for(ROLE_HANDLERS[intent](db, user, task, payload), timeout=timeout)
            result.elapsed_ms = round((time.perf_counter() - started) * 1000)
            logger.info("agent_task task_id=%s user_id=%s intent=%s status=%s elapsed_ms=%d", task_id, user.id, intent, result.status, result.elapsed_ms)
            return result
        except asyncio.TimeoutError:
            db.rollback()
            logger.warning("agent_task task_id=%s user_id=%s intent=%s status=timeout", task_id, user.id, intent)
            return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": "timeout", "message": "本次学习任务超时，请稍后重试"}, elapsed_ms=round((time.perf_counter() - started) * 1000))
        except HTTPException as error:
            db.rollback()
            logger.info("agent_task task_id=%s user_id=%s intent=%s status=rejected", task_id, user.id, intent)
            return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": f"http_{error.status_code}", "message": str(error.detail)}, elapsed_ms=round((time.perf_counter() - started) * 1000))
        except Exception as error:
            db.rollback()
            logger.warning("agent_task task_id=%s user_id=%s intent=%s status=error error_type=%s", task_id, user.id, intent, type(error).__name__)
            return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": "agent_unavailable", "message": "该智能学习服务暂不可用，请稍后重试"}, elapsed_ms=round((time.perf_counter() - started) * 1000))


async def run_agent(db: Session, user: User, payload: AgentRunInput) -> dict:
    await _check_limit(user.id)
    intent = resolve_intent(payload)
    result = await _run_one(db, user, payload, intent)
    if result.status == "failed" and intent in {"profile", "graph", "tutor"}:
        logger.info("agent_task_retry user_id=%s intent=%s attempt=2", user.id, intent)
        result = await _run_one(db, user, payload, intent)
    return result.model_dump()


async def run_parallel_readonly(db: Session, user: User, payload: AgentRunInput, intents: list[str]) -> dict:
    await _check_limit(user.id)
    if not 2 <= len(intents) <= 2 or len(set(intents)) != len(intents) or not set(intents).issubset(_READ_ONLY_PARALLEL):
        raise HTTPException(422, "并行编排仅允许同时运行画像与图谱两个只读智能体")
    if not _parallel_slots.acquire(blocking=False):
        raise HTTPException(429, "并行分析任务已满，请稍后重试")
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)

    def execute_readonly(intent: str) -> AgentResult:
        task_id = str(uuid.uuid4())
        started = time.perf_counter()
        with factory() as worker_db:
            worker_user = worker_db.get(User, user.id)
            if worker_user is None:
                return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": "account_unavailable", "message": "当前账号不可用"})
            profile = worker_db.get(UserProfile, worker_user.id)
            task = AgentTask(task_id=task_id, user_id=worker_user.id, education_stage=profile.education_stage if profile else "未设置", intent=intent)
            try:
                # Each worker owns a distinct synchronous SQLAlchemy Session. Only
                # the profile and graph agents are admitted to this read-only fan-out.
                result = asyncio.run(ROLE_HANDLERS[intent](worker_db, worker_user, task, payload))
                result.elapsed_ms = round((time.perf_counter() - started) * 1000)
                logger.info("agent_task task_id=%s user_id=%s intent=%s status=%s elapsed_ms=%d", task_id, user.id, intent, result.status, result.elapsed_ms)
                return result
            except HTTPException as error:
                worker_db.rollback()
                return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": f"http_{error.status_code}", "message": str(error.detail)}, elapsed_ms=round((time.perf_counter() - started) * 1000))
            except Exception as error:
                worker_db.rollback()
                logger.warning("agent_task task_id=%s user_id=%s intent=%s status=error error_type=%s", task_id, user.id, intent, type(error).__name__)
                return AgentResult(task_id=task_id, intent=intent, agent=intent, status="failed", error={"code": "agent_unavailable", "message": "该只读分析暂不可用，请稍后重试"}, elapsed_ms=round((time.perf_counter() - started) * 1000))

    try:
        results = await asyncio.wait_for(asyncio.gather(*(asyncio.to_thread(execute_readonly, intent) for intent in intents)), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(504, "并行分析超时，请稍后重试") from None
    finally:
        _parallel_slots.release()
    by_intent = {item.intent: item for item in results}
    profile_result = by_intent.get("profile")
    graph_result = by_intent.get("graph")
    failures = [
        {"intent": item.intent, "code": item.error.code, "message": item.error.message}
        for item in results
        if item.error is not None
    ]
    status = "completed" if all(item.status == "completed" for item in results) else "failed" if all(item.status == "failed" for item in results) else "partial"
    merged = {
        "message": "综合结果分别基于当前账号学习记录和所选课程的正式图谱生成；建议仅供参考，可自行调整。",
        "profile": profile_result.result if profile_result and profile_result.status != "failed" else None,
        "graph": graph_result.result if graph_result and graph_result.status != "failed" else None,
        "errors": failures,
    }
    return {"status": status, "results": [item.model_dump() for item in results], "merged": merged}
