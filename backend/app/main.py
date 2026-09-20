import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.db import SessionLocal
from app.deps import get_current_user
from app.routers import analytics, auth, documents, search, ws
from app.search.engine import SearchEngine
from app.search.loader import build_engine

log = logging.getLogger("searchhub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with SessionLocal() as db:
            app.state.search_engine = build_engine(db)
        log.info("Indexed %d documents", app.state.search_engine.index.n_docs)
    except Exception:
        log.exception("Could not build search index; starting empty")
        app.state.search_engine = SearchEngine()
    yield


app = FastAPI(title="SearchHub", version="0.1.0", lifespan=lifespan)
protected = [Depends(get_current_user)]
app.include_router(auth.router)
app.include_router(search.router, dependencies=protected)
app.include_router(documents.router, dependencies=protected)
app.include_router(analytics.router, dependencies=protected)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"status": "ok"}
