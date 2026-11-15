from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from ..research.fetcher import FetchError, fetch_page_text
from ..research.verify import quote_in_text

router = APIRouter()


class VerifyQuoteRequest(BaseModel):
    url: HttpUrl
    excerpt: str = Field(min_length=10, max_length=3000)


class VerifyQuoteResponse(BaseModel):
    found: bool
    final_url: str
    page_title: str
    checked_at: datetime
    note: str


@router.post("/research/verify-quote", response_model=VerifyQuoteResponse)
async def verify_quote(payload: VerifyQuoteRequest):
    try:
        page = await fetch_page_text(str(payload.url))
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    found = quote_in_text(payload.excerpt, page["text"])
    note = (
        "The excerpt appears in the page text. A human must still judge whether it supports the claim."
        if found
        else "The excerpt was NOT found in the page text. It may be misquoted, or the page may load its content with JavaScript."
    )
    return VerifyQuoteResponse(
        found=found,
        final_url=page["final_url"],
        page_title=page["title"],
        checked_at=datetime.now(timezone.utc),
        note=note,
    )