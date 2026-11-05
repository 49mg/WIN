"""Does keyword + vector retrieval ("hybrid search") find more of the right items? (WIN-34)

    uv run python -m app.recsys.hybrid_eval

Same setup as llm_eval (close to real WIN use): each test user gives their last 5 liked
movies; score = similarity to the closest liked item + w * popularity; we predict what they
liked next. Retrieval quality is measured as recall at 30 and 100 (how many of the right
movies are in the candidate pool the app would pass on), plus ndcg@10 of the final top 10.

Rankings compared:
  vector     MiniLM embeddings of title + genres + tags + TMDB overview (the current engine)
  keyword    TF-IDF over the same text (what PostgreSQL full-text search approximates)
  hybrid     Reciprocal Rank Fusion of the two: sum of 1 / (60 + rank) in each list
"""

import numpy as np
import pandas as pd

from app.recsys.data import DATA_DIR, LIKE_THRESHOLD, load, split
from app.recsys.models import EmbeddingContent, TfidfContent

N_LIKED, RRF_K = 5, 60
RESULTS = DATA_DIR.parent / "notebooks" / "results_hybrid.csv"


def ranks(scores: np.ndarray) -> np.ndarray:
    """rank[i] = position of item i when sorted by score, best = 0."""
    order = np.argsort(-scores)
    r = np.empty_like(order)
    r[order] = np.arange(len(order))
    return r


def recall_at(order: np.ndarray, relevant: set, n: int) -> float:
    return len(relevant & set(order[:n].tolist())) / len(relevant)


def ndcg_at_10(order: np.ndarray, relevant: set) -> float:
    disc = 1 / np.log2(np.arange(2, 12))
    hits = np.array([i in relevant for i in order[:10]])
    return float((hits * disc).sum() / disc[: min(len(relevant), 10)].sum())


def main() -> pd.DataFrame:
    ratings, movies = load(tmdb=True)
    train, test = split(ratings)
    col = pd.Series(np.arange(len(movies)), index=movies["movieId"])
    liked_train = train[train["rating"] >= LIKE_THRESHOLD]
    pop = np.log1p(np.bincount(col[liked_train["movieId"]], minlength=len(movies)))
    pop = pop / pop.max()

    E = EmbeddingContent("all-MiniLM-L6-v2").item_vectors(movies)
    T = TfidfContent().item_vectors(movies).tocsr()

    # Popularity weight changes results a lot, so every ranking is tried at the same weights.
    configs = {}
    for w in (0.3, 0.5):
        configs[f"vector + {w} pop"] = f"vector{w}"
        configs[f"keyword + {w} pop"] = f"keyword{w}"
        configs[f"hybrid RRF + {w} pop"] = f"hybrid{w}"
    rows = []
    users = [u for u in test["userId"].unique()
             if (liked_train["userId"] == u).sum() >= N_LIKED]
    for u in users:
        hist = train[train.userId == u]
        seen = col[hist["movieId"]].to_numpy()
        liked = col[liked_train.loc[liked_train.userId == u]
                    .sort_values("timestamp")["movieId"].iloc[-N_LIKED:]].to_numpy()
        relevant = set(col[test.loc[test.userId == u, "movieId"]].tolist())

        vec = (E @ E[liked].T).max(axis=1)
        kw = (T @ T[liked].T).toarray().max(axis=1)
        scored = {}
        for w in (0.3, 0.5):
            scored[f"vector{w}"] = vec + w * pop
            scored[f"keyword{w}"] = kw + w * pop
            r_vec, r_kw = ranks(scored[f"vector{w}"]), ranks(scored[f"keyword{w}"])
            scored[f"hybrid{w}"] = 1 / (RRF_K + r_vec) + 1 / (RRF_K + r_kw)

        row = {"user": u}
        for name, key in configs.items():
            s = scored[key].astype(float).copy()
            s[seen] = -np.inf
            order = np.argsort(-s)
            row[f"{name}|recall@30"] = recall_at(order, relevant, 30)
            row[f"{name}|recall@100"] = recall_at(order, relevant, 100)
            row[f"{name}|ndcg@10"] = ndcg_at_10(order, relevant)
        rows.append(row)

    per_user = pd.DataFrame(rows)
    summary = pd.DataFrame([{
        "ranking": name,
        **{m: per_user[f"{name}|{m}"].mean() for m in ("recall@30", "recall@100", "ndcg@10")},
    } for name in configs])
    summary.to_csv(RESULTS, index=False)
    print(f"users={len(per_user)}  liked per user={N_LIKED}")
    print(summary.round(4).to_string(index=False))

    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(per_user), size=(5000, len(per_user)))
    for w in (0.3, 0.5):  # each method vs vector search at the same popularity weight
        for name in (f"keyword + {w} pop", f"hybrid RRF + {w} pop"):
            for m in ("recall@30", "ndcg@10"):
                d = (per_user[f"{name}|{m}"] - per_user[f"vector + {w} pop|{m}"]).to_numpy()
                lo, hi = np.percentile(d[idx].mean(axis=1), [2.5, 97.5])
                sig = "significant" if lo > 0 or hi < 0 else "not significant"
                print(f"{name:<22} vs vector + {w} pop, {m:<10} {d.mean():+.4f} "
                      f"[{lo:+.4f}, {hi:+.4f}] {sig}")
    return summary


if __name__ == "__main__":
    main()
