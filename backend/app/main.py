from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.db import connect, init_schema
from app.recommend import recommend


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    yield


app = FastAPI(title="WIN API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"])


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


class RecommendRequest(BaseModel):
    liked: list[int] = Field(min_length=1, max_length=50)
    disliked: list[int] = Field(default=[], max_length=200)
    categories: list[str] = []
    k: int = Field(default=10, ge=1, le=50)


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
    return recommend(req.liked, req.disliked, req.categories, req.k)
