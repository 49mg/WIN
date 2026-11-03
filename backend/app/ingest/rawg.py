"""Video games from RAWG (free key). https://rawg.io/apidocs

RAWG's terms require a visible link back to rawg.io wherever this data is shown.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx

from app.config import settings
from app.ingest import clean_text, shared_genres

API = "https://api.rawg.io/api"


def fetch(limit: int):
    if not settings.rawg_api_key:
        raise SystemExit("RAWG_API_KEY is empty. Add your free key to .env")
    params = {"key": settings.rawg_api_key}
    with httpx.Client(base_url=API, timeout=30, params=params) as client:
        games, page = [], 1
        while len(games) < limit:
            r = client.get("/games", params={**params, "ordering": "-added", "page_size": 40,
                                             "page": page})
            r.raise_for_status()
            games += r.json()["results"]
            page += 1
        games = games[:limit]

        def details(g):
            return client.get(f"/games/{g['id']}").json()

        with ThreadPoolExecutor(4) as pool:
            full = list(pool.map(details, games))

    for g, d in zip(games, full, strict=True):
        genres = [x["name"] for x in g.get("genres", [])]
        tags = [t["name"] for t in g.get("tags", []) if t.get("language") == "eng"]
        released = g.get("released") or ""
        yield {
            "category": "game",
            "source": "rawg",
            "source_id": str(g["id"]),
            "title": g["name"],
            "year": int(released[:4]) if released[:4].isdigit() else None,
            "description": clean_text(d.get("description_raw")),
            "creators": [x["name"] for x in d.get("developers", [])][:3],
            "genres": shared_genres(genres + tags),
            "tags": [x.lower() for x in genres] + [t.lower() for t in tags[:12]],
            "image_url": g.get("background_image"),
            "popularity_raw": g.get("added", 0),
        }
