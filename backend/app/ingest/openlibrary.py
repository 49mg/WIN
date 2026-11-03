"""Books from Open Library (free, no key). https://openlibrary.org/developers/api

The search API gives us popular books per subject; descriptions need one extra call per book.
"""

import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.ingest import clean_text, shared_genres

SUBJECTS = ["fantasy", "science_fiction", "mystery", "thriller", "romance", "horror",
            "historical_fiction", "young_adult_fiction", "classics", "adventure", "dystopias",
            "humor", "biography", "philosophy", "self-help", "graphic_novels"]
FIELDS = "key,title,author_name,first_publish_year,cover_i,subject,readinglog_count"
HEADERS = {"User-Agent": "WIN-recommender (portfolio project)"}
# Open Library has a few spam "books" that are really customer-service phone listings.
SPAM = re.compile(r"phone number|customer service|contact guide|support guide|™|®", re.I)


def _description(client: httpx.Client, key: str) -> str | None:
    try:
        d = client.get(f"https://openlibrary.org{key}.json").json().get("description")
    except (httpx.HTTPError, ValueError):
        return None
    return clean_text(d["value"] if isinstance(d, dict) else d)


def fetch(limit: int):
    per_subject = limit // len(SUBJECTS) + 1
    seen: dict[str, dict] = {}
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        for subject in SUBJECTS:
            r = client.get("https://openlibrary.org/search.json", params={
                "q": f"subject:{subject} language:eng", "sort": "readinglog",
                "fields": FIELDS, "limit": per_subject,
            })
            r.raise_for_status()
            for b in r.json()["docs"]:
                if not b.get("readinglog_count") or SPAM.search(b["title"]):
                    continue
                seen.setdefault(b["key"], {**b, "found_in": []})["found_in"].append(subject)
            print(f"  {subject}: {len(seen)} books so far")

        books = list(seen.values())[:limit]
        with ThreadPoolExecutor(4) as pool:  # be polite: Open Library is a free service
            descriptions = list(pool.map(lambda b: _description(client, b["key"]), books))

    for b, desc in zip(books, descriptions, strict=True):
        subjects = [s for s in b.get("subject", []) if ":" not in s and len(s) < 40]
        yield {
            "category": "book",
            "source": "openlibrary",
            "source_id": b["key"].removeprefix("/works/"),
            "title": b["title"],
            "year": b.get("first_publish_year"),
            "description": desc,
            "creators": b.get("author_name", [])[:3],
            # subject lists are long and noisy, so trust the search that found the book
            # plus only its first few subjects
            "genres": shared_genres([f.replace("_", " ") for f in b["found_in"]] + subjects[:10]),
            "tags": [s.lower() for s in subjects[:12]],
            "image_url": f"https://covers.openlibrary.org/b/id/{b['cover_i']}-M.jpg"
            if b.get("cover_i") else None,
            "popularity_raw": b["readinglog_count"],
        }
