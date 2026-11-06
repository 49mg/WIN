"""LLM re-ranking: Claude (Haiku 5.5 by default) picks and orders the best picks
from the engine's candidates and writes the reason for each.

The engine (app/recommend.py) does retrieval: it finds ~30 real candidates from our own
catalog. The LLM only chooses among them, by index, through structured output, so it can't
invent titles or return items we can't show. Any failure returns None and the caller
falls back to the engine's own picks and rule-based reasons.
"""

import logging
import time
from collections import OrderedDict

import anthropic
from pydantic import BaseModel

from app.config import settings
from app.db import connect

log = logging.getLogger(__name__)

SYSTEM = """You are the recommendation editor for WIN, an app that suggests what to watch, \
read or play next across movies, TV shows, books, games and anime.

You get the things the user loved and a numbered list of candidates that a retrieval \
engine already found in our catalog. Choose the candidates this person is most likely to \
enjoy next and put the best first.

How to judge:
- Match what the user's items are actually about: story, themes, tone, setting, pacing. \
Similar title words mean nothing ("The Last of Us" and "The Wolf Among Us" are unrelated).
- Prefer variety across categories when candidates are equally good.
- Skip other editions, adaptations or direct sequels of something the user already listed; \
a different work by the same creator is fine.

For each pick write one sentence (max 20 words) saying why this user would enjoy it. Name \
the liked item it connects to and the concrete shared quality. Write plainly, no hype, no \
"you'll love"."""


class Pick(BaseModel):
    index: int
    reason: str


class Ranking(BaseModel):
    picks: list[Pick]


_client: anthropic.Anthropic | None = None
_cache: OrderedDict[tuple, list[Pick]] = OrderedDict()
CACHE_SIZE = 512
# After a failure, skip the LLM for a while so every request doesn't wait on a broken call.
_paused_until = 0.0
PAUSE_PERMANENT = 600  # bad key / no credits: won't fix itself soon
PAUSE_TRANSIENT = 60  # timeouts, rate limits, server errors


def enabled() -> bool:
    return bool(settings.anthropic_api_key) and settings.llm_rerank and time.time() >= _paused_until


def _pause(e: Exception) -> None:
    global _paused_until
    # bad key, no access, or a request the API rejects (e.g. "credit balance is too low")
    permanent = isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                               anthropic.BadRequestError))
    seconds = PAUSE_PERMANENT if permanent else PAUSE_TRANSIENT
    _paused_until = time.time() + seconds
    log.warning("rerank failed, LLM paused for %ss: %s", seconds, e)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # short timeout + one retry: a slow LLM should never block recommendations for long
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=20.0,
                                      max_retries=1)
    return _client


def _describe(it: dict, n: int | None = None) -> str:
    head = f"[{n}] " if n is not None else "- "
    year = f", {it['year']}" if it.get("year") else ""
    genres = f" | {', '.join(it['genres'][:4])}" if it.get("genres") else ""
    desc = (it.get("description") or "").replace("\n", " ")[:280]
    return f"{head}{it['title']} ({it['category']}{year}){genres}\n    {desc}"


def build_prompt(liked: list[dict], candidates: list[dict], k: int, vibe: str | None) -> str:
    if vibe:
        wanted = f"The user described the mood they want:\n\"{vibe}\""
    else:
        wanted = "The user loved:\n" + "\n".join(_describe(x) for x in liked)
    cands = "\n".join(_describe(c, i) for i, c in enumerate(candidates))
    return (f"{wanted}\n\nCandidates:\n{cands}\n\n"
            f"Return the {k} best candidates by index, best first, each with its reason.")


def rerank(liked: list[dict], candidates: list[dict], k: int,
           vibe: str | None = None) -> list[dict] | None:
    """Return up to k candidates in the LLM's order with `reason` set, or None on failure."""
    if not enabled() or not candidates:
        return None
    key = (tuple(x["id"] for x in liked), vibe, tuple(c["id"] for c in candidates), k)
    picks = _cache.get(key)
    if picks is None:
        if calls_today() >= settings.llm_daily_cap:
            log.warning("rerank skipped: daily cap of %s LLM calls reached", settings.llm_daily_cap)
            return None
        try:
            resp = _get_client().messages.parse(
                model=settings.llm_model,
                max_tokens=4000,
                system=SYSTEM,
                output_config={"effort": "low"},  # choosing among 30 items needs little thinking
                messages=[{"role": "user",
                           "content": build_prompt(liked, candidates, k, vibe)}],
                output_format=Ranking,
            )
        except anthropic.APIError as e:  # timeouts, rate limits, 5xx, bad key: fall back
            _pause(e)
            return None
        record_usage(resp.usage.input_tokens, resp.usage.output_tokens)  # billed even if unusable
        # "refusal" (safety decline) or "max_tokens" (cut off): use the engine's picks instead
        if resp.stop_reason != "end_turn" or resp.parsed_output is None:
            log.warning("rerank unusable: stop_reason=%s", resp.stop_reason)
            return None
        picks = resp.parsed_output.picks
        _cache[key] = picks
        if len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)

    out, seen = [], set()
    for p in picks:
        if 0 <= p.index < len(candidates) and p.index not in seen:
            seen.add(p.index)
            out.append({**candidates[p.index], "reason": p.reason.strip()})
        if len(out) == k:
            break
    return out or None


# ---- cost protection: a daily cap on LLM calls, counted in the database ----

def calls_today() -> int:
    with connect() as conn:
        row = conn.execute("SELECT calls FROM llm_usage WHERE day = current_date").fetchone()
    return row[0] if row else 0


def record_usage(input_tokens: int, output_tokens: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO llm_usage (day, calls, input_tokens, output_tokens) "
            "VALUES (current_date, 1, %s, %s) ON CONFLICT (day) DO UPDATE SET "
            "calls = llm_usage.calls + 1, input_tokens = llm_usage.input_tokens + %s, "
            "output_tokens = llm_usage.output_tokens + %s",
            (input_tokens, output_tokens, input_tokens, output_tokens),
        )
