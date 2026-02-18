from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import sessions

settings = get_settings()

app = FastAPI(
    title="Super Tutor API",
    description="AI-powered study session generation from URLs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])


@app.get("/health")
async def health():
    return {"status": "ok"}

# Start with: uvicorn app.main:app --reload --port 8000  (from backend/ directory)
