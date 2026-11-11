"""Settings and runtime profiles."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://legal:legal@localhost:5440/legal"
    # Unset: the package data home ($SC_JUDGMENTS_HOME or ~/.local/share/indian-sc-judgments).
    sc_judgments_home: Path | None = None
