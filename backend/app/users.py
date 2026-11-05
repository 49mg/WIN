"""Anonymous accounts: what a user loved, their 👍/👎 and their Next queue, stored on the server.

POST /users gives a new random id. The browser keeps it and sends it as the X-User-Id
header. There is no password, so the id is the only key to the data: treat it like a
private link.
"""

import random
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.db import connect

router = APIRouter()

ITEM_COLS = "i.id, i.title, i.category, i.year, i.image_url, i.genres"
ITEM_KEYS = ("id", "title", "category", "year", "image_url", "genres")


class ItemOut(BaseModel):
    id: int
    title: str
    category: str
    year: int | None
    image_url: str | None
    genres: list[str]


class FeedbackOut(BaseModel):
    item: ItemOut
    liked: bool


class QueueOut(BaseModel):
    item: ItemOut
    done: bool


class UserData(BaseModel):
    id: UUID
    arm: str  # A/B test group: "llm" (engine + LLM re-ranking) or "engine" (holdout)
    liked: list[ItemOut]
    feedback: list[FeedbackOut]
    queue: list[QueueOut]


class LikedIn(BaseModel):
    item_ids: list[int] = Field(max_length=50)


class VoteIn(BaseModel):
    liked: bool


class QueueIn(BaseModel):
    item_id: int


class DoneIn(BaseModel):
    done: bool


def current_user(x_user_id: Annotated[UUID, Header()]) -> UUID:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id = %s", (x_user_id,)).fetchone():
            raise HTTPException(401, "Unknown user id. Create one with POST /users.")
    return x_user_id


User = Annotated[UUID, Depends(current_user)]


def _item(row) -> ItemOut:
    return ItemOut(**dict(zip(ITEM_KEYS, row, strict=True)))


def _check_items(conn, ids: list[int]) -> None:
    found = {r[0] for r in conn.execute("SELECT id FROM items WHERE id = ANY(%s)", (ids,))}
    missing = sorted(set(ids) - found)
    if missing:
        raise HTTPException(404, f"Unknown item ids: {missing}")


def load_user(user: UUID) -> UserData:
    with connect() as conn:
        arm = conn.execute("SELECT arm FROM users WHERE id = %s", (user,)).fetchone()[0]
        liked = conn.execute(
            f"SELECT {ITEM_COLS} FROM liked l JOIN items i ON i.id = l.item_id "
            "WHERE l.user_id = %s ORDER BY l.position", (user,)).fetchall()
        feedback = conn.execute(
            f"SELECT {ITEM_COLS}, f.liked FROM feedback f JOIN items i ON i.id = f.item_id "
            "WHERE f.user_id = %s ORDER BY f.created_at", (user,)).fetchall()
        queue = conn.execute(
            f"SELECT {ITEM_COLS}, q.done FROM queue q JOIN items i ON i.id = q.item_id "
            "WHERE q.user_id = %s ORDER BY q.added_at", (user,)).fetchall()
    return UserData(
        id=user,
        arm=arm,
        liked=[_item(r) for r in liked],
        feedback=[FeedbackOut(item=_item(r[:-1]), liked=r[-1]) for r in feedback],
        queue=[QueueOut(item=_item(r[:-1]), done=r[-1]) for r in queue],
    )


@router.post("/users", response_model=UserData, status_code=201)
def create_user():
    with connect() as conn:
        arm = "engine" if random.random() < settings.llm_holdout else "llm"
        user = conn.execute("INSERT INTO users (arm) VALUES (%s) RETURNING id",
                            (arm,)).fetchone()[0]
    return load_user(user)


@router.get("/me", response_model=UserData)
def me(user: User):
    return load_user(user)


@router.put("/me/liked", response_model=UserData)
def set_liked(body: LikedIn, user: User):
    ids = list(dict.fromkeys(body.item_ids))  # drop repeats, keep order
    with connect() as conn:
        _check_items(conn, ids)
        conn.execute("DELETE FROM liked WHERE user_id = %s", (user,))
        conn.cursor().executemany(
            "INSERT INTO liked (user_id, item_id, position) VALUES (%s, %s, %s)",
            [(user, item, pos) for pos, item in enumerate(ids)])
    return load_user(user)


@router.put("/me/feedback/{item_id}", status_code=204)
def vote(item_id: int, body: VoteIn, user: User):
    with connect() as conn:
        _check_items(conn, [item_id])
        conn.execute(
            "INSERT INTO feedback (user_id, item_id, liked) VALUES (%s, %s, %s) "
            "ON CONFLICT (user_id, item_id) DO UPDATE SET liked = EXCLUDED.liked, "
            "created_at = now()", (user, item_id, body.liked))
    return Response(status_code=204)


@router.delete("/me/feedback/{item_id}", status_code=204)
def unvote(item_id: int, user: User):
    with connect() as conn:
        conn.execute("DELETE FROM feedback WHERE user_id = %s AND item_id = %s", (user, item_id))
    return Response(status_code=204)


@router.post("/me/queue", status_code=204)
def add_to_queue(body: QueueIn, user: User):
    with connect() as conn:
        _check_items(conn, [body.item_id])
        conn.execute("INSERT INTO queue (user_id, item_id) VALUES (%s, %s) "
                     "ON CONFLICT DO NOTHING", (user, body.item_id))
    return Response(status_code=204)


@router.patch("/me/queue/{item_id}", status_code=204)
def set_done(item_id: int, body: DoneIn, user: User):
    with connect() as conn:
        updated = conn.execute("UPDATE queue SET done = %s WHERE user_id = %s AND item_id = %s",
                               (body.done, user, item_id)).rowcount
    if not updated:
        raise HTTPException(404, "Item is not in your queue")
    return Response(status_code=204)


@router.delete("/me/queue/{item_id}", status_code=204)
def remove_from_queue(item_id: int, user: User):
    with connect() as conn:
        conn.execute("DELETE FROM queue WHERE user_id = %s AND item_id = %s", (user, item_id))
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def delete_me(user: User):
    """Delete this account and everything saved for it (likes, votes, queue)."""
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = %s", (user,))
    return Response(status_code=204)


class EventIn(BaseModel):
    event: Literal["impression", "like", "dislike", "queue"]
    item_id: int
    list_id: UUID
    mode: Literal["titles", "vibe"]
    source: Literal["engine", "llm"]
    position: int = Field(ge=0, le=100)


class EventsIn(BaseModel):
    events: list[EventIn] = Field(max_length=100)


@router.post("/me/events", status_code=204)
def log_events(body: EventsIn, user: User):
    """What the user was shown and did with it (online metrics, WIN-37)."""
    if body.events:
        with connect() as conn:
            _check_items(conn, list({e.item_id for e in body.events}))
            conn.cursor().executemany(
                "INSERT INTO events (user_id, event, item_id, list_id, mode, source, position) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [(user, e.event, e.item_id, e.list_id, e.mode, e.source, e.position)
                 for e in body.events])
    return Response(status_code=204)
