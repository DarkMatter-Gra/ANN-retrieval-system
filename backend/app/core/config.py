from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ANN Retrieval Backend"
    app_env: str = "dev"
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 3

    database_url: str = "sqlite:///./ann_system.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_always_eager: bool = False

    data_dir: str = "../data"
    index_dir: str = "../indices"
    report_dir: str = "../reports"
    export_dir: str = "../exports"

    upload_chunk_size: int = 4 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @property
    def index_path(self) -> Path:
        return Path(self.index_dir).resolve()

    @property
    def report_path(self) -> Path:
        return Path(self.report_dir).resolve()

    @property
    def export_path(self) -> Path:
        return Path(self.export_dir).resolve()


settings = Settings()

# 启动时确保关键目录存在
for _path in (
    settings.data_path,
    settings.index_path,
    settings.report_path,
    settings.export_path,
):
    _path.mkdir(parents=True, exist_ok=True)
(settings.data_path / "raw").mkdir(parents=True, exist_ok=True)
(settings.data_path / "processed").mkdir(parents=True, exist_ok=True)
