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
from app.routers import chat

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
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}


from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from app.agents.notes_agent import build_notes_agent
from app.agents.chat_agent import build_chat_agent
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.agents.research_agent import build_research_agent


def _wrap_with_agentos(fastapi_app: FastAPI) -> FastAPI:
    """
    Wrap the FastAPI app with AgentOS for local SQLite tracing.
    Called once at module load after all routes/middleware are registered.
    Returns the merged app (drop-in replacement — uvicorn target unchanged).

    INT-02 compliance note: Tracing for all five agent types is achieved via
    db= injection at call time in routers (plan 06-03), NOT via the agents=[]
    registration list. Per agno docs (Pitfall 5), agents called directly via
    agent.run() are traced as long as db= is set on the Agent instance and
    tracing=True is set on the AgentOS instance. One representative agent is
    registered in agents=[] solely to satisfy AgentOS startup requirements —
    it does NOT replace per-request agent instances created inside routers.
    """
    traces_db = SqliteDb(
        db_file=settings.trace_db_path,
        id="super_tutor_traces",
    )
    agent_os = AgentOS(
        agents=[
            build_notes_agent("micro_learning", db=traces_db),
        ],
        base_app=fastapi_app,
        db=traces_db,
        tracing=True,
        on_route_conflict="preserve_base_app",
    )
    return agent_os.get_app()


app = _wrap_with_agentos(app)

# Start with: uvicorn app.main:app --reload --port 8000  (from backend/ directory)
