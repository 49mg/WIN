"""Keyword retrieval: TF-IDF over each item's genres, tags and description, kept in memory.

This is the keyword half of hybrid search (WIN-34). It is the same TF-IDF that was measured
in app/recsys/hybrid_eval.py, where fusing it with vector search raised recall@30 by 24%.
(PostgreSQL's ts_rank was not used: it ignores how rare a word is, so it would be a
different method from the one we evaluated.)

The index is built from the database on first use and rebuilt when the catalog changes.
"""

import threading
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.db import connect

CHECK_EVERY = 60  # seconds between "did the catalog change?" checks


class KeywordIndex:
    def __init__(self):
        self._lock = threading.Lock()
        self._version = None
        self._checked = 0.0

    def _build(self, conn, version):
        rows = conn.execute(
            "SELECT id, category, popularity, genres, tags, coalesce(description, '') "
            "FROM items ORDER BY id"
        ).fetchall()
        docs = [" ".join(g.replace("-", "") for g in genres) + " " + " ".join(tags) + " " + desc
                for _, _, _, genres, tags, desc in rows]
        self.vectorizer = TfidfVectorizer(min_df=2, sublinear_tf=True, stop_words="english")
        self.matrix = self.vectorizer.fit_transform(docs).tocsr()
        self.ids = np.array([r[0] for r in rows])
        self.categories = np.array([r[1] for r in rows])
        self.popularity = np.array([r[2] for r in rows], dtype=float)
        self.row_of = {int(item_id): i for i, item_id in enumerate(self.ids)}
        self._version = version

    def _ensure(self):
        now = time.time()
        if self._version is not None and now - self._checked < CHECK_EVERY:
            return
        with self._lock, connect() as conn:
            version = conn.execute("SELECT count(*), max(id) FROM items").fetchone()
            if version != self._version:
                self._build(conn, version)
            self._checked = now

    def similarity_to_items(self, item_ids: list[int]) -> np.ndarray:
        """Keyword similarity of every catalog item to its closest item in `item_ids`."""
        self._ensure()
        rows = [self.row_of[i] for i in item_ids if i in self.row_of]
        if not rows:
            return np.zeros(len(self.ids))
        return np.asarray((self.matrix @ self.matrix[rows].T).toarray().max(axis=1)).ravel()

    def similarity_to_text(self, text: str) -> np.ndarray:
        """Keyword similarity of every catalog item to free text (all zeros if no known word)."""
        self._ensure()
        query = self.vectorizer.transform([text])
        return np.asarray((self.matrix @ query.T).toarray()).ravel()

    def top(self, sims: np.ndarray, pop_weight: float, n: int, exclude: list[int],
            categories: list[str]) -> list[int]:
        """Ids of the n best keyword matches (similarity + popularity), with filters applied."""
        s = sims + pop_weight * self.popularity
        s[sims <= 0] = -np.inf  # no shared words at all: not a keyword match
        s[[self.row_of[i] for i in exclude if i in self.row_of]] = -np.inf
        if categories:
            s[~np.isin(self.categories, categories)] = -np.inf
        best = np.argsort(-s)[:n]
        return [int(self.ids[i]) for i in best if np.isfinite(s[i])]

    def lookup(self, sims: np.ndarray, item_ids: list[int]) -> np.ndarray:
        return np.array([sims[self.row_of[i]] if i in self.row_of else 0.0 for i in item_ids])


index = KeywordIndex()
