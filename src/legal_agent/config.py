"""Settings and runtime profiles."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://legal:legal@localhost:5440/legal"
    # All app files stay inside the repo: <repo>/data/sc-judgments unless SC_JUDGMENTS_HOME is set.
    sc_judgments_home: Path = Path(__file__).resolve().parents[2] / "data" / "sc-judgments"
