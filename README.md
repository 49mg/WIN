# WIN — What Is Next

Tell WIN what you loved (movies, books, games, anime) and it recommends what to try next, from any category, with a reason for each pick.

> Work in progress. Tasks are tracked in Taskflow (project `WIN`).

## Project layout

```
backend/     FastAPI app, data import, recommendation code (Python, uv)
notebooks/   Data exploration and model evaluation
frontend/    Next.js app (coming in Phase 2)
data/        Downloaded and generated data (gitignored)
```

## Run locally

```bash
cp .env.example .env          # add your free TMDB and RAWG keys
docker compose up -d db       # PostgreSQL + pgvector
cd backend && uv sync
uv run uvicorn app.main:app --reload
# http://localhost:8000/health
```

Or run everything in Docker: `docker compose up --build`.

## Data sources

This product uses the TMDB API but is not endorsed or certified by TMDB.
Other sources: RAWG, Open Library, Jikan (MyAnimeList), MovieLens (GroupLens Research).
