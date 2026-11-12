"""Regenerate english_mini.tar and english_mini.index.json: a few gate-sample PDFs in the bucket's
English tar layout (flat `<path>_EN.pdf` entries), plus one unreadable entry.

Run: uv run python packages/indian-sc-judgments-mcp/tests/fixtures/make_mini_tar.py [GATE_PDF_DIR]
GATE_PDF_DIR defaults to project-prds/data-gates/raw/legal/pdf_main next to this repo.
"""

import io
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_GATE = HERE.parents[5] / "project-prds" / "data-gates" / "raw" / "legal" / "pdf_main"

# Known structure (checked page by page: one full-page image under render-mode-3 text, or none).
PDFS = [
    "S_1996_4_314_315_EN.pdf",  # scanned, 1996, 2 pages
    "S_2003_2_63_65_EN.pdf",  # scanned, 2003, 3 pages
    "2017_7_348_348_EN.pdf",  # scanned, 2017, 1 page (scans run past 2010)
    "2024_4_598_605_EN.pdf",  # born-digital, 2024, 8 pages
]
UNREADABLE = "2099_1_1_1_EN.pdf"  # not a PDF at all
MISSING = "2099_1_2_2_EN.pdf"  # listed in the index, absent from the tar


def _add(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 1768411020  # fixed, so the fixture is byte-stable
    info.mode = 0o664
    tar.addfile(info, io.BytesIO(data))


def main(gate: Path) -> None:
    with tarfile.open(HERE / "english_mini.tar", "w", format=tarfile.USTAR_FORMAT) as tar:
        for name in PDFS:
            _add(tar, name, (gate / name).read_bytes())
        _add(tar, UNREADABLE, b"this is not a pdf\n" * 4)
        _add(tar, "README.txt", b"not listed in the index\n")
    files = [*PDFS, UNREADABLE, MISSING]
    index = {
        "year": 2099,
        "archive_type": "english",
        "file_count": len(files),
        "parts": [{"name": "english.tar", "files": files, "file_count": len(files)}],
    }
    (HERE / "english_mini.index.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GATE)
