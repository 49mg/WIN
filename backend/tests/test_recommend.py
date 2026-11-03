import numpy as np

from app.recommend import balance, drop_duplicates, explain, score


def test_score_uses_closest_liked_item_and_penalises_dislikes():
    liked = [_item("A", emb=(1.0, 0.0)), _item("B", emb=(0.0, 1.0))]
    disliked = [_item("X", emb=(0.6, -0.8))]
    items = [{**_item("near B", emb=(0.1, 0.99)), "popularity": 0.0},
             {**_item("near X", emb=(0.8, -0.6)), "popularity": 0.0}]
    score(items, liked, disliked, w=0.3)
    assert items[0]["anchor"] == 1  # matched to B, not to the average of A and B
    assert np.isclose(items[0]["sim"], 0.99)
    assert items[1]["score"] < items[1]["sim"]  # close to a dislike -> pushed down


def test_balance_caps_each_category():
    ranked = [{"id": c * 100 + i, "category": cat}
              for c, cat in enumerate(["anime", "book", "game"]) for i in range(10)]
    picks = balance(ranked, k=10, n_liked=1, mix_categories=True)
    cats = [p["category"] for p in picks]
    assert len(picks) == 10
    assert cats.count("anime") == 4  # capped, even though all anime ranked higher
    assert cats.count("game") == 2
    assert picks[0]["id"] == 0  # best item still comes first


def test_balance_fills_up_when_only_one_category():
    ranked = [{"id": i, "category": "anime"} for i in range(10)]
    assert len(balance(ranked, k=10, n_liked=1, mix_categories=True)) == 10


def test_balance_gives_every_liked_item_its_share():
    # anchor 0 (e.g. Death Note) dominates the ranking, anchor 1 (Dune) comes later
    ranked = [{"id": i, "category": "book", "anchor": 0} for i in range(10)] + [
        {"id": 100 + i, "category": "book", "anchor": 1} for i in range(10)]
    picks = balance(ranked, k=10, n_liked=2, mix_categories=False)
    assert [p["anchor"] for p in picks].count(1) == 5


def _item(title, creators=(), genres=(), emb=(1.0, 0.0), anchor=0):
    return {"title": title, "creators": list(creators), "genres": list(genres),
            "embedding": np.array(emb), "anchor": anchor}


def test_explain_prefers_shared_creator():
    liked = [_item("The Martian", creators=["Andy Weir"])]
    pick = _item("Project Hail Mary", creators=["Andy Weir"])
    assert explain(pick, liked) == "Also by Andy Weir, who made The Martian."


def test_explain_uses_closest_liked_item_and_shared_genres():
    liked = [_item("Interstellar", genres=["sci-fi", "drama"], emb=(1.0, 0.0)),
             _item("Amélie", genres=["romance"], emb=(0.0, 1.0))]
    pick = _item("Arrival", genres=["sci-fi", "drama", "mystery"], emb=(0.9, 0.1), anchor=0)
    assert explain(pick, liked) == "Because you liked Interstellar: both are sci-fi, drama."


def test_drop_duplicates_removes_editions_and_repeat_creators():
    liked = [_item("1984", creators=["George Orwell"], emb=(1.0, 0.0))]
    ranked = [
        _item("George Orwell's 1984", creators=["Someone"], emb=(0.99, 0.14)),  # edition
        _item("Animal Farm", creators=["George Orwell"], emb=(0.6, 0.8)),
        _item("Homage to Catalonia", creators=["George Orwell"], emb=(0.5, -0.866)),
        _item("Brave New World", creators=["Aldous Huxley"], emb=(-0.6, 0.8)),
    ]
    kept = [x["title"] for x in drop_duplicates(ranked, liked)]
    assert kept == ["Animal Farm", "Brave New World"]


def test_balance_relaxes_category_cap_before_anchor_cap():
    # only two categories: the 40% category cap can't fill 10 slots, but each of the
    # two liked items should still get 5 picks
    ranked = [{"id": i, "category": "anime", "anchor": 0} for i in range(10)] + [
        {"id": 100 + i, "category": "book", "anchor": 1} for i in range(10)]
    picks = balance(ranked, k=10, n_liked=2, mix_categories=True)
    assert [p["anchor"] for p in picks].count(1) == 5
    assert [p["id"] for p in picks] == sorted(p["id"] for p in picks)  # best-first order
