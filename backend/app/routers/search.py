from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import SearchEvent, User
from app.realtime import manager, trending_message
from app.search.engine import EmptyQueryError, SearchEngine

router = APIRouter(prefix="/search", tags=["search"])


def get_engine(request: Request) -> SearchEngine:
    return request.app.state.search_engine


class HitOut(BaseModel):
    id: int
    title: str
    snippet: str
    score: float
    tags: list[str]
    author_id: int
    created_at: datetime


class SearchOut(BaseModel):
    query: str
    total: int
    page: int
    limit: int
    took_ms: float
    facets: dict[str, int]
    results: list[HitOut]


class SuggestOut(BaseModel):
    prefix: str
    suggestions: list[str]


def _log_event(db: Session, user_id: int, query: str, results_count: int, latency_ms: int) -> None:
    try:
        db.add(SearchEvent(user_id=user_id, query=query[:500], results_count=results_count, latency_ms=latency_ms))
        db.commit()
    except Exception:
        db.rollback()


@router.get("", response_model=SearchOut)
def search(
    background: BackgroundTasks,
    q: str = Query("", description="Search text, e.g. 'redis cache'"),
    tag: list[str] | None = Query(None, description="Repeat or comma-separate; a doc must have ALL tags"),
    author_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["relevance", "newest", "oldest"] = "relevance",
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    engine: SearchEngine = Depends(get_engine),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(400, "Query parameter 'q' must not be empty.")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "'date_from' must not be after 'date_to'.")
    tags = [t.strip() for value in (tag or []) for t in value.split(",") if t.strip()]

    try:
        result = engine.search(q, tags, author_id, date_from, date_to, sort, page, limit)
    except EmptyQueryError as exc:
        raise HTTPException(400, str(exc))

    _log_event(db, user.id, q, result.total, int(result.took_ms))
    if manager.connections:
        background.add_task(manager.broadcast, trending_message(db))
    return SearchOut(
        query=result.query, total=result.total, page=result.page, limit=result.limit,
        took_ms=result.took_ms, facets=result.facets,
        results=[HitOut(**vars(h)) for h in result.hits],
    )


@router.get("/suggest", response_model=SuggestOut)
def suggest(prefix: str = "", engine: SearchEngine = Depends(get_engine)):
    if not prefix.strip():
        raise HTTPException(400, "Query parameter 'prefix' must not be empty.")
    return SuggestOut(prefix=prefix, suggestions=engine.suggest(prefix, k=5))
