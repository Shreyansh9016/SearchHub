from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SearchEvent
from app.queries import trending_queries
from app.search.index import as_utc

WINDOW_MINUTES = 60
CHART_MINUTES = 30

router = APIRouter(prefix="/analytics", tags=["analytics"])


class QueryCount(BaseModel):
    query: str
    count: int


class MinuteCount(BaseModel):
    minute: datetime
    count: int


class SummaryOut(BaseModel):
    total_searches: int
    zero_result_searches: int
    zero_result_rate: float
    top_queries: list[QueryCount]
    per_minute: list[MinuteCount]


@router.get("/summary", response_model=SummaryOut)
def summary(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    in_window = SearchEvent.created_at >= cutoff

    total, zero = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(case((SearchEvent.results_count == 0, 1), else_=0)), 0),
        ).where(in_window)
    ).one()

    top = trending_queries(db, WINDOW_MINUTES, 10)
    minutes_to_show = CHART_MINUTES
    end_minute = now.replace(second=0, microsecond=0)
    buckets = {end_minute - timedelta(minutes=i): 0 for i in range(minutes_to_show)}
    recent = db.scalars(
        select(SearchEvent.created_at).where(SearchEvent.created_at >= end_minute - timedelta(minutes=minutes_to_show - 1))
    ).all()
    for created in recent:
        key = as_utc(created).replace(second=0, microsecond=0)
        if key in buckets:
            buckets[key] += 1

    return SummaryOut(
        total_searches=total,
        zero_result_searches=zero,
        zero_result_rate=round(zero / total, 4) if total else 0.0,
        top_queries=[QueryCount(query=q, count=n) for q, n in top],
        per_minute=[MinuteCount(minute=m, count=buckets[m]) for m in sorted(buckets)],
    )
