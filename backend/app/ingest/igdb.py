"""Video games from IGDB (free, Twitch developer account). https://api-docs.igdb.com

Auth: a Twitch app's client id + secret are exchanged for an app access token.
Replaced RAWG, whose API was down (Cloudflare 522) when we built this.
"""

import time
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.ingest import clean_text, shared_genres

FIELDS = (
    "name, first_release_date, summary, storyline, genres.name, themes.name, keywords.name, "
    "cover.image_id, total_rating_count, involved_companies.company.name, "
    "involved_companies.developer"
)
# Main games only: no editions/remasters of another entry (version_parent), no DLC (parent_game)
WHERE = "total_rating_count > 10 & version_parent = null & parent_game = null"
PAGE = 500  # IGDB maximum


def _token() -> str:
    if not (settings.igdb_client_id and settings.igdb_client_secret):
        raise SystemExit("IGDB_CLIENT_ID / IGDB_CLIENT_SECRET are empty. Add them to .env")
    r = httpx.post("https://id.twitch.tv/oauth2/token", timeout=30, params={
        "client_id": settings.igdb_client_id, "client_secret": settings.igdb_client_secret,
        "grant_type": "client_credentials",
    })
    r.raise_for_status()
    return r.json()["access_token"]


def fetch(limit: int):
    headers = {"Client-ID": settings.igdb_client_id, "Authorization": f"Bearer {_token()}"}
    n, offset = 0, 0
    with httpx.Client(base_url="https://api.igdb.com/v4", headers=headers, timeout=60) as client:
        while n < limit:
            body = (f"fields {FIELDS}; where {WHERE}; sort total_rating_count desc; "
                    f"limit {min(PAGE, limit - n)}; offset {offset};")
            r = client.post("/games", content=body)
            if r.status_code == 429:  # 4 requests/second limit
                time.sleep(1)
                continue
            r.raise_for_status()
            games = r.json()
            if not games:
                break
            for g in games:
                n += 1
                yield _item(g)
            offset += len(games)
            time.sleep(0.3)


def _item(g: dict) -> dict:
    genres = [x["name"] for x in g.get("genres", [])]
    themes = [x["name"] for x in g.get("themes", [])]
    keywords = [x["name"] for x in g.get("keywords", [])]
    developers = [c["company"]["name"] for c in g.get("involved_companies", [])
                  if c.get("developer") and "company" in c]
    text = " ".join(filter(None, [g.get("summary"), g.get("storyline")]))
    released = g.get("first_release_date")
    cover = g.get("cover", {}).get("image_id")
    return {
        "category": "game",
        "source": "igdb",
        "source_id": str(g["id"]),
        "title": g["name"],
        "year": datetime.fromtimestamp(released, UTC).year if released else None,
        "description": clean_text(text),
        "creators": developers[:3],
        # official genres + themes only; free-form keywords ("aliens" side quest) over-tag
        "genres": shared_genres(genres + themes),
        "tags": [x.lower() for x in genres + themes] + [k.lower() for k in keywords[:10]],
        "image_url": f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover}.jpg"
        if cover else None,
        "popularity_raw": g.get("total_rating_count", 0),
    }
