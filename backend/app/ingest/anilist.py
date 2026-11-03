"""Anime from AniList (free GraphQL API, no key). https://docs.anilist.co"""

import time

import httpx

from app.ingest import clean_text, shared_genres

QUERY = """
query ($page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(type: ANIME, sort: POPULARITY_DESC, isAdult: false) {
      id format seasonYear startDate { year }
      title { english romaji }
      description(asHtml: false)
      genres
      tags { name rank isMediaSpoiler }
      coverImage { large }
      popularity
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""


def fetch(limit: int):
    page, n = 1, 0
    with httpx.Client(timeout=30) as client:
        while n < limit:
            body = {"query": QUERY, "variables": {"page": page}}
            r = client.post("https://graphql.anilist.co", json=body)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 60)))
                continue
            r.raise_for_status()
            data = r.json()["data"]["Page"]
            for m in data["media"]:
                if m["format"] in ("MUSIC", "PV", "CM") or n >= limit:
                    continue
                tags = [t["name"] for t in m["tags"] if t["rank"] >= 60 and not t["isMediaSpoiler"]]
                n += 1
                yield {
                    "category": "anime",
                    "source": "anilist",
                    "source_id": str(m["id"]),
                    "title": m["title"]["english"] or m["title"]["romaji"],
                    "year": m["seasonYear"] or m["startDate"]["year"],
                    "description": clean_text(m["description"]),
                    "creators": [s["name"] for s in m["studios"]["nodes"]],
                    "genres": shared_genres(m["genres"] + tags),
                    "tags": [g.lower() for g in m["genres"]] + [t.lower() for t in tags[:10]],
                    "image_url": m["coverImage"]["large"],
                    "popularity_raw": m["popularity"] or 0,
                }
            if not data["pageInfo"]["hasNextPage"]:
                break
            page += 1
            time.sleep(1)  # stay well under AniList's rate limit
