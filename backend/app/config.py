from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://win:win@localhost:5433/win"
    tmdb_api_key: str = ""
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    # score = cosine similarity + pop_weight * popularity. 0.3 chosen on MovieLens:
    # 84% of the best NDCG@10 with ~2x the catalog coverage of 0.5 (see app/recommend.py).
    pop_weight: float = 0.3
    cors_origins: list[str] = ["http://localhost:3000"]
    # LLM re-ranking (app/rerank.py); off automatically when no key is set
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    llm_rerank: bool = True
    # A/B test (WIN-37): share of new users who get the engine only, without LLM re-ranking
    llm_holdout: float = 0.3
    # Cost protection: the LLM is paid per call with the owner's key
    llm_daily_cap: int = 1000  # LLM re-rank calls per day (all users); then the engine only
    llm_price_in_per_m: float = 0.10  # USD per million input tokens (Claude Haiku 5.5)
    llm_price_out_per_m: float = 0.50  # USD per million output tokens
    rate_limit_per_minute: int = 20  # recommendation lists per user (or IP) per minute


settings = Settings()
