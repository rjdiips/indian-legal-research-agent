import datetime as dt
import hashlib
import shutil
from pathlib import Path

import pytest

from indian_sc_judgments_mcp.corpus.extract import raw_text_path
from indian_sc_judgments_mcp.corpus.fetch import english_tar_keys, local_path
from indian_sc_judgments_mcp.corpus.loader import Judgment
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot
from legal_agent.db.corpus import save_snapshot, upsert_judgments
from legal_agent.db.migrate import MIGRATIONS_DIR, migrate
from legal_agent.extract import extract_text

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[2] / "packages" / "indian-sc-judgments-mcp" / "tests" / "fixtures"
YEAR = 2099
PATHS = ["S_1996_4_314_315", "S_2003_2_63_65", "2017_7_348_348", "2024_4_598_605", "2099_1_1_1"]


def _judgment(path: str, snapshot_id: str) -> Judgment:
    fields = dict.fromkeys(
        ["title", "petitioner", "respondent", "description", "judge", "author_judge", "citation", "case_id",
         "cnr", "disposal_nature", "court", "available_languages", "nc_display", "scraped_at"],
    )  # fmt: skip
    return Judgment(
        path=path, decision_date=dt.date(2000, 1, 1), reporter_year=YEAR,
        snapshot_id=snapshot_id, source_uri="fixture", **fields,
    )  # fmt: skip


@pytest.fixture
def corpus(conn, tmp_path):
    """A migrated store holding the mini tar's Judgments (all but one), and the tar in the data home."""
    migrate(conn, MIGRATIONS_DIR)
    snapshot = Snapshot.from_listing([])
    save_snapshot(conn, snapshot, {})
    upsert_judgments(conn, [_judgment(p, snapshot.snapshot_id) for p in PATHS if p != "S_2003_2_63_65"])
    index_key, tar_key = english_tar_keys(YEAR)
    files = [(FIXTURES / "english_mini.index.json", index_key), (FIXTURES / "english_mini.tar", tar_key)]
    for src, key in files:
        local_path(tmp_path, key).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, local_path(tmp_path, key))
    return tmp_path


def _rows(conn):
    rows = conn.execute(
        "SELECT path, raw_text_sha256, text_quality, page_count, scanned_pages, text_error,"
        " text_extracted_at IS NOT NULL FROM judgments"
    ).fetchall()
    return {r[0]: r[1:] for r in rows}


def test_each_judgment_gets_its_raw_text_hash_and_text_quality(conn, corpus):
    extract_text(conn, data_home=corpus, years=[YEAR])

    rows = _rows(conn)
    sha, quality, pages, scanned, error, stamped = rows["2024_4_598_605"]
    assert (quality, pages, scanned, error, stamped) == ("born_digital", 8, 0, None, True)
    assert sha == hashlib.sha256(raw_text_path(corpus, "2024_4_598_605").read_bytes()).hexdigest()
    assert rows["S_1996_4_314_315"][1:4] == ("ocr", 2, 2)
    assert rows["2017_7_348_348"][1] == "ocr"


def test_an_unreadable_pdf_is_an_error_on_its_judgment_and_the_rest_still_load(conn, corpus):
    report = extract_text(conn, data_home=corpus, years=[YEAR])

    sha, quality, _, _, error, stamped = _rows(conn)["2099_1_1_1"]
    assert (sha, quality, stamped) == (None, None, True)
    assert error
    assert report.counts == {
        "extracted": 4, "errors": 1, "ocr": 3, "born_digital": 1,
        "without_judgment": 1, "missing_from_tar": 1, "unindexed": 1,
    }  # fmt: skip
    assert report.without_judgment == ["S_2003_2_63_65"]


def test_rerunning_gives_the_same_hashes(conn, corpus):
    extract_text(conn, data_home=corpus, years=[YEAR])
    first = _rows(conn)

    extract_text(conn, data_home=corpus, years=[YEAR])

    assert {p: r[:5] for p, r in _rows(conn).items()} == {p: r[:5] for p, r in first.items()}
