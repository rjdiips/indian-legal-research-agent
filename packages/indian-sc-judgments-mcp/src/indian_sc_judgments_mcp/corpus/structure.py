"""Cleaned text, Pinpoint paragraphs and Bench size for one Judgment, from its raw text file (Day 2).

Reads `<data_home>/text/raw/<path>.txt` (see `extract.py`), writes the cleaned text to
`<data_home>/text/clean/<path>.txt` (UTF-8) and its offset map back to raw to
`<data_home>/text/clean/<path>.map.json`, both atomically, and returns the paragraphs and Bench
size. Storage-agnostic (ADR-0001): the caller persists the hashes, paragraphs and Bench size.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from indian_sc_judgments_mcp.corpus.clean import clean_text
from indian_sc_judgments_mcp.corpus.extract import raw_text_path
from indian_sc_judgments_mcp.corpus.parse import Bench, Paragraph, bench_size, paragraphs


def clean_text_path(data_home: Path, path: str) -> Path:
    return Path(data_home) / "text" / "clean" / f"{path}.txt"


def offset_map_path(data_home: Path, path: str) -> Path:
    return Path(data_home) / "text" / "clean" / f"{path}.map.json"


@dataclass(frozen=True)
class Structured:
    path: str
    clean_sha256: str | None  # of the cleaned text file; None on error
    bench: Bench | None
    paragraphs: list[Paragraph] = field(default_factory=list)
    clean_text_path: Path | None = None
    error: str | None = None


def structure_judgment(data_home: Path, path: str, raw_sha256: str | None = None) -> Structured:
    """Clean one Judgment's raw text and parse it. With `raw_sha256` (from extraction), a raw
    file whose bytes no longer match is an error rather than cleaned."""
    source = raw_text_path(data_home, path)
    try:
        data = source.read_bytes()
    except FileNotFoundError:
        return Structured(path, None, None, error=f"no raw text at {source}")
    if raw_sha256 is not None and hashlib.sha256(data).hexdigest() != raw_sha256:
        return Structured(path, None, None, error="raw text changed since extraction; rerun extract-text")

    cleaned = clean_text(data.decode("utf-8"), path=path)
    dest = clean_text_path(data_home, path)
    _write(dest, cleaned.text.encode("utf-8"))
    _write(offset_map_path(data_home, path), cleaned.offset_map_json().encode("utf-8"))
    return Structured(
        path,
        cleaned.sha256,
        bench_size(cleaned.text[: cleaned.page_end(0)]),
        paragraphs(cleaned.text),
        dest,
    )


def _write(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
