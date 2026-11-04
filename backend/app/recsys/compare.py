"""Run every candidate model through the same evaluation and save the results table.

    uv run python -m app.recsys.compare           # Phase 1: MovieLens text only
    uv run python -m app.recsys.compare --tmdb    # with TMDB overviews + keywords
"""

import sys

import pandas as pd

from app.recsys.data import DATA_DIR, load, split
from app.recsys.evaluate import evaluate
from app.recsys.models import ALS, EmbeddingContent, Popularity, TfidfContent, WithPopularity

RESULTS = DATA_DIR.parent / "notebooks" / "results.csv"
RESULTS_TMDB = DATA_DIR.parent / "notebooks" / "results_tmdb.csv"


PHASE1_MODELS = [
    Popularity(),
    TfidfContent(),
    EmbeddingContent("all-MiniLM-L6-v2"),
    EmbeddingContent("all-mpnet-base-v2"),
    WithPopularity(TfidfContent(), 1.0),
    WithPopularity(EmbeddingContent("all-MiniLM-L6-v2"), 1.0),
    WithPopularity(EmbeddingContent("all-mpnet-base-v2"), 0.5),
    WithPopularity(EmbeddingContent("all-mpnet-base-v2"), 1.0),
    WithPopularity(EmbeddingContent("all-mpnet-base-v2"), 2.0),
    ALS(factors=32, regularization=0.05, alpha=10),
    ALS(factors=64, regularization=0.05, alpha=10),
    ALS(factors=128, regularization=0.1, alpha=20),
]
TMDB_MODELS = [
    Popularity(),
    TfidfContent(),
    EmbeddingContent("all-MiniLM-L6-v2"),
    WithPopularity(TfidfContent(), 1.0),
    WithPopularity(EmbeddingContent("all-MiniLM-L6-v2"), 1.0),
    ALS(factors=32, regularization=0.05, alpha=10),
]


def main(tmdb: bool = False) -> pd.DataFrame:
    """tmdb=False: the Phase 1 comparison (MovieLens genres + user tags only).
    tmdb=True: content models also get TMDB overviews + keywords, like items in the app."""
    ratings, movies = load(tmdb=tmdb)
    train, test = split(ratings)
    print(f"train={len(train):,} ratings  test={len(test):,} liked  users={test.userId.nunique()}")

    rows = []
    for m in TMDB_MODELS if tmdb else PHASE1_MODELS:
        r = evaluate(m, train, test, movies)
        print({k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()})
        rows.append(r)

    df = pd.DataFrame(rows).sort_values("ndcg@10", ascending=False)
    out = RESULTS_TMDB if tmdb else RESULTS
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    main(tmdb="--tmdb" in sys.argv)
