from fastapi import FastAPI
from .database import Base, engine, settings
from .api.routes import router
from .api.ai_routes import router as ai_router
from .api.research_routes import router as research_router
from .api.candidate_routes import router as candidate_router
from .api.verify_routes import router as verify_router
from .api.dashboard_routes import router as dashboard_router
from .api.suggest_routes import router as suggest_router
from .api.content_routes import router as content_router
from .migrations import add_missing_columns

Base.metadata.create_all(bind=engine)
add_missing_columns(engine)  # upgrades an older creatoros.db without losing data

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first niche research and opportunity scoring for CreatorOS.",
)

app.include_router(router, prefix="/api/v1", tags=["CreatorOS"])
app.include_router(ai_router, prefix="/api/v1", tags=["AI"])
app.include_router(research_router, prefix="/api/v1", tags=["Research"])
app.include_router(candidate_router, prefix="/api/v1", tags=["Review"])
app.include_router(verify_router, prefix="/api/v1", tags=["Research"])
app.include_router(suggest_router, prefix="/api/v1", tags=["Research"])
app.include_router(content_router, prefix="/api/v1", tags=["Content"])
app.include_router(dashboard_router)

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "application": settings.app_name, "version": "0.1.0"}