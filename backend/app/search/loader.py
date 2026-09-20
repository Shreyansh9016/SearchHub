from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document
from app.search.engine import SearchEngine


def build_engine(db: Session) -> SearchEngine:
    engine = SearchEngine()
    for doc in db.scalars(select(Document).where(Document.status == "indexed")):
        engine.add_document(
            doc.id, doc.title, doc.body,
            tags=[t.name for t in doc.tags],
            author_id=doc.author_id,
            created_at=doc.created_at,
        )
    return engine
