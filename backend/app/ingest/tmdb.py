"""Movies and TV shows from TMDB (free key). https://developer.themoviedb.org

This product uses the TMDB API but is not endorsed or certified by TMDB.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx

from app.config import settings
from app.ingest import clean_text, shared_genres

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"


def _client() -> httpx.Client:
    key = settings.tmdb_api_key
    if not key:
        raise SystemExit("TMDB_API_KEY is empty. Add your free key to .env")
    # TMDB gives two kinds of key: a short v3 "API key" or a long v4 "read access token".
    if len(key) > 40:
        return httpx.Client(base_url=API, timeout=30, headers={"Authorization": f"Bearer {key}"})
    return httpx.Client(base_url=API, timeout=30, params={"api_key": key})


def _details(client, kind, tmdb_id):
    extra = "keywords,credits" if kind == "movie" else "keywords"
    return client.get(f"/{kind}/{tmdb_id}", params={"append_to_response": extra}).json()


def _fetch_kind(client, kind: str, limit: int):
    ids, page = [], 1
    while len(ids) < limit:
        r = client.get(f"/discover/{kind}", params={
            "sort_by": "vote_count.desc", "page": page, "include_adult": "false",
        })
        r.raise_for_status()
        results = r.json()["results"]
        if not results:
            break
        ids += [x["id"] for x in results]
        page += 1
    ids = ids[:limit]

    with ThreadPoolExecutor(8) as pool:
        details = list(pool.map(lambda i: _details(client, kind, i), ids))

    for d in details:
        if "id" not in d:
            continue
        genres = [g["name"] for g in d.get("genres", [])]
        kw = d.get("keywords", {})
        keywords = [k["name"] for k in kw.get("keywords", kw.get("results", []))]
        if kind == "movie":
            creators = [c["name"] for c in d.get("credits", {}).get("crew", [])
                        if c["job"] == "Director"]
        else:
            creators = [c["name"] for c in d.get("created_by", [])]
        date = d.get("release_date") or d.get("first_air_date") or ""
        yield {
            "category": "movie" if kind == "movie" else "tv",
            "source": "tmdb",
            "source_id": f"{kind}/{d['id']}",
            "title": d.get("title") or d.get("name"),
            "year": int(date[:4]) if date[:4].isdigit() else None,
            "description": clean_text(d.get("overview")),
            "creators": creators[:3],
            "genres": shared_genres(genres + keywords),
            "tags": [g.lower() for g in genres] + [k.lower() for k in keywords[:12]],
            "image_url": IMG + d["poster_path"] if d.get("poster_path") else None,
            "popularity_raw": d.get("vote_count", 0),
        }


def fetch(limit: int):
    with _client() as client:
        yield from _fetch_kind(client, "movie", int(limit * 0.7))
        yield from _fetch_kind(client, "tv", int(limit * 0.3))
