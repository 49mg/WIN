"""Offline evaluation: one function that scores any model the same way.

A model is any object with:
    fit(train_ratings, movies) -> self
    score(user_ids) -> array of shape (len(user_ids), len(movies)), higher = better
Columns of the score array follow the row order of `movies`.
"""

import time

import numpy as np
import pandas as pd


def evaluate(model, train: pd.DataFrame, test: pd.DataFrame, movies: pd.DataFrame, k: int = 10):
    t0 = time.perf_counter()
    model.fit(train, movies)
    fit_s = time.perf_counter() - t0

    col = pd.Series(np.arange(len(movies)), index=movies["movieId"])
    seen = train.groupby("userId")["movieId"].apply(lambda m: col[m].to_numpy())
    truth = test.groupby("userId")["movieId"].apply(lambda m: set(col[m]))
    users = truth.index.to_numpy()

    genre_sets = movies["genres"].apply(set).tolist()
    discounts = 1.0 / np.log2(np.arange(2, k + 2))

    precision, recall, ndcg, diversity = [], [], [], []
    recommended = set()
    for start in range(0, len(users), 256):
        batch = users[start : start + 256]
        scores = np.asarray(model.score(batch), dtype=np.float64)
        for row, user in zip(scores, batch, strict=True):
            row[seen.get(user, [])] = -np.inf  # never recommend what the user already rated
            top = np.argpartition(-row, k)[:k]
            top = top[np.argsort(-row[top])]
            recommended.update(top.tolist())

            relevant = truth[user]
            hit = np.array([i in relevant for i in top])
            precision.append(hit.sum() / k)
            recall.append(hit.sum() / len(relevant))
            ideal = discounts[: min(len(relevant), k)].sum()
            ndcg.append((hit * discounts).sum() / ideal)
            diversity.append(_genre_diversity([genre_sets[i] for i in top]))

    return {
        "model": getattr(model, "name", type(model).__name__),
        f"precision@{k}": float(np.mean(precision)),
        f"recall@{k}": float(np.mean(recall)),
        f"ndcg@{k}": float(np.mean(ndcg)),
        "coverage": len(recommended) / len(movies),
        "diversity": float(np.mean(diversity)),
        "fit_seconds": round(fit_s, 1),
        "users": len(users),
    }


def _genre_diversity(genres: list[set]) -> float:
    """1 - average Jaccard similarity of genres between every pair in the list."""
    sims = []
    for i in range(len(genres)):
        for j in range(i + 1, len(genres)):
            union = genres[i] | genres[j]
            sims.append(len(genres[i] & genres[j]) / len(union) if union else 0.0)
    return 1.0 - float(np.mean(sims)) if sims else 0.0
