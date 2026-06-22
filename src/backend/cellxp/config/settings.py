from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    product_name: str = "CellXP"
    environment: str = "development"
    runtime_backend: str = "local"
    database_url: str = "sqlite:///./.cellxp/runtime.db"
    redis_url: str = "redis://localhost:6379/0"
    object_store_url: str = "file:///tmp/cellxp-artifacts"
    job_stream: str = "cellxp:jobs"
    job_consumer_group: str = "cellxp-workers"
    graph_job_stream: str = "cellxp:graph-commands"
    graph_consumer_group: str = "cellxp-graph-executors"

    def prepare_local_paths(self) -> None:
        """Create parent directories needed by configured local durable backends."""
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(
                parents=True, exist_ok=True
            )
