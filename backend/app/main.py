import time
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import embed, latency
from app.config import settings
from app.db import connect, init_schema
from app.metrics import router as metrics_router
from app.ratelimit import limiter
from app.recommend import recommend, recommend_vibe
from app.schemas import Item, Recommendation
from app.share import router as share_router
from app.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    # Load the embedding model before serving (~12s, mostly importing torch), so no request
    # has to wait for it. Loading in a background thread made the first request slower.
    embed.model()
    yield


app = FastAPI(title="WIN API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(users_router)
app.include_router(metrics_router)
app.include_router(share_router)


class RecommendRequest(BaseModel):
    liked: list[int] = Field(min_length=1, max_length=50)
    disliked: list[int] = Field(default=[], max_length=200)
    categories: list[str] = []
    k: int = Field(default=10, ge=1, le=50)
    use_llm: bool = True  # LLM re-ranking; falls back to the engine if off or failing


class VibeRequest(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    disliked: list[int] = Field(default=[], max_length=200)
    categories: list[str] = []
    k: int = Field(default=10, ge=1, le=50)
    use_llm: bool = True


@app.get("/health")
def health() -> dict:
    with connect() as conn:
        rows = conn.execute(
            "SELECT category, count(*), count(embedding) FROM items GROUP BY category"
        ).fetchall()
    return {"status": "ok", "items": {c: {"total": n, "embedded": e} for c, n, e in rows}}


@app.get("/popular", response_model=dict[str, list[Item]])
def popular(per_category: int = Query(12, ge=1, le=40)):
    """Most popular items with a cover, per category: fills the home page before a search."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, title, category, year, image_url, genres FROM (
                   SELECT *, row_number() OVER (PARTITION BY category ORDER BY popularity DESC) AS r
                   FROM items WHERE image_url IS NOT NULL AND embedding IS NOT NULL) t
               WHERE r <= %s ORDER BY category, r""",
            (per_category,),
        ).fetchall()
    out: dict[str, list[Item]] = {}
    keys = ("id", "title", "category", "year", "image_url", "genres")
    for r in rows:
        out.setdefault(r[2], []).append(Item(**dict(zip(keys, r, strict=True))))
    return out


@app.get("/search", response_model=list[Item])
def search(q: str = Query(min_length=1, max_length=100), limit: int = Query(8, le=20)):
    """Autocomplete across all categories: prefix matches first, then fuzzy, then popular."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, title, category, year, image_url, genres FROM items
               WHERE title ILIKE '%%' || %(q)s || '%%' OR title %% %(q)s
               ORDER BY title ILIKE %(q)s || '%%' DESC, similarity(title, %(q)s) DESC,
                        popularity DESC
               LIMIT %(limit)s""",
            {"q": q, "limit": limit},
        ).fetchall()
    keys = ("id", "title", "category", "year", "image_url", "genres")
    return [Item(**dict(zip(keys, r, strict=True))) for r in rows]


UserHeader = Annotated[UUID | None, Header(alias="X-User-Id")]


def guard(request: Request, user_id: UUID | None, wants_llm: bool) -> bool:
    """Cost protection for the recommend endpoints. Rate-limits per user (or IP when
    anonymous) and returns whether the paid LLM step may run: only for a known user in the
    "llm" arm of the A/B test, so anonymous or engine-arm callers can never trigger it."""
    key = f"user:{user_id}" if user_id else f"ip:{request.client.host if request.client else '?'}"
    ok, retry = limiter.allow(key, settings.rate_limit_per_minute)
    if not ok:
        raise HTTPException(429, f"Too many requests. Try again in {retry} seconds.",
                            headers={"Retry-After": str(retry)})
    if not (wants_llm and user_id):
        return False
    with connect() as conn:
        row = conn.execute("SELECT arm FROM users WHERE id = %s", (user_id,)).fetchone()
    return bool(row) and row[0] == "llm"


def timed(mode: str, recs: list[dict], start: float) -> None:
    source = "ai" if any(r.get("ai") for r in recs) else "engine"
    latency.record(f"{mode}/{source}", (time.perf_counter() - start) * 1000)


@app.post("/recommend", response_model=list[Recommendation])
def recommend_endpoint(req: RecommendRequest, request: Request, user_id: UserHeader = None):
    llm = guard(request, user_id, req.use_llm)
    start = time.perf_counter()
    recs = recommend(req.liked, req.disliked, req.categories, req.k, use_llm=llm)
    timed("titles", recs, start)
    return recs


@app.post("/recommend/vibe", response_model=list[Recommendation])
def recommend_vibe_endpoint(req: VibeRequest, request: Request, user_id: UserHeader = None):
    """Recommend from a mood description, e.g. "cozy and a bit sad for a rainy night"."""
    llm = guard(request, user_id, req.use_llm)
    start = time.perf_counter()
    recs = recommend_vibe(req.text, req.disliked, req.categories, req.k, llm)
    timed("vibe", recs, start)
    return recs
