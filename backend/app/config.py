from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API / networking
    mock_api_base_url: str = Field(default="http://localhost:8001")
    api_timeout_seconds: float = Field(default=2.0, ge=0.1, le=60.0)

    # Paths
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "data")
    db_path: Optional[Path] = None
    audit_log_path: Optional[Path] = None

    # Trust computation
    pagerank_iterations: int = Field(default=30, ge=1, le=500)
    pagerank_damping: float = Field(default=0.85, ge=0.0, le=1.0)
    pagerank_tolerance: float = Field(default=1e-8, ge=0.0)
    trust_cache_ttl_seconds: float = Field(default=300.0, ge=1.0, le=3600.0)

    # Query limits
    max_query_length: int = Field(default=1000, ge=10, le=50_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DATA_ECONOMY_",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if self.db_path is None:
            self.db_path = self.data_dir / "warehouse.db"
        if self.audit_log_path is None:
            self.audit_log_path = self.data_dir / "audit_log.jsonl"


settings = Settings()

