import argparse
import importlib
import time

from app.db import init_schema
from app.ingest import save

SOURCES = ["anilist", "openlibrary", "tmdb", "igdb"]

parser = argparse.ArgumentParser(description="Import items into the WIN database.")
parser.add_argument("source", choices=SOURCES)
parser.add_argument("--limit", type=int, default=2000)
args = parser.parse_args()

init_schema()
t0 = time.perf_counter()
module = importlib.import_module(f"app.ingest.{args.source}")
n = save(module.fetch(args.limit))
print(f"{args.source}: saved {n} items in {time.perf_counter() - t0:.0f}s")
