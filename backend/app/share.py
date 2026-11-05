"""Share codes: a read-only public view of what someone loved, used by Blend mode (WIN-35)
and taste cards (WIN-36). The code never reveals the user id."""

import secrets
from collections import Counter

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import connect
from app.recommend import recommend_blend
from app.schemas import Recommendation
from app.users import ITEM_COLS, ItemOut, User, _item

router = APIRouter()


class ShareCode(BaseModel):
    code: str


class SharedTaste(BaseModel):
    code: str
    liked: list[ItemOut]
    top_genres: list[tuple[str, int]]


class BlendIn(BaseModel):
    code: str
    categories: list[str] = []
    k: int = Field(default=10, ge=1, le=30)


def _taste_ids(conn, user_id) -> list[int]:
    """What a person loved: the items they added plus the picks they gave 👍."""
    rows = conn.execute(
        "SELECT item_id FROM (SELECT item_id, position AS o FROM liked WHERE user_id = %(u)s "
        "UNION ALL SELECT item_id, 1000 AS o FROM feedback WHERE user_id = %(u)s AND liked) t "
        "GROUP BY item_id ORDER BY min(o)", {"u": user_id}).fetchall()
    return [r[0] for r in rows]


def _owner(conn, code: str):
    row = conn.execute("SELECT id FROM users WHERE share_code = %s", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "This share link doesn't exist (anymore).")
    return row[0]


@router.post("/me/share", response_model=ShareCode)
def share(user: User):
    """Create (once) and return this user's read-only share code."""
    with connect() as conn:
        code = conn.execute("SELECT share_code FROM users WHERE id = %s", (user,)).fetchone()[0]
        if not code:
            code = secrets.token_urlsafe(8)
            conn.execute("UPDATE users SET share_code = %s WHERE id = %s", (code, user))
    return ShareCode(code=code)


@router.get("/share/{code}", response_model=SharedTaste)
def shared_taste(code: str):
    with connect() as conn:
        ids = _taste_ids(conn, _owner(conn, code))
        rows = conn.execute(f"SELECT {ITEM_COLS} FROM items i WHERE i.id = ANY(%s)",
                            (ids,)).fetchall()
    by_id = {r[0]: _item(r) for r in rows}
    liked = [by_id[i] for i in ids if i in by_id]
    genres = Counter(g for it in liked for g in it.genres).most_common(6)
    return SharedTaste(code=code, liked=liked, top_genres=genres)


@router.post("/blend", response_model=list[Recommendation])
def blend(body: BlendIn, user: User):
    """Picks for the current user and the owner of `code`, together."""
    with connect() as conn:
        other = _owner(conn, body.code)
        if other == user:
            raise HTTPException(400, "That's your own link. Send it to a friend instead.")
        mine, theirs = _taste_ids(conn, user), _taste_ids(conn, other)
        seen = [r[0] for r in conn.execute(
            "SELECT item_id FROM feedback WHERE user_id = ANY(%s) AND NOT liked "
            "UNION SELECT item_id FROM queue WHERE user_id = %s", ([user, other], user))]
    if not mine or not theirs:
        raise HTTPException(400, "Both people need at least one loved item to blend.")
    return recommend_blend(mine, theirs, seen, body.categories, body.k)
