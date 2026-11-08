from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agents.research_planner import build_planning_prompt
from ..ai.ollama_client import MODEL_NAME, generate_response

router = APIRouter()

Criterion = Literal[
    "audience_demand",
    "monetization_potential",
    "affiliate_opportunities",
    "competition_accessibility",
    "production_feasibility",
    "long_term_demand",
    "creator_capability",
]


class ResearchPlanRequest(BaseModel):
    niche_name: str = Field(..., min_length=3, max_length=300)
    criterion: Criterion


class ResearchPlanResponse(BaseModel):
    niche_name: str
    criterion: str
    model: str
    plan: str
    status: str
    note: str


@router.post("/research/plan", response_model=ResearchPlanResponse)
async def research_plan(payload: ResearchPlanRequest):
    prompt = build_planning_prompt(payload.niche_name, payload.criterion)
    try:
        text = await generate_response(prompt)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama took too long to respond.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ResearchPlanResponse(
        niche_name=payload.niche_name,
        criterion=payload.criterion,
        model=MODEL_NAME,
        plan=text,
        status="ai_draft",
        note="AI-generated research plan. Contains no verified evidence. Human review required.",
    )