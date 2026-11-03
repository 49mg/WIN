"""The WIN engine: nearest items to each liked item (pgvector) -> popularity re-rank ->
remove duplicates -> balanced list -> reasons.

Design comes from Phase 1 (notebooks/02_models.ipynb): content embeddings + a popularity
prior. Choices below were checked on MovieLens with the same evaluation code:

Popularity weight (score = cosine + w * popularity):
    weight   ndcg@10   coverage
    0.1      0.034     4.8%
    0.3      0.072     2.2%   <- default: most of the accuracy, twice the discovery of 0.5
    0.5      0.082     1.3%

Closest liked item instead of the average of liked items ("multi-interest"): averaging a
dark anime and a desert sci-fi novel gives a vector close to neither. Using the max
similarity to any liked item scored ndcg 0.078 vs 0.072 with 2.5x coverage on full user
histories, and 0.068 vs 0.070 (but 2.25x coverage) when users only give their last 5 likes.
"""

import math

import numpy as np

from app.config import settings
from app.db import connect

PER_LIKED = 80  # candidates fetched around each liked item
DISLIKE_WEIGHT = 0.5
# Editions and direct sequels of a liked item measured cos >= 0.69 (1984 vs "George Orwell's
# 1984" 0.83, Dune vs Dune Messiah 0.75); real recommendations were 0.40-0.63.
DUPLICATE_SIM = 0.68

CANDIDATE_COLS = ("id", "title", "category", "year", "description", "creators", "genres",
                  "image_url", "popularity", "embedding")


def _vec(v) -> np.ndarray | None:
    """pgvector returns its own Vector type; we compute with numpy."""
    return None if v is None else np.asarray(v.to_numpy(), dtype=np.float32)


def _rows_to_items(rows, cols) -> list[dict]:
    items = [dict(zip(cols, r, strict=True)) for r in rows]
    for it in items:
        it["embedding"] = _vec(it["embedding"])
    return [it for it in items if it["embedding"] is not None]


def _load(conn, ids):
    rows = conn.execute(
        "SELECT id, title, category, creators, genres, embedding FROM items WHERE id = ANY(%s)",
        (list(ids),),
    ).fetchall()
    return _rows_to_items(rows, ("id", "title", "category", "creators", "genres", "embedding"))


def _candidates(conn, liked, exclude, categories) -> list[dict]:
    where = "embedding IS NOT NULL AND NOT (id = ANY(%(exclude)s))"
    if categories:
        where += " AND category = ANY(%(categories)s)"
    found: dict[int, dict] = {}
    for src in liked:
        rows = conn.execute(
            f"""SELECT {", ".join(CANDIDATE_COLS)} FROM items WHERE {where}
                ORDER BY embedding <=> %(v)s LIMIT {PER_LIKED}""",
            {"v": src["embedding"], "exclude": exclude, "categories": categories},
        ).fetchall()
        for it in _rows_to_items(rows, CANDIDATE_COLS):
            found[it["id"]] = it
    return list(found.values())


def score(items: list[dict], liked: list[dict], disliked: list[dict], w: float) -> None:
    """sim = similarity to the closest liked item (that item becomes the pick's 'anchor'),
    minus a penalty for being close to something disliked; score adds popularity."""
    E = np.stack([it["embedding"] for it in items])
    L = np.stack([x["embedding"] for x in liked])
    sims = E @ L.T
    penalty = np.zeros(len(items))
    if disliked:
        penalty = DISLIKE_WEIGHT * np.clip((E @ np.stack([x["embedding"] for x in disliked]).T)
                                           .max(axis=1), 0, None)
    for it, row, pen in zip(items, sims, penalty, strict=True):
        it["anchor"] = int(row.argmax())
        it["sim"] = float(row.max())
        it["score"] = it["sim"] - pen + w * it["popularity"]


def drop_duplicates(ranked: list[dict], liked: list[dict]) -> list[dict]:
    """Remove other editions/sequels of liked items, near-copies of better-ranked picks,
    and keep at most one pick per creator, so the list is about discovery."""
    kept, seen_vecs = [], [x["embedding"] for x in liked]
    used_creators: set[str] = set()  # a liked creator may still appear once ("Also by ...")
    for item in ranked:
        if any(float(np.dot(item["embedding"], v)) > DUPLICATE_SIM for v in seen_vecs):
            continue
        creators = set(item["creators"])
        if creators & used_creators:
            continue
        kept.append(item)
        seen_vecs.append(item["embedding"])
        used_creators |= creators
    return kept


def balance(ranked: list[dict], k: int, n_liked: int, mix_categories: bool,
            max_category_share: float = 0.4) -> list[dict]:
    """Best items first, but every liked item gets its share of picks and (when not
    filtering) no category fills more than max_category_share. If the candidates don't
    have enough variety, fill up with the best of the rest."""
    anchor_cap = math.ceil(k / n_liked)
    chosen: set[int] = set()  # positions in `ranked`
    per_cat: dict[str, int] = {}
    per_anchor: dict[int, int] = {}
    # pass 1: both caps; pass 2: only the per-liked-item cap; pass 3: anything left
    for cat_cap, a_cap in [
        (max(1, math.ceil(k * max_category_share)) if mix_categories else k, anchor_cap),
        (k, anchor_cap),
        (k, k),
    ]:
        for i, it in enumerate(ranked):
            c, a = it["category"], it.get("anchor", 0)
            if len(chosen) == k:
                break
            if i in chosen or per_cat.get(c, 0) >= cat_cap or per_anchor.get(a, 0) >= a_cap:
                continue
            chosen.add(i)
            per_cat[c] = per_cat.get(c, 0) + 1
            per_anchor[a] = per_anchor.get(a, 0) + 1
    return [ranked[i] for i in sorted(chosen)]  # best-first order


def explain(item: dict, liked: list[dict]) -> str:
    """Free, rule-based reason: same creator > closest liked item + shared genres."""
    for src in liked:
        same = set(item["creators"]) & set(src["creators"])
        if same:
            return f"Also by {', '.join(sorted(same))}, who made {src['title']}."
    closest = liked[item["anchor"]]
    shared = [g for g in item["genres"] if g in closest["genres"]][:3]
    if shared:
        return f"Because you liked {closest['title']}: both are {', '.join(shared)}."
    return f"Similar story and themes to {closest['title']}."


# Mood text vs item similarities are low and flat (top-200 range ~0.2-0.5), so a smaller
# popularity weight than title mode: at 0 literal word matches win ("mind games" ->
# "The Hating Game"); 0.2 gave the most fitting lists in manual checks.
VIBE_POP_WEIGHT = 0.2
VIBE_CANDIDATES = 200
GENERIC_TAGS = {"fiction", "general", "literature", "novel", "novels", "english fiction",
                "american fiction", "large type books", "accessible book", "protected daisy"}


def vibe_reason(item: dict, query_vec: np.ndarray) -> str:
    """Name the item's tags that are closest in meaning to the mood the user typed."""
    from app.embed import encode

    # Open Library subjects can be long compound strings ("fiction, science fiction, general")
    tags = [t for t in dict.fromkeys(item["tags"])
            if t not in GENERIC_TAGS and not any(c in t for c in ",/(") and len(t) <= 30][:15]
    if not tags:
        return "Fits the mood you described."
    sims = encode(tags) @ query_vec
    best = [tags[i] for i in np.argsort(-sims)[:3]]
    return f"Fits your vibe: {', '.join(best)}."


def recommend_vibe(text: str, disliked_ids: list[int] | None = None,
                   categories: list[str] | None = None, k: int = 10) -> list[dict]:
    from app.embed import encode

    disliked_ids, categories = disliked_ids or [], categories or []
    query = encode([text])[0]
    where = "embedding IS NOT NULL AND NOT (id = ANY(%(exclude)s))"
    if categories:
        where += " AND category = ANY(%(categories)s)"
    with connect() as conn:
        disliked = _load(conn, disliked_ids)
        rows = conn.execute(
            f"""SELECT {", ".join(CANDIDATE_COLS)}, tags FROM items WHERE {where}
                ORDER BY embedding <=> %(v)s LIMIT {VIBE_CANDIDATES}""",
            {"v": query, "exclude": disliked_ids, "categories": categories},
        ).fetchall()
    items = _rows_to_items(rows, (*CANDIDATE_COLS, "tags"))
    if not items:
        return []

    # the mood acts as the single "liked" item
    score(items, [{"embedding": query}], disliked, VIBE_POP_WEIGHT)
    items.sort(key=lambda it: it["score"], reverse=True)
    picks = balance(drop_duplicates(items, []), k, 1, not categories)

    for it in picks:
        it["reason"] = vibe_reason(it, query)
        it["match"] = round(100 * max(it["sim"], 0))
        del it["embedding"], it["anchor"], it["tags"]
    return picks


def recommend(liked_ids: list[int], disliked_ids: list[int] | None = None,
              categories: list[str] | None = None, k: int = 10,
              pop_weight: float | None = None) -> list[dict]:
    w = settings.pop_weight if pop_weight is None else pop_weight
    disliked_ids, categories = disliked_ids or [], categories or []
    with connect() as conn:
        liked = _load(conn, liked_ids)
        if not liked:
            return []
        disliked = _load(conn, disliked_ids)
        items = _candidates(conn, liked, list(liked_ids) + list(disliked_ids), categories)
    if not items:
        return []

    score(items, liked, disliked, w)
    items.sort(key=lambda it: it["score"], reverse=True)
    picks = balance(drop_duplicates(items, liked), k, len(liked), not categories)

    for it in picks:
        it["reason"] = explain(it, liked)
        it["match"] = round(100 * max(it["sim"], 0))
        del it["embedding"], it["anchor"]
    return picks
