from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/poker_banker"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if (
            self.SECRET_KEY == _DEFAULT_SECRET_KEY
            and "sqlite" not in self.DATABASE_URL
        ):
            raise ValueError(
                "SECRET_KEY must be changed from the default value in production. "
                "Set a strong SECRET_KEY when using a non-SQLite DATABASE_URL."
            )
        return self


settings = Settings()
