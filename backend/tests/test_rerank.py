from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import rerank
from app.config import settings


class FakeClient:
    """Stands in for anthropic.Anthropic: returns a fixed ranking or raises an error."""

    def __init__(self, picks=None, error=None, stop_reason="end_turn"):
        self.calls = 0
        parsed = rerank.Ranking(picks=[rerank.Pick(index=i, reason=r) for i, r in picks or []])
        response = SimpleNamespace(stop_reason=stop_reason,
                                   parsed_output=parsed if stop_reason == "end_turn" else None)

        def parse(**kwargs):
            self.calls += 1
            if error:
                raise error
            return response

        self.messages = SimpleNamespace(parse=parse)


@pytest.fixture(autouse=True)
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_rerank", True)
    monkeypatch.setattr(rerank, "_paused_until", 0.0)
    rerank._cache.clear()


def _use(monkeypatch, client):
    monkeypatch.setattr(rerank, "_get_client", lambda: client)
    return client


LIKED = [{"id": 1, "title": "Dune", "category": "book", "year": 1965, "genres": ["sci-fi"],
          "description": "Desert planet politics."}]
CANDS = [{"id": 10 + i, "title": f"Item {i}", "category": "movie", "year": 2000,
          "genres": [], "description": ""} for i in range(5)]


def test_returns_candidates_in_llm_order_with_its_reasons(monkeypatch):
    _use(monkeypatch, FakeClient(picks=[(3, "Desert epic. "), (0, "Politics.")]))
    out = rerank.rerank(LIKED, CANDS, k=2)
    assert [x["id"] for x in out] == [13, 10]
    assert out[0]["reason"] == "Desert epic."


def test_ignores_out_of_range_and_repeated_indices(monkeypatch):
    _use(monkeypatch, FakeClient(picks=[(99, "x"), (2, "a"), (2, "again"), (-1, "y"), (4, "b")]))
    out = rerank.rerank(LIKED, CANDS, k=3)
    assert [x["id"] for x in out] == [12, 14]  # only real, distinct candidates


def test_api_error_falls_back_and_pauses_the_llm(monkeypatch):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.AuthenticationError("invalid x-api-key",
                                        response=httpx.Response(401, request=req), body=None)
    client = _use(monkeypatch, FakeClient(error=err))
    assert rerank.rerank(LIKED, CANDS, k=2) is None
    assert not rerank.enabled()  # paused: the next request skips the LLM entirely
    assert rerank.rerank(LIKED, CANDS, k=2) is None
    assert client.calls == 1


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refusal_or_cut_off_falls_back(monkeypatch, stop_reason):
    _use(monkeypatch, FakeClient(picks=[(1, "a")], stop_reason=stop_reason))
    assert rerank.rerank(LIKED, CANDS, k=2) is None


def test_same_request_is_cached(monkeypatch):
    client = _use(monkeypatch, FakeClient(picks=[(1, "a")]))
    rerank.rerank(LIKED, CANDS, k=1)
    rerank.rerank(LIKED, CANDS, k=1)
    assert client.calls == 1


def test_disabled_without_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    client = _use(monkeypatch, FakeClient(picks=[(1, "a")]))
    assert rerank.rerank(LIKED, CANDS, k=1) is None
    assert client.calls == 0


def test_prompt_lists_liked_items_and_numbered_candidates():
    prompt = rerank.build_prompt(LIKED, CANDS[:2], k=2, vibe=None)
    assert "- Dune (book, 1965) | sci-fi" in prompt
    assert "[0] Item 0 (movie, 2000)" in prompt and "[1] Item 1" in prompt
    assert '"cozy"' in rerank.build_prompt([], CANDS[:1], k=1, vibe="cozy")
