"""Does the LLM help? Three-way comparison on MovieLens (WIN-33).

    uv run python -m app.recsys.llm_eval --users 100

Setup, made to look like real WIN use: each test user gives only their last 5 liked
movies; we predict the movies they went on to like (same time-based split as Phase 1).

1. engine        WIN's retrieval: closest-liked-item similarity + 0.3 popularity,
                 duplicate filter (same code as the app), top 10
2. engine + LLM  the engine's 30 best candidates, ordered by Claude (app/rerank.py)
3. LLM only      Claude is asked for movies directly; titles matched to the catalog

LLM answers are cached in data/processed/llm_eval_cache.json, so re-runs are free.
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app import rerank
from app.config import settings
from app.recommend import DUPLICATE_SIM, balance, drop_duplicates
from app.recsys.data import DATA_DIR, LIKE_THRESHOLD, load, split
from app.recsys.models import EmbeddingContent

K, N_LIKED, POOL = 10, 5, 30
CACHE = DATA_DIR / "processed" / "llm_eval_cache.json"
RESULTS = DATA_DIR.parent / "notebooks" / "results_llm.csv"


class Movie(BaseModel):
    title: str
    year: int


class MovieList(BaseModel):
    movies: list[Movie]


LLM_ONLY_SYSTEM = """You recommend movies. Given movies a person loved, suggest movies they \
are most likely to enjoy next, best first. Only suggest real, released movies; do not repeat \
the ones they listed."""


def _norm(title: str) -> str:
    """'Matrix, The (1999)' and 'The Matrix' -> 'matrix'."""
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    t = re.sub(r"^(.*), (the|a|an)$", r"\2 \1", t, flags=re.I)
    t = re.sub(r"^(the|a|an) ", "", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _metrics(picked: list[int], relevant: set[int]) -> dict:
    hits = np.array([i in relevant for i in picked[:K]] + [False] * (K - len(picked[:K])))
    disc = 1 / np.log2(np.arange(2, K + 2))
    return {"precision@10": hits.sum() / K, "recall@10": hits.sum() / len(relevant),
            "ndcg@10": (hits * disc).sum() / disc[: min(len(relevant), K)].sum()}


def main(n_users: int) -> pd.DataFrame:
    if not rerank.enabled():
        raise SystemExit("Set ANTHROPIC_API_KEY in .env to run the LLM comparison")
    ratings, movies = load(tmdb=True)
    train, test = split(ratings)
    E = EmbeddingContent("all-MiniLM-L6-v2").item_vectors(movies)
    col = pd.Series(np.arange(len(movies)), index=movies["movieId"])
    likes = train[train["rating"] >= LIKE_THRESHOLD].groupby("userId")["movieId"].size()
    pop = np.log1p(np.bincount(col[train.loc[train.rating >= LIKE_THRESHOLD, "movieId"]],
                               minlength=len(movies)))
    pop = pop / pop.max()

    users = test["userId"].drop_duplicates().sample(frac=1, random_state=42)
    users = [u for u in users if likes.get(u, 0) >= N_LIKED][:n_users]
    by_title = {}
    for i, (t, y) in enumerate(zip(movies["title"], movies["year"], strict=True)):
        by_title.setdefault(_norm(t), []).append((0 if pd.isna(y) else int(y), i))

    def item(i: int) -> dict:
        m = movies.iloc[i]
        return {"id": int(i), "title": m["title"], "category": "movie",
                "year": None if pd.isna(m["year"]) else int(m["year"]), "genres": m["genres"],
                "description": m["overview"], "creators": [], "embedding": E[i],
                "popularity": float(pop[i])}

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    def evaluate_user(u):
        hist = train[train.userId == u].sort_values("timestamp")
        seen = set(col[hist["movieId"]])
        liked_idx = list(col[hist.loc[hist.rating >= LIKE_THRESHOLD, "movieId"]].iloc[-N_LIKED:])
        relevant = set(col[test.loc[test.userId == u, "movieId"]])
        liked = [item(i) for i in liked_idx]

        # 1. engine (same scoring, duplicate filter and balancing code as the app)
        sims = E @ E[liked_idx].T
        score = sims.max(axis=1) + settings.pop_weight * pop
        score[list(seen)] = -np.inf
        cands = []
        for i in np.argsort(-score)[:200]:
            it = item(int(i))
            it.update(sim=float(sims[i].max()), anchor=int(sims[i].argmax()), score=score[i])
            cands.append(it)
        ranked = drop_duplicates(cands, liked)
        engine = [c["id"] for c in balance(ranked, K, N_LIKED, False)]
        pool = balance(ranked, POOL, N_LIKED, False)

        # 2. engine + LLM re-ranking (production code path)
        key = f"rerank:{u}"
        if key not in cache:
            out = rerank.rerank(liked, pool, K)
            cache[key] = [x["id"] for x in out] if out else None
        reranked = cache[key] or engine

        # 3. LLM only: ask for 20 so we can drop ones the user already rated
        key = f"llm_only:{u}"
        if key not in cache:
            listed = "\n".join(f"- {x['title']}" for x in liked)
            resp = rerank._get_client().messages.parse(
                model=settings.llm_model, max_tokens=4000, system=LLM_ONLY_SYSTEM,
                output_config={"effort": "low"}, output_format=MovieList,
                messages=[{"role": "user", "content": f"Movies I loved:\n{listed}\n\n"
                                                      "Recommend 20 movies, best first."}])
            cache[key] = ([m.model_dump() for m in resp.parsed_output.movies]
                          if resp.parsed_output else [])
        matched, misses = [], 0
        for m in cache[key]:
            options = by_title.get(_norm(m["title"]), [])
            hit = min(options, key=lambda o: abs(o[0] - m["year"]), default=None)
            if hit is None:
                misses += 1
            elif hit[1] not in seen and hit[1] not in matched:
                matched.append(hit[1])
        return {"user": u, "pool_recall": len(relevant & {c["id"] for c in pool}) / len(relevant),
                "llm_only_unmatched": misses / max(len(cache[key]), 1),
                **{f"engine {k}": v for k, v in _metrics(engine, relevant).items()},
                **{f"engine + LLM {k}": v for k, v in _metrics(reranked, relevant).items()},
                **{f"LLM only {k}": v for k, v in _metrics(matched, relevant).items()}}

    try:
        with ThreadPoolExecutor(4) as pool_exec:
            rows = list(pool_exec.map(evaluate_user, users))
    finally:  # keep paid-for LLM answers even if the run crashes
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache))

    per_user = pd.DataFrame(rows)
    summary = pd.DataFrame([
        {"method": m, **{k: per_user[f"{m} {k}"].mean() for k in ("precision@10", "recall@10",
                                                                     "ndcg@10")}}
        for m in ("engine", "engine + LLM", "LLM only")
    ])
    RESULTS.parent.mkdir(exist_ok=True)
    summary.to_csv(RESULTS, index=False)
    print(f"users={len(per_user)}  liked per user={N_LIKED}  duplicate filter={DUPLICATE_SIM}")
    print(f"recall ceiling of the 30-candidate pool given to the LLM: "
          f"{per_user['pool_recall'].mean():.3f}")
    print(f"LLM-only titles not found in the MovieLens catalog: "
          f"{per_user['llm_only_unmatched'].mean():.1%}")
    print(summary.round(4).to_string(index=False))
    per_user.to_csv(RESULTS.with_name("results_llm_per_user.csv"), index=False)

    # Paired bootstrap: is the difference vs the engine real or noise? (same users, resampled)
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(per_user), size=(5000, len(per_user)))
    for m in ("engine + LLM", "LLM only"):
        for k in ("recall@10", "ndcg@10"):
            diff = (per_user[f"{m} {k}"] - per_user[f"engine {k}"]).to_numpy()
            boots = diff[idx].mean(axis=1)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            print(f"{m:<13} vs engine, {k}: {diff.mean():+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]"
                  f"  {'(significant)' if lo > 0 or hi < 0 else '(not significant)'}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=100)
    main(parser.parse_args().users)
