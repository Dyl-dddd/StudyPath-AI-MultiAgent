from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.contracts import AgentParallelInput, AgentRunInput
from app.agents.orchestrator import run_agent, run_parallel_readonly
from app.agents.providers import AgentHarnessAdapter, DeepSeekCompatibleProvider
from app.core.db import get_db
from app.core.security import current_user
from app.models import User

router = APIRouter(prefix="/agents", tags=["learning-agents"])


@router.get("/health")
def agent_health(user: User = Depends(current_user)):
    del user  # Authentication is required, but provider credentials are never returned.
    model = DeepSeekCompatibleProvider.status()
    harness = AgentHarnessAdapter.status()
    return {
        "status": "available",
        "orchestrator": "application",
        "roles": ["user_profile", "mistake_transfer", "course_rag", "general_tutor", "knowledge_graph"],
        "providers": {
            "openai_compatible": {"status": model.status, "model_configured": model.model_configured},
            "agentharness": {"status": harness.status, "credential_configured": harness.model_configured, "execution_enabled": False},
        },
    }


@router.post("/run")
async def run(payload: AgentRunInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await run_agent(db, user, payload)


@router.post("/run/parallel")
async def run_parallel(payload: AgentParallelInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await run_parallel_readonly(db, user, payload, payload.intents)
