CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS items (
    id          BIGSERIAL PRIMARY KEY,
    category    TEXT NOT NULL,          -- movie | tv | book | game | anime
    source      TEXT NOT NULL,          -- tmdb | rawg | openlibrary | jikan
    source_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    year        INT,
    description TEXT,
    genres      TEXT[] NOT NULL DEFAULT '{}',
    tags        TEXT[] NOT NULL DEFAULT '{}',
    image_url   TEXT,
    popularity  REAL,
    embedding   vector(384),
    UNIQUE (source, source_id)
);
