"""RevWatch FastAPI application entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key
from api.deps import get_db_path
from api.routes import businesses, markets, rankings, signals, validation
from api.schemas import HealthOut
from db.repository import RevWatchRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = get_db_path()
    repo = RevWatchRepository(db_path)
    app.state.repo = repo
    yield
    repo.close()


app = FastAPI(
    title="RevWatch API",
    description=(
        "Autonomous business revenue intelligence. "
        "Every estimate includes a confidence interval and score — never a bare number. "
        "Set REVWATCH_API_KEY to enable the X-API-Key stub middleware."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REVWATCH_CORS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(businesses.router)
app.include_router(markets.router)
app.include_router(rankings.router)
app.include_router(validation.router)
app.include_router(signals.router)


@app.get("/health", response_model=HealthOut, tags=["health"])
def health(_key: str | None = Depends(require_api_key)) -> HealthOut:
    repo: RevWatchRepository = app.state.repo
    return HealthOut(
        status="ok",
        businesses=repo.count_businesses(),
        promoted_model=repo.get_promoted_model_version(),
    )
