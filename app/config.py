from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from psycopg.conninfo import make_conninfo


class Settings(BaseSettings):
    app_name: str = "Ali Raza Enterprises ERP"
    app_environment: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    session_signing_key: str = ""
    database_host: str = "127.0.0.1"
    database_port: int = 5432
    database_name: str = "ali_raza_erp"
    database_user: str = "postgres"
    database_password: str = ""
    database_sslmode: str = "prefer"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self):
        if len(self.session_signing_key.strip()) < 32:
            raise ValueError(
                "SESSION_SIGNING_KEY must contain at least 32 non-whitespace characters."
            )

        if self.app_environment.strip().lower() == "production":
            if self.database_user.strip().lower() == "postgres":
                raise ValueError(
                    "Production must use a restricted application database role, not postgres."
                )
            if not self.database_password:
                raise ValueError(
                    "DATABASE_PASSWORD is required in production."
                )

        return self

    @property
    def database_dsn(self) -> str:
        # Let psycopg safely quote connection parameters, including passwords
        # containing spaces, quotes, #, @, %, or other special characters.
        return make_conninfo(
            host=self.database_host,
            port=self.database_port,
            dbname=self.database_name,
            user=self.database_user,
            password=self.database_password,
            sslmode=self.database_sslmode,
            connect_timeout=3,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
