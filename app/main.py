from fastapi import FastAPI
from .database import Base, engine, settings
from .api.routes import router
from .api.ai_routes import router as ai_router
from .api.research_routes import router as research_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first niche research and opportunity scoring for CreatorOS.",
)

app.include_router(router, prefix="/api/v1", tags=["CreatorOS"])
app.include_router(ai_router, prefix="/api/v1", tags=["AI"])
app.include_router(research_router, prefix="/api/v1", tags=["Research"])

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "application": settings.app_name, "version": "0.1.0"}