"""The four candidate recommenders compared in Phase 1.

All follow the interface in evaluate.py: fit(train, movies) then score(user_ids).
"""

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from app.recsys.data import DATA_DIR, LIKE_THRESHOLD


def _likes_matrix(train: pd.DataFrame, movies: pd.DataFrame):
    """Sparse users x items matrix with 1 where the user liked the movie."""
    col = pd.Series(np.arange(len(movies)), index=movies["movieId"])
    users = np.sort(train["userId"].unique())
    row = pd.Series(np.arange(len(users)), index=users)
    liked = train[train["rating"] >= LIKE_THRESHOLD]
    m = sparse.csr_matrix(
        (np.ones(len(liked)), (row[liked["userId"]].to_numpy(), col[liked["movieId"]].to_numpy())),
        shape=(len(users), len(movies)),
    )
    return m, row


class Popularity:
    """Baseline: everyone gets the most-liked movies they haven't seen."""

    name = "popularity"

    def fit(self, train, movies):
        likes, _ = _likes_matrix(train, movies)
        self.pop = np.asarray(likes.sum(axis=0)).ravel()
        return self

    def score(self, user_ids):
        return np.tile(self.pop, (len(user_ids), 1))


class _ContentModel:
    """Profile = average vector of the movies the user liked; score = similarity."""

    def item_vectors(self, movies):  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def fit(self, train, movies):
        self.items = self.item_vectors(movies)  # (n_items, dim), rows L2-normalised
        likes, self.row = _likes_matrix(train, movies)
        counts = np.asarray(likes.sum(axis=1)).ravel()
        counts[counts == 0] = 1
        self.profiles = sparse.diags(1.0 / counts) @ likes @ self.items
        # tiny popularity tie-break so users with no likes still get sensible picks
        self.tiebreak = 1e-6 * np.asarray(likes.sum(axis=0)).ravel()
        return self

    def score(self, user_ids):
        p = self.profiles[self.row[user_ids].to_numpy()]
        s = p @ self.items.T
        s = s.toarray() if sparse.issparse(s) else np.asarray(s)
        return s + self.tiebreak


def item_text(movies: pd.DataFrame) -> pd.Series:
    return (
        movies["title"]
        + ". Genres: "
        + movies["genres"].str.join(", ")
        + ". Tags: "
        + movies["tags"].str.join(", ")
    )


class TfidfContent(_ContentModel):
    name = "tfidf"

    def item_vectors(self, movies):
        tokens = movies["genres"].str.join(" ").str.replace("-", "") + " " + movies[
            "tags"
        ].str.join(" ")
        return TfidfVectorizer(min_df=2, sublinear_tf=True).fit_transform(tokens)


class EmbeddingContent(_ContentModel):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.name = f"embedding ({model_name})"

    def item_vectors(self, movies):
        cache = DATA_DIR / "processed" / f"ml_emb_{self.model_name.replace('/', '_')}.npy"
        if cache.exists():
            emb = np.load(cache)
            if len(emb) == len(movies):
                return emb
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self.model_name)
        emb = model.encode(
            item_text(movies).tolist(), batch_size=128, normalize_embeddings=True,
            show_progress_bar=True,
        )
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, emb)
        return emb


class WithPopularity:
    """Blend a content model with a popularity prior: score = similarity + w * popularity.

    Both parts are scaled to 0..1 per user. Content models alone push obscure items;
    a little popularity keeps picks relevant while still following the user's taste.
    """

    def __init__(self, base: _ContentModel, weight: float):
        self.base, self.weight = base, weight
        self.name = f"{base.name} + pop (w={weight})"

    def fit(self, train, movies):
        self.base.fit(train, movies)
        likes, _ = _likes_matrix(train, movies)
        pop = np.log1p(np.asarray(likes.sum(axis=0)).ravel())
        self.pop = pop / pop.max()
        return self

    def score(self, user_ids):
        s = self.base.score(user_ids)
        lo, hi = s.min(axis=1, keepdims=True), s.max(axis=1, keepdims=True)
        return (s - lo) / np.maximum(hi - lo, 1e-9) + self.weight * self.pop


class ALS:
    """Collaborative filtering: learns from what similar users liked (implicit library)."""

    def __init__(self, factors: int = 64, regularization: float = 0.05, alpha: float = 10.0,
                 iterations: int = 20):
        self.params = dict(factors=factors, regularization=regularization, alpha=alpha,
                           iterations=iterations)
        self.name = f"als (f={factors}, reg={regularization}, a={alpha})"

    def fit(self, train, movies):
        from implicit.als import AlternatingLeastSquares

        likes, self.row = _likes_matrix(train, movies)
        self.model = AlternatingLeastSquares(**self.params, random_state=42)
        self.model.fit(likes.tocsr(), show_progress=False)
        return self

    def score(self, user_ids):
        u = self.model.user_factors[self.row[user_ids].to_numpy()]
        return np.asarray(u @ self.model.item_factors.T)
