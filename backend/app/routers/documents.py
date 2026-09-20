from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import Bookmark, Document, Tag, User
from app.queries import top_tags_by_bookmarks
from app.routers.search import get_engine
from app.search.engine import SearchEngine

router = APIRouter(tags=["documents"])


class RelatedOut(BaseModel):
    id: int
    title: str
    tags: list[str]


class DocumentOut(BaseModel):
    id: int
    title: str
    body: str
    tags: list[str]
    author: str
    status: str
    created_at: datetime
    updated_at: datetime
    bookmarked: bool
    related: list[RelatedOut]


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    tags: list[str] = []


class DocumentSaved(BaseModel):
    id: int
    title: str
    status: str
    tags: list[str]


class BookmarkState(BaseModel):
    document_id: int
    bookmarked: bool


class TagBookmarks(BaseModel):
    name: str
    bookmarks: int


def load_document(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found.")
    return doc


def resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    wanted = list(dict.fromkeys(n.strip().lower() for n in names if n.strip()))
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.name.in_(wanted)))} if wanted else {}
    return [existing.get(name) or Tag(name=name) for name in wanted]


def sync_index(engine: SearchEngine, doc: Document) -> None:
    engine.add_document(doc.id, doc.title, doc.body, [t.name for t in doc.tags], doc.author_id, doc.created_at)


def saved(doc: Document) -> DocumentSaved:
    return DocumentSaved(id=doc.id, title=doc.title, status=doc.status, tags=sorted(t.name for t in doc.tags))


@router.post("/documents", response_model=DocumentSaved, status_code=201)
def create_document(
    body: DocumentIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    engine: SearchEngine = Depends(get_engine),
):
    doc = Document(
        title=body.title.strip(), body=body.body, author_id=admin.id, status="indexed",
        tags=resolve_tags(db, body.tags),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    sync_index(engine, doc)
    return saved(doc)


@router.put("/documents/{doc_id}", response_model=DocumentSaved)
def update_document(
    doc_id: int,
    body: DocumentIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    engine: SearchEngine = Depends(get_engine),
):
    doc = load_document(db, doc_id)
    doc.title = body.title.strip()
    doc.body = body.body
    doc.tags = resolve_tags(db, body.tags)
    doc.status = "indexed"
    db.commit()
    db.refresh(doc)
    sync_index(engine, doc)
    return saved(doc)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    engine: SearchEngine = Depends(get_engine),
):
    doc = load_document(db, doc_id)
    db.execute(delete(Bookmark).where(Bookmark.document_id == doc_id))
    db.delete(doc)
    db.commit()
    engine.remove_document(doc_id)
    return Response(status_code=204)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    engine: SearchEngine = Depends(get_engine),
):
    doc = load_document(db, doc_id)
    bookmarked = db.get(Bookmark, (user.id, doc_id)) is not None
    related = [RelatedOut(id=h.id, title=h.title, tags=h.tags) for h in engine.related(doc_id)]
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        body=doc.body,
        tags=sorted(t.name for t in doc.tags),
        author=doc.author.name,
        status=doc.status,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        bookmarked=bookmarked,
        related=related,
    )


@router.put("/documents/{doc_id}/bookmark", response_model=BookmarkState)
def add_bookmark(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    load_document(db, doc_id)
    if db.get(Bookmark, (user.id, doc_id)) is None:
        db.add(Bookmark(user_id=user.id, document_id=doc_id))
        db.commit()
    return BookmarkState(document_id=doc_id, bookmarked=True)


@router.delete("/documents/{doc_id}/bookmark", response_model=BookmarkState)
def remove_bookmark(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    load_document(db, doc_id)
    existing = db.get(Bookmark, (user.id, doc_id))
    if existing is not None:
        db.delete(existing)
        db.commit()
    return BookmarkState(document_id=doc_id, bookmarked=False)


@router.get("/tags/top-bookmarked", response_model=list[TagBookmarks])
def top_bookmarked_tags(days: int = 7, db: Session = Depends(get_db)):
    return [TagBookmarks(name=n, bookmarks=c) for n, c in top_tags_by_bookmarks(db, days=days)]
