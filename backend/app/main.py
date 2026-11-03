from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import connect, init_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    yield


app = FastAPI(title="WIN API", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    with connect() as conn:
        items = conn.execute("SELECT count(*) FROM items").fetchone()[0]
    return {"status": "ok", "items": items}
