from functools import lru_cache
from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: PostgresDsn
    cors_origins: list[str] = []
    docs_enabled: bool = False
    # Админка /admin включается, только если заданы пароль и секрет для cookie сессии.
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    admin_secret_key: SecretStr | None = None
    admin_secure_cookie: bool = True

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password and self.admin_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
