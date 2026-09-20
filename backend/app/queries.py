from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Bookmark, DocumentTag, SearchEvent, Tag


def top_tags_by_bookmarks(db: Session, days: int = 7, limit: int = 10):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(Tag.name, func.count().label("bookmark_count"))
        .select_from(Bookmark)
        .join(DocumentTag, DocumentTag.document_id == Bookmark.document_id)
        .join(Tag, Tag.id == DocumentTag.tag_id)
        .where(Bookmark.created_at >= cutoff)
        .group_by(Tag.id, Tag.name)
        .order_by(desc("bookmark_count"), Tag.name)
        .limit(limit)
    )
    return [(name, count) for name, count in db.execute(stmt).all()]


def trending_queries(db: Session, minutes: int = 60, limit: int = 10):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    lowered = func.lower(SearchEvent.query)
    stmt = (
        select(lowered, func.count().label("n"))
        .where(SearchEvent.created_at >= cutoff)
        .group_by(lowered)
        .order_by(func.count().desc(), lowered)
        .limit(limit)
    )
    return [(query, count) for query, count in db.execute(stmt).all()]
