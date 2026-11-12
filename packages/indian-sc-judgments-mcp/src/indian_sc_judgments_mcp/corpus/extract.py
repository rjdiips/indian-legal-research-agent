"""Stream a year's English tar to raw text files, one per Judgment (Day 2).

The tar is read once, front to back (`tarfile` stream mode), so a 500 MB tar is never
unpacked to disk. Entries are matched to Judgments through the year's `english.index.json`:
an entry named `<path>_EN.pdf` belongs to the Judgment with that `path`. Entries not in the
index are skipped and reported; index names never seen in the tar are reported too.

Raw text lands at `<data_home>/text/raw/<path>.txt` (UTF-8, pages separated by `\\f`),
written atomically. An unreadable PDF gives a result with `error` set and no file, and the
run continues.

Storage-agnostic (ADR-0001): yields results; the caller persists hashes and Text quality.
"""

from __future__ import annotations

import json
import os
import tarfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from indian_sc_judgments_mcp.corpus.fetch import english_tar_keys, local_path
from indian_sc_judgments_mcp.corpus.raw_text import TextQuality, UnreadablePdf, extract_raw_text

PDF_SUFFIX = "_EN.pdf"


def raw_text_path(data_home: Path, path: str) -> Path:
    """Where a Judgment's raw text file is kept."""
    return Path(data_home) / "text" / "raw" / f"{path}.txt"


def indexed_pdf_names(index_path: Path) -> list[str]:
    """Every PDF name an `english.index.json` lists, across all its parts, in order."""
    index = json.loads(Path(index_path).read_text())
    return [name for part in index.get("parts", []) for name in part.get("files", [])]


@dataclass(frozen=True)
class Extracted:
    path: str  # the Judgment's `path`
    sha256: str | None  # of the raw text; None on error
    text_quality: TextQuality | None
    pages: int | None
    scanned_pages: int | None
    raw_text_path: Path | None
    error: str | None = None


class TarExtraction:
    """One pass over a tar. Iterate `results`; `missing_from_tar` and `unindexed` are complete
    once it is exhausted."""

    def __init__(self, tar_path: Path, index_path: Path, data_home: Path) -> None:
        self.tar_path = Path(tar_path)
        self.data_home = Path(data_home)
        self._indexed = indexed_pdf_names(index_path)
        self.missing_from_tar: list[str] = []
        self.unindexed: list[str] = []
        self.results: Iterator[Extracted] = self._run()

    def _run(self) -> Iterator[Extracted]:
        wanted = set(self._indexed)
        seen: set[str] = set()
        with tarfile.open(self.tar_path, mode="r|") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                name = os.path.basename(member.name)
                if name not in wanted or not name.endswith(PDF_SUFFIX):
                    self.unindexed.append(member.name)
                    continue
                if name in seen:
                    continue
                seen.add(name)
                handle = tar.extractfile(member)
                data = handle.read() if handle else b""
                yield self._extract(name.removesuffix(PDF_SUFFIX), data)
        self.missing_from_tar = [n for n in self._indexed if n not in seen]

    def _extract(self, path: str, pdf: bytes) -> Extracted:
        try:
            raw = extract_raw_text(pdf)
        except UnreadablePdf as exc:
            return Extracted(path, None, None, None, None, None, error=str(exc) or "unreadable PDF")
        dest = raw_text_path(self.data_home, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(raw.text.encode("utf-8"))
        tmp.replace(dest)
        return Extracted(path, raw.sha256, raw.text_quality, raw.pages, raw.scanned_pages, dest)


def extract_tar(tar_path: Path, index_path: Path, *, data_home: Path) -> TarExtraction:
    return TarExtraction(tar_path, index_path, data_home)


def extract_year(data_home: Path, year: int) -> TarExtraction:
    """Extract one Reporter year's downloaded English tar (see `fetch.fetch_corpus`)."""
    index_key, tar_key = english_tar_keys(year)
    return TarExtraction(local_path(data_home, tar_key), local_path(data_home, index_key), data_home)
