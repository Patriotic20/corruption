from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token_client: str = ""
    bot_token_admin: str = ""
    postgres_dsn: str = "postgresql+asyncpg://corruption:secret@localhost:5432/corruption"
    redis_url: str = "redis://localhost:6379/0"
    # super-admins (owners), comma-separated, e.g. "123456789,987654321".
    # Ordinary admins are added from the bot itself via /add_admin.
    admin_ids: str = ""
    admin_invite_ttl_days: int = 7

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]


settings = Settings()
