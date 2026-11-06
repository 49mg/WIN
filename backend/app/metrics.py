"""Online metrics for the A/B test (WIN-37): how real users react to each arm's picks.

Rates are per impression (a card shown in a list). Each action counts once per card per list,
so toggling 👍 on and off doesn't inflate it. Results are grouped by the user's arm
(intent-to-treat): an "llm" user whose re-ranking failed still counts as "llm".
"""

import math
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.db import connect

router = APIRouter()


class Rate(BaseModel):
    value: float
    low: float  # 95% Wilson interval
    high: float


class ArmStats(BaseModel):
    arm: str
    mode: str
    users: int
    lists: int
    impressions: int
    like_rate: Rate
    dislike_rate: Rate
    queue_rate: Rate
    positive_rate: Rate  # 👍 or queued


class LlmDay(BaseModel):
    day: date
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float  # estimate from settings.llm_price_*


class LlmUsage(BaseModel):
    daily_cap: int
    calls_today: int
    cost_today_usd: float
    last_7_days: list[LlmDay]


class Metrics(BaseModel):
    users_per_arm: dict[str, int]
    results: list[ArmStats]
    llm: LlmUsage


def wilson(hits: int, n: int, z: float = 1.96) -> Rate:
    if n == 0:
        return Rate(value=0.0, low=0.0, high=0.0)
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return Rate(value=p, low=max(0.0, centre - half), high=min(1.0, centre + half))


QUERY = """
WITH acts AS (  -- one row per card shown, with what happened to it
    SELECT u.arm, e.mode, e.user_id, e.list_id, e.item_id,
           bool_or(e.event = 'like') AS liked, bool_or(e.event = 'dislike') AS disliked,
           bool_or(e.event = 'queue') AS queued
    FROM events e JOIN users u ON u.id = e.user_id
    GROUP BY u.arm, e.mode, e.user_id, e.list_id, e.item_id
    HAVING bool_or(e.event = 'impression')
)
SELECT arm, mode, count(DISTINCT user_id), count(DISTINCT list_id), count(*),
       count(*) FILTER (WHERE liked), count(*) FILTER (WHERE disliked),
       count(*) FILTER (WHERE queued), count(*) FILTER (WHERE liked OR queued)
FROM acts GROUP BY arm, mode ORDER BY arm, mode
"""


@router.get("/metrics", response_model=Metrics)
def metrics():
    with connect() as conn:
        rows = conn.execute(QUERY).fetchall()
        per_arm = dict(conn.execute("SELECT arm, count(*) FROM users GROUP BY arm").fetchall())
        usage = conn.execute(
            "SELECT day, calls, input_tokens, output_tokens FROM llm_usage "
            "WHERE day > current_date - 7 ORDER BY day DESC").fetchall()
        db_today = conn.execute("SELECT current_date").fetchone()[0]  # the day the cap counts
    days = [LlmDay(day=d, calls=c, input_tokens=i, output_tokens=o,
                   cost_usd=round(i / 1e6 * settings.llm_price_in_per_m
                                  + o / 1e6 * settings.llm_price_out_per_m, 4))
            for d, c, i, o in usage]
    today = next((d for d in days if d.day == db_today), None)
    return Metrics(
        users_per_arm=per_arm,
        results=[ArmStats(arm=arm, mode=mode, users=users, lists=lists, impressions=n,
                          like_rate=wilson(likes, n), dislike_rate=wilson(dislikes, n),
                          queue_rate=wilson(queues, n), positive_rate=wilson(pos, n))
                 for arm, mode, users, lists, n, likes, dislikes, queues, pos in rows],
        llm=LlmUsage(daily_cap=settings.llm_daily_cap, calls_today=today.calls if today else 0,
                     cost_today_usd=today.cost_usd if today else 0.0, last_7_days=days),
    )
