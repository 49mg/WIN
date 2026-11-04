"""One-time import of items from free APIs into the items table.

    uv run python -m app.ingest anilist --limit 2000
    uv run python -m app.ingest openlibrary --limit 3000
    uv run python -m app.ingest tmdb --limit 5000      # needs TMDB_API_KEY
    uv run python -m app.ingest igdb --limit 3000      # needs IGDB_CLIENT_ID/SECRET (Twitch)

Each source module yields dicts with the keys in FIELDS. Re-running is safe (upsert).
"""

import re

from app.db import connect

FIELDS = ["category", "source", "source_id", "title", "year", "description", "creators",
          "genres", "tags", "image_url", "popularity_raw"]

# Shared genre vocabulary: lets a sci-fi book, movie, game and anime match each other.
# A source genre/subject maps to a shared genre if it contains one of the keywords as a whole
# word (an optional plural "s"/"es" is allowed), so "war" does not match "warrior".
SHARED_GENRES = {
    "action": ["action", "shooter", "fighting", "martial arts"],
    "adventure": ["adventure", "exploration", "open world"],
    "comedy": ["comedy", "humor", "humour", "funny", "parody", "satire"],
    "crime": ["crime", "detective", "heist", "gangster", "noir"],
    "drama": ["drama", "soap", "melodrama"],
    "family": ["family", "kids", "children", "juvenile"],
    "fantasy": ["fantasy", "magic", "mahou", "wizard", "dragon", "sword"],
    "history": ["history", "historical", "war & politics"],
    "horror": ["horror", "zombie", "vampire", "ghost", "gore"],
    "music": ["music", "musical", "idol"],
    "mystery": ["mystery", "mysteries", "whodunit"],
    "psychological": ["psychological", "philosophy", "philosophical"],
    "romance": ["romance", "love story", "love stories", "romantic"],
    "sci-fi": ["science fiction", "science-fiction", "sci-fi", "scifi", "mecha", "cyberpunk",
               "space opera", "dystopia", "time travel", "alien"],
    "slice of life": ["slice of life", "iyashikei", "school life"],
    "sports": ["sport", "racing"],
    "strategy": ["strategy", "tactics", "puzzle"],
    "supernatural": ["supernatural", "paranormal", "occult"],
    "thriller": ["thriller", "suspense", "espionage", "spy"],
    "war": ["war", "military"],
    "western": ["western", "cowboy"],
}


_PATTERNS = {
    genre: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")(s|es)?\b")
    for genre, kws in SHARED_GENRES.items()
}


def shared_genres(raw: list[str]) -> list[str]:
    text = " | ".join(raw).lower()
    return [genre for genre, pattern in _PATTERNS.items() if pattern.search(text)]


def clean_text(s: str | None) -> str | None:
    """Strip HTML tags and source notes like '(Source: ...)'."""
    if not s:
        return None
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\((source|written by)[^)]*\)|\[written by[^\]]*\]", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip() or None


UPSERT = f"""
INSERT INTO items ({", ".join(FIELDS)})
VALUES ({", ".join(f"%({f})s" for f in FIELDS)})
ON CONFLICT (source, source_id) DO UPDATE SET
    {", ".join(f"{f} = EXCLUDED.{f}" for f in FIELDS if f not in ("source", "source_id"))},
    -- text changed -> old vector is stale; `python -m app.embed` fills it again
    embedding = CASE WHEN (items.title, items.description, items.genres, items.tags)
                     IS NOT DISTINCT FROM (EXCLUDED.title, EXCLUDED.description,
                                           EXCLUDED.genres, EXCLUDED.tags)
                     THEN items.embedding END
"""

# Popularity counts differ wildly per source, so scale them 0..1 inside each category (log).
NORMALISE_POPULARITY = """
UPDATE items i SET popularity = ln(1 + i.popularity_raw) / NULLIF(m.max_log, 0)
FROM (SELECT category, max(ln(1 + popularity_raw)) AS max_log FROM items GROUP BY category) m
WHERE i.category = m.category
"""


def save(items) -> int:
    n = 0
    with connect() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(UPSERT, item)
                n += 1
                if n % 500 == 0:
                    conn.commit()
                    print(f"  saved {n}")
        conn.execute(NORMALISE_POPULARITY)
    return n
