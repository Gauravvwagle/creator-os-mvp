from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_PAGE = Path(__file__).resolve().parent.parent / "static" / "dashboard.html"


@router.get("/dashboard", include_in_schema=False)
def dashboard():
    """A single local page for reviewing niches and candidate evidence."""
    return FileResponse(_PAGE, media_type="text/html")
