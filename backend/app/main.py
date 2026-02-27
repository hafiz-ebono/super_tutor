import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("super_tutor.main")

# Module-level settings used by CORS middleware (evaluated before lifespan runs)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Super Tutor API starting — provider=%s model=%s origins=%s",
        settings.agent_provider,
        settings.agent_model,
        settings.allowed_origins,
    )
    yield
    logger.info("Super Tutor API shutting down")


from app.routers import sessions

app = FastAPI(
    title="Super Tutor API",
    description="AI-powered study session generation from URLs",
    version="1.0.0",
    lifespan=lifespan,
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
