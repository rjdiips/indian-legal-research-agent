import datetime as dt
from pathlib import Path

from indian_sc_judgments_mcp.corpus.loader import ATTRIBUTION, LICENSE, load_judgments

TINY = Path(__file__).parent / "fixtures" / "metadata_tiny.parquet"
SOURCE = "https://indian-supreme-court-judgments.s3.amazonaws.com/metadata/parquet/year=2020/metadata.parquet"


def _load():
    return load_judgments(TINY, snapshot_id="snap-1", source_uri=SOURCE)


def test_repeated_path_produces_one_judgment_from_the_latest_scrape():
    result = _load()

    paths = [j.path for j in result.judgments]
    assert sorted(paths) == ["2020_1_10_20", "2020_2_30_40", "2020_3_50_60", "2020_4_552_564", "2020_5_70_80"]
    assert result.rows_read == 6
    assert result.duplicates == 1
    a = next(j for j in result.judgments if j.path == "2020_4_552_564")
    assert a.title == "A v. State"


def test_decision_date_comes_only_from_decision_date_never_the_reporter_year():
    b = next(j for j in _load().judgments if j.path == "2020_1_10_20")

    assert b.decision_date == dt.date(2019, 11, 27)
    assert b.reporter_year == 2020


def test_missing_and_bad_decision_dates_are_counted_and_kept():
    result = _load()

    assert result.missing_dates == ["2020_2_30_40"]
    assert result.bad_dates == {"2020_3_50_60": "31-02-2020", "2020_5_70_80": "sometime in 2020"}
    undated = {j.path for j in result.judgments if j.decision_date is None}
    assert undated == {"2020_2_30_40", "2020_3_50_60", "2020_5_70_80"}


def test_every_judgment_carries_snapshot_source_and_attribution():
    for j in _load().judgments:
        assert j.snapshot_id == "snap-1"
        assert j.source_uri == SOURCE
        assert j.license == LICENSE == "CC-BY-4.0"
        assert j.attribution == ATTRIBUTION
        assert "CC-BY-4.0" in ATTRIBUTION
