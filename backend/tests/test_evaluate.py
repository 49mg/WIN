import numpy as np
import pandas as pd

from app.recsys.data import split
from app.recsys.evaluate import _genre_diversity, evaluate


def _movies(n=20):
    return pd.DataFrame(
        {"movieId": range(1, n + 1), "genres": [["A"] if i % 2 else ["B"] for i in range(n)]}
    )


class Oracle:
    """Cheats by scoring the test items highest, so every metric should be perfect."""

    name = "oracle"

    def __init__(self, test, movies):
        self.test, self.movies = test, movies

    def fit(self, train, movies):
        return self

    def score(self, user_ids):
        s = np.zeros((len(user_ids), len(self.movies)))
        for r, u in enumerate(user_ids):
            liked = self.test[self.test.userId == u].movieId
            s[r, self.movies.index[self.movies.movieId.isin(liked)]] = 1
        return s


def test_oracle_gets_perfect_ndcg_and_recall():
    movies = _movies()
    train = pd.DataFrame({"userId": [1, 1], "movieId": [1, 2], "rating": [5, 5]})
    test = pd.DataFrame({"userId": [1, 1], "movieId": [3, 4], "rating": [5, 5]})
    r = evaluate(Oracle(test, movies), train, test, movies, k=10)
    assert r["recall@10"] == 1.0
    assert r["ndcg@10"] == 1.0
    assert r["precision@10"] == 0.2


def test_seen_items_are_never_recommended():
    movies = _movies()
    train = pd.DataFrame({"userId": [1], "movieId": [5], "rating": [5]})
    test = pd.DataFrame({"userId": [1], "movieId": [5], "rating": [5]})  # same item
    r = evaluate(Oracle(test, movies), train, test, movies, k=5)
    assert r["recall@5"] == 0.0


def test_split_is_time_based_and_test_only_has_likes():
    ratings = pd.DataFrame(
        {
            "userId": [1] * 10,
            "movieId": range(10),
            "rating": [5] * 8 + [2, 5],
            "timestamp": range(10),
        }
    )
    train, test = split(ratings, test_frac=0.2, min_likes=5)
    assert train.timestamp.max() < ratings.timestamp.iloc[-2:].min()
    assert list(test.movieId) == [9]  # movie 8 was rated 2, so it is not a "like"


def test_genre_diversity():
    assert _genre_diversity([{"A"}, {"A"}]) == 0.0
    assert _genre_diversity([{"A"}, {"B"}]) == 1.0
