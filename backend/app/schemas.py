"""Response models shared by several endpoints."""

from pydantic import BaseModel


class Item(BaseModel):
    id: int
    title: str
    category: str
    year: int | None
    image_url: str | None
    genres: list[str]


class Recommendation(Item):
    description: str | None
    creators: list[str]
    match: int
    reason: str
    ai: bool  # True when the LLM picked/ordered this item and wrote the reason
