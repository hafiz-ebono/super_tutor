import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Export .env vars into os.environ before any tool/client constructors run

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.utils.logging import configure_logging
from app.config import get_settings
from app.dependencies import limiter, ACTIVE_TASKS

configure_logging()

logger = logging.getLogger("super_tutor.main")

# Module-level settings used by CORS middleware (evaluated before lifespan runs)
settings = get_settings()

# Rate limiter imported from dependencies.py — shared across all routers.


from agno.db.sqlite import SqliteDb

# Single shared SqliteDb instance for the entire process lifetime.
# Stored on app.state so routers access it via Depends(get_traces_db).
_traces_db = SqliteDb(
    db_file=settings.trace_db_path,
    id="super_tutor_traces",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Super Tutor API starting — provider=%s model=%s origins=%s",
        settings.agent_provider,
        settings.agent_model,
        settings.allowed_origins,
    )
    app.state.traces_db = _traces_db
    # Clean up sessions that were left pending by a previous crash
    from app.utils.session_status import mark_stale_sessions_failed
    mark_stale_sessions_failed()
    yield
    # Graceful shutdown: wait up to 60s for in-flight background tasks to finish.
    # Any task still running after the timeout is cancelled so the process can exit cleanly.
    if ACTIVE_TASKS:
        logger.info("Shutdown: waiting for %d active task(s) to complete...", len(ACTIVE_TASKS))
        _, pending = await asyncio.wait(ACTIVE_TASKS, timeout=60)
        for task in pending:
            logger.warning("Shutdown: cancelling task that did not finish in time — %s", task.get_name())
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    logger.info("Super Tutor API shutting down")


from app.routers import sessions
from app.routers import chat
from app.routers import upload as upload_router
from app.routers import tutor as tutor_router

app = FastAPI(
    title="Super Tutor API",
    description="AI-powered study session generation from URLs",
    version="1.0.0",
    lifespan=lifespan,
)

# Attach limiter to app state so @limiter.limit decorators can find it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_control_plane_origins = ["https://os.agno.com", "https://app.agno.com", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*settings.allowed_origins, *_control_plane_origins],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(upload_router.router, prefix="/sessions", tags=["sessions"])
app.include_router(tutor_router.router, prefix="/tutor", tags=["tutor"])


@app.get("/health")
async def health():
    return {"status": "ok"}


from agno.os import AgentOS
from app.agents.notes_agent import build_notes_agent
from app.agents.chat_agent import build_chat_agent
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.agents.research_agent import build_research_agent
from app.workflows.session_workflow import build_session_workflow


def _wrap_with_agentos(fastapi_app: FastAPI) -> FastAPI:
    """
    Wrap the FastAPI app with AgentOS for local SQLite tracing.
    Called once at module load after all routes/middleware are registered.
    Returns the merged app (drop-in replacement — uvicorn target unchanged).

    INT-02 compliance note: Tracing for all five agent types is achieved via
    db= injection at call time in routers (plan 06-03), NOT via the agents=[]
    registration list. Per agno docs (Pitfall 5), agents called directly via
    agent.run() are traced as long as db= is set on the Agent instance and
    tracing=True is set on the AgentOS instance. All five agents are registered
    in agents=[] to provide full visibility in the AgentOS playground UI —
    they do NOT replace per-request agent instances created inside routers.

    The session workflow is registered in workflows=[] so it appears in the
    AgentOS playground. This representative instance (all steps enabled) is
    for UI visibility only — per-request instances are created inside routers.

    TutorTeam (Phase 14+) is now registered via teams=[placeholder_team] so it
    is visible in the AgentOS control plane playground UI alongside all other
    agents. Per-request Team instances continue to be created in the tutor
    router at request time with db= injection for tracing.
    """
    from app.agents.tutor_team import build_tutor_team
    traces_db = _traces_db  # reuse the single shared instance
    session_workflow = build_session_workflow(
        session_id="playground",
        session_db=traces_db,  # use traces_db so this placeholder appears in AgentOS "Workflows"
        session_type="topic",
        generate_flashcards=True,
        generate_quiz=True,
    )
    placeholder_team = build_tutor_team(
        source_content="[AgentOS placeholder — not a real session]",
        notes="",
        tutoring_type="micro_learning",
        db=traces_db,
        session_topic="[placeholder]",
    )
    agent_os = AgentOS(
        agents=[
            build_notes_agent("micro_learning", db=traces_db),
            build_chat_agent("micro_learning", notes="", db=traces_db),
            build_flashcard_agent("micro_learning", db=traces_db),
            build_quiz_agent("micro_learning", db=traces_db),
            build_research_agent(db=traces_db),
        ],
        workflows=[session_workflow],
        teams=[placeholder_team],
        base_app=fastapi_app,
        db=traces_db,
        tracing=True,
        on_route_conflict="preserve_base_app",
        id="super_tutor_agentos",
    )
    return agent_os.get_app()


app = _wrap_with_agentos(app)

# Start with: uvicorn app.main:app --reload --port 8000  (from backend/ directory)
