"""Run every candidate model through the same evaluation and save the results table.

    uv run python -m app.recsys.compare
"""

import pandas as pd

from app.recsys.data import DATA_DIR, load, split
from app.recsys.evaluate import evaluate
from app.recsys.models import ALS, EmbeddingContent, Popularity, TfidfContent, WithPopularity

RESULTS = DATA_DIR.parent / "notebooks" / "results.csv"


def main() -> pd.DataFrame:
    ratings, movies = load()
    train, test = split(ratings)
    print(f"train={len(train):,} ratings  test={len(test):,} liked  users={test.userId.nunique()}")

    models = [
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
    rows = []
    for m in models:
        r = evaluate(m, train, test, movies)
        print({k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()})
        rows.append(r)

    df = pd.DataFrame(rows).sort_values("ndcg@10", ascending=False)
    RESULTS.parent.mkdir(exist_ok=True)
    df.to_csv(RESULTS, index=False)
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    main()
