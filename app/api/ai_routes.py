import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai.ollama_client import MODEL_NAME, generate_response

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)


class GenerateResponse(BaseModel):
    model: str
    response: str
    note: str


@router.post("/ai/generate", response_model=GenerateResponse)
async def ai_generate(payload: GenerateRequest):
    try:
        text = await generate_response(payload.prompt)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Ollama took too long to respond. Try a shorter prompt or close other heavy apps.",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return GenerateResponse(
        model=MODEL_NAME,
        response=text,
        note="AI-generated draft. Not verified evidence. Human review required.",
    )