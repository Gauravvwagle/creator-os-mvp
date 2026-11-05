from fastapi import FastAPI
from .database import Base, engine, settings
from .api.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first niche research and opportunity scoring for CreatorOS.",
)

app.include_router(router, prefix="/api/v1", tags=["CreatorOS"])


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "application": settings.app_name, "version": "0.1.0"}
