CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS items (
    id          BIGSERIAL PRIMARY KEY,
    category    TEXT NOT NULL,          -- movie | tv | book | game | anime
    source      TEXT NOT NULL,          -- tmdb | igdb | openlibrary | anilist
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

-- Anonymous accounts: the server hands out a random id, the browser keeps it.
-- A real login can later attach to the same row.
CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- the things a user says they loved (the chips on Discover), in the order they added them
CREATE TABLE IF NOT EXISTS liked (
    user_id  UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_id  BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    position INT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

-- 👍 / 👎 on recommendations
CREATE TABLE IF NOT EXISTS feedback (
    user_id    UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_id    BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    liked      BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS queue (
    user_id  UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_id  BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    done     BOOLEAN NOT NULL DEFAULT false,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

-- A/B test (WIN-37): each new user is put in one arm at random.
-- 'llm' = engine + LLM re-ranking, 'engine' = engine only (holdout).
ALTER TABLE users ADD COLUMN IF NOT EXISTS arm TEXT NOT NULL DEFAULT 'llm';

-- What users were shown and what they did with it, for online metrics.
CREATE TABLE IF NOT EXISTS events (
    id       BIGSERIAL PRIMARY KEY,
    user_id  UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    event    TEXT NOT NULL CHECK (event IN ('impression', 'like', 'dislike', 'queue')),
    item_id  BIGINT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    list_id  UUID NOT NULL,       -- one recommendation list shown to the user
    mode     TEXT NOT NULL CHECK (mode IN ('titles', 'vibe')),
    source   TEXT NOT NULL CHECK (source IN ('engine', 'llm')),  -- who picked the item
    position INT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_user ON events (user_id);

-- Read-only share code (Blend, taste cards). Separate from the user id, which works like a
-- password: anyone with the id can change the user's data, so it must never be shared.
ALTER TABLE users ADD COLUMN IF NOT EXISTS share_code TEXT UNIQUE;

-- LLM usage per day: enforces the daily call cap and shows calls + cost on /stats.
CREATE TABLE IF NOT EXISTS llm_usage (
    day           DATE PRIMARY KEY,
    calls         INT NOT NULL DEFAULT 0,
    input_tokens  BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0
);
