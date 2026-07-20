"""FastAPI dependencies — shared repository + model version resolution."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Request

from db.repository import RevWatchRepository


def get_db_path() -> Path:
    return Path(os.environ.get("REVWATCH_DB", "data/revwatch.duckdb"))


@lru_cache(maxsize=1)
def _repo_singleton(db_path: str) -> RevWatchRepository:
    return RevWatchRepository(db_path)


def get_repo(request: Request) -> RevWatchRepository:
    """Prefer app-state repo (set at startup); fall back to singleton."""
    repo = getattr(request.app.state, "repo", None)
    if repo is not None:
        return repo
    return _repo_singleton(str(get_db_path()))


def resolve_model_version(repo: RevWatchRepository, model_version: str | None = None) -> str:
    if model_version:
        return model_version
    promoted = repo.get_promoted_model_version()
    if promoted:
        return promoted
    row = repo.conn.execute(
        "SELECT model_version FROM revenue_estimates ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row:
        return str(row[0])
    return "v0.1.0"


RepoDep = Depends(get_repo)
