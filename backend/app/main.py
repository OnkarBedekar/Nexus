"""FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .redis_client import close_redis, get_redis
from .routers import agent, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the Redis connection so failures surface at startup, not at first request.
    try:
        await get_redis().ping()
        log.info("Redis connection healthy")
    except Exception as exc:
        log.warning("Redis ping failed at startup: %s", exc)
    yield
    await close_redis()


settings = get_settings()
app = FastAPI(title="Nexus Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|172\.\d+\.\d+\.\d+):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(agent.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "app": "nexus-backend",
        "version": "0.1.0",
        "mock_tinyfish": str(settings.mock_tinyfish),
    }
