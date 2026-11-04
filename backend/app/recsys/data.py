"""MovieLens download, loading and train/test split.

MovieLens (GroupLens Research) gives us real user ratings, which is what we need
to measure recommendation quality offline. links.csv maps each movie to its TMDB id.
"""

import io
import zipfile
from pathlib import Path

import httpx
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
ML_DIR = DATA_DIR / "raw" / "ml-latest-small"

LIKE_THRESHOLD = 4.0  # a rating >= 4 counts as "liked"


def download() -> Path:
    if (ML_DIR / "ratings.csv").exists():
        return ML_DIR
    resp = httpx.get(URL, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    zipfile.ZipFile(io.BytesIO(resp.content)).extractall(ML_DIR.parent)
    return ML_DIR


TMDB_CACHE = DATA_DIR / "processed" / "ml_tmdb.parquet"


def tmdb_text(tmdb_ids: list[int]) -> pd.DataFrame:
    """Overview + keywords from TMDB for each movie (one call per movie, cached on disk)."""
    if TMDB_CACHE.exists():
        return pd.read_parquet(TMDB_CACHE)
    from concurrent.futures import ThreadPoolExecutor

    from app.ingest.tmdb import _client, _details

    with _client() as client, ThreadPoolExecutor(8) as pool:
        details = list(pool.map(lambda i: _details(client, "movie", i), tmdb_ids))
    rows = [{
        "tmdb_id": i,
        "overview": d.get("overview") or "",
        "keywords": [k["name"].lower() for k in d.get("keywords", {}).get("keywords", [])][:12],
    } for i, d in zip(tmdb_ids, details, strict=True)]
    df = pd.DataFrame(rows)
    TMDB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(TMDB_CACHE)
    return df


def load(tmdb: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (ratings, movies). movies has a genres list, user tags and tmdb_id.
    With tmdb=True it also gets TMDB `overview` and `keywords` (needs TMDB_API_KEY once)."""
    d = download()
    ratings = pd.read_csv(d / "ratings.csv")
    movies = pd.read_csv(d / "movies.csv")
    links = pd.read_csv(d / "links.csv")
    tags = pd.read_csv(d / "tags.csv")

    movies["year"] = movies["title"].str.extract(r"\((\d{4})\)\s*$")[0].astype("Int64")
    movies["genres"] = movies["genres"].replace("(no genres listed)", "").str.split("|")
    movies["genres"] = movies["genres"].apply(lambda g: [x for x in g if x])

    tags["tag"] = tags["tag"].astype(str).str.lower().str.strip()
    movie_tags = tags.groupby("movieId")["tag"].apply(lambda t: sorted(set(t)))
    movies["tags"] = movies["movieId"].map(movie_tags).apply(
        lambda t: t if isinstance(t, list) else []
    )
    movies = movies.merge(links[["movieId", "tmdbId"]], on="movieId", how="left")
    movies = movies.rename(columns={"tmdbId": "tmdb_id"})
    if tmdb:
        ids = movies["tmdb_id"].dropna().astype(int).unique().tolist()
        extra = tmdb_text(ids)
        movies["tmdb_id"] = movies["tmdb_id"].astype("Int64")
        movies = movies.merge(extra.astype({"tmdb_id": "Int64"}), on="tmdb_id", how="left")
        movies["overview"] = movies["overview"].fillna("")
        movies["keywords"] = movies["keywords"].apply(
            lambda k: list(k) if isinstance(k, (list, tuple)) or hasattr(k, "tolist") else []
        )
    return ratings, movies


def split(ratings: pd.DataFrame, test_frac: float = 0.2, min_likes: int = 5):
    """Time-based split per user.

    For each user with at least `min_likes` liked movies, the most recent
    `test_frac` of their ratings go to test. The model only sees the past and must
    predict which movies the user went on to like.
    Returns (train, test) where test only keeps liked items.
    """
    ratings = ratings.sort_values(["userId", "timestamp"])
    likes = ratings[ratings["rating"] >= LIKE_THRESHOLD].groupby("userId").size()
    eligible = likes[likes >= min_likes].index

    rank = ratings.groupby("userId").cumcount(ascending=False)  # 0 = newest
    n = ratings.groupby("userId")["movieId"].transform("size")
    is_test = (rank < (n * test_frac).round().clip(lower=1)) & ratings["userId"].isin(eligible)

    train = ratings[~is_test]
    test = ratings[is_test & (ratings["rating"] >= LIKE_THRESHOLD)]
    test = test[test["userId"].isin(train["userId"])]
    return train.reset_index(drop=True), test.reset_index(drop=True)
