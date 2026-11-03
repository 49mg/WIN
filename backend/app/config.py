from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://win:win@localhost:5433/win"
    tmdb_api_key: str = ""
    rawg_api_key: str = ""


settings = Settings()
