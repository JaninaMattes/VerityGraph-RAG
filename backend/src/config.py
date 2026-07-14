from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    debug: bool = True
    api_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env")
