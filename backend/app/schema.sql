CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS items (
    id          BIGSERIAL PRIMARY KEY,
    category    TEXT NOT NULL,          -- movie | tv | book | game | anime
    source      TEXT NOT NULL,          -- tmdb | rawg | openlibrary | anilist
    source_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    year        INT,
    description TEXT,
    creators    TEXT[] NOT NULL DEFAULT '{}',  -- authors, directors, studios
    genres      TEXT[] NOT NULL DEFAULT '{}',  -- shared vocabulary across categories
    tags        TEXT[] NOT NULL DEFAULT '{}',  -- source-specific keywords
    image_url   TEXT,
    popularity_raw REAL NOT NULL DEFAULT 0,    -- source's own count (members, readers, votes)
    popularity  REAL NOT NULL DEFAULT 0,       -- 0..1 within its category, from popularity_raw
    embedding   vector(384),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS items_title_trgm ON items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS items_embedding ON items USING hnsw (embedding vector_cosine_ops);

-- user_id is a random id kept in the browser until real accounts exist (WIN-25)
CREATE TABLE IF NOT EXISTS feedback (
    user_id    TEXT NOT NULL,
    item_id    BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    liked      BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS queue (
    user_id  TEXT NOT NULL,
    item_id  BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    done     BOOLEAN NOT NULL DEFAULT false,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);
