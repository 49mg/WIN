# WIN — What Is Next

Tell WIN what you loved (anime, books, movies, games) and it recommends what to try next, from any category, with a reason for each pick.

> Work in progress. Tasks are tracked in Taskflow (project `WIN`).

## How it works

1. **Import** popular items from free APIs into PostgreSQL. Each source's genres are mapped to one shared vocabulary, so a sci-fi book and a sci-fi anime match.
2. **Embed** each item's title, creators, genres, tags and description with `all-MiniLM-L6-v2`, stored in pgvector.
3. **Recommend:** fetch the nearest items around *each* liked item, score them as `similarity to the closest liked item + 0.3 × popularity`, and push down anything close to a 👎.
4. **Clean up:** drop other editions and sequels of what you liked, allow one pick per author or studio, and balance the list across your liked items and across categories.
5. **Explain** each pick with a rule-based reason ("Also by Frank Herbert…", "Because you liked Dune: both are sci-fi").

Every modelling choice was tested offline on MovieLens first. See `notebooks/02_models.ipynb` and the docstring of `backend/app/recommend.py`.

## Project layout

```
backend/     FastAPI app, data import, embeddings, recommendation engine (Python, uv)
frontend/    Next.js + Tailwind app
notebooks/   Data exploration and model evaluation
data/        Downloaded and generated data (gitignored)
```

## Run locally

```bash
cp .env.example .env                      # add free TMDB and IGDB keys (optional for anime/books)
docker compose up -d --build              # db :5433, API :8000, app :3000

cd backend && uv sync
uv run python -m app.ingest anilist --limit 2000       # anime, no key needed
uv run python -m app.ingest openlibrary --limit 3000   # books, no key needed (~10 min)
uv run python -m app.ingest tmdb --limit 5000          # movies + TV, needs TMDB_API_KEY
uv run python -m app.ingest igdb --limit 3000          # games, needs IGDB (Twitch) keys
uv run python -m app.embed                             # vectors for new or changed items
```

Then open http://localhost:3000.

Tests: `cd backend && uv run pytest`. Model comparison: `uv run python -m app.recsys.compare`.

## Data sources

Anime data from [AniList](https://anilist.co), books from [Open Library](https://openlibrary.org), games from [IGDB](https://www.igdb.com), movies and TV from [TMDB](https://www.themoviedb.org). This product uses the TMDB API but is not endorsed or certified by TMDB. Model evaluation uses [MovieLens](https://grouplens.org/datasets/movielens/) (GroupLens Research).
