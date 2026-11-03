"""Turn items into vectors and store them in pgvector.

    uv run python -m app.embed          # embeds only items that have no vector yet

The model choice comes from Phase 1 (notebooks/02_models.ipynb): all-MiniLM-L6-v2.
Category is left out of the text on purpose, so a book and a movie about the same
thing land close together.
"""

import threading

import numpy as np

from app.db import connect

MODEL = "all-MiniLM-L6-v2"
_model = None
_lock = threading.Lock()


def model():
    """Load once. The lock stops the startup warm-up and a first request loading it twice."""
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            try:  # cached copy first: skips slow update checks against the Hugging Face Hub
                _model = SentenceTransformer(MODEL, local_files_only=True)
            except OSError:
                _model = SentenceTransformer(MODEL)  # first run: download
    return _model


def encode(texts: list[str]) -> np.ndarray:
    return model().encode(texts, batch_size=64, normalize_embeddings=True)


def item_text(title, creators, genres, tags, description) -> str:
    parts = [title]
    if creators:
        parts.append("By " + ", ".join(creators))
    if genres:
        parts.append("Genres: " + ", ".join(genres))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if description:
        parts.append(description[:1000])
    return ". ".join(parts)


def embed_missing(batch: int = 256) -> int:
    done = 0
    with connect() as conn:
        while True:
            rows = conn.execute(
                "SELECT id, title, creators, genres, tags, description FROM items "
                "WHERE embedding IS NULL LIMIT %s", (batch,)
            ).fetchall()
            if not rows:
                return done
            vectors = encode([item_text(*r[1:]) for r in rows])
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE items SET embedding = %s WHERE id = %s",
                    [(v, r[0]) for v, r in zip(vectors, rows, strict=True)],
                )
            conn.commit()
            done += len(rows)
            print(f"  embedded {done}")


if __name__ == "__main__":
    print(f"embedded {embed_missing()} items")
