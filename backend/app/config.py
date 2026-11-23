"""Ilova sozlamalari. Barcha qiymatlar muhit o'zgaruvchilaridan (CLPE_*) o'qiladi."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLPE_", env_file=".env", extra="ignore")

    app_name: str = "CLPE"
    environment: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'clpe.db'}"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production-please-32b"
    flag_pepper: str = "change-me-flag-pepper"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cors_origins: list[str] = ["http://localhost:5173", "tauri://localhost", "http://tauri.localhost"]

    # Lab Engine
    lab_provider: str = "mock"  # mock | docker | virtualbox | libvirt
    use_celery: bool = False
    labs_dir: Path = BASE_DIR / "labs"
    content_dir: Path = BASE_DIR / "content"
    catalog_file: Path = BASE_DIR / "catalog" / "machine_templates.yaml"
    lab_subnet_pool: str = "10.200.0.0/16"
    max_active_labs_per_user: int = 2
    allow_internet_labs: bool = False  # 9.6: internet default holatda yopiq

    seed_admin_email: str = "admin@clpe.local"
    seed_admin_password: str = "Admin12345!"


@lru_cache
def get_settings() -> Settings:
    return Settings()
