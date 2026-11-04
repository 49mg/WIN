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


settings = Settings()
