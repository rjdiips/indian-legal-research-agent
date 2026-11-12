"""Package settings: data home and index format version."""

from __future__ import annotations

import os
from pathlib import Path

DATA_HOME_ENV = "SC_JUDGMENTS_HOME"


def data_home() -> Path:
    """Where snapshots and downloads live: `$SC_JUDGMENTS_HOME`, else `~/.local/share/indian-sc-judgments`."""
    configured = os.environ.get(DATA_HOME_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "share" / "indian-sc-judgments"
