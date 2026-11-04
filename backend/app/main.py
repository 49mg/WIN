from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import embed
from app.config import settings
from app.db import connect, init_schema
from app.recommend import recommend, recommend_vibe
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


class Item(BaseModel):
    id: int
    title: str
    category: str
    year: int | None
    image_url: str | None
    genres: list[str]


class Recommendation(Item):
    description: str | None
    creators: list[str]
    match: int
    reason: str
    ai: bool  # True when the LLM picked/ordered this item and wrote the reason


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


@app.post("/recommend", response_model=list[Recommendation])
def recommend_endpoint(req: RecommendRequest):
    return recommend(req.liked, req.disliked, req.categories, req.k, use_llm=req.use_llm)


@app.post("/recommend/vibe", response_model=list[Recommendation])
def recommend_vibe_endpoint(req: VibeRequest):
    """Recommend from a mood description, e.g. "cozy and a bit sad for a rainy night"."""
    return recommend_vibe(req.text, req.disliked, req.categories, req.k, req.use_llm)
