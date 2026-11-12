import json
from pathlib import Path

import pytest
from fake_bucket import FakeBucket

from indian_sc_judgments_mcp.corpus.download import Pacer
from indian_sc_judgments_mcp.corpus.fetch import english_tar_keys, fetch_corpus, tar_year

FIXTURES = Path(__file__).parent / "fixtures"
BUCKET_URL = "https://indian-supreme-court-judgments.s3.amazonaws.com/"
META_2020 = "metadata/parquet/year=2020/metadata.parquet"
META_2021 = "metadata/parquet/year=2021/metadata.parquet"


def _tar(year: int) -> dict[str, bytes]:
    index = {"year": year, "archive_type": "english", "parts": [{"name": "english.tar", "files": []}]}
    return {
        f"data/tar/year={year}/english/english.tar": f"english tar {year}".encode() * 50,
        f"data/tar/year={year}/english/english.index.json": json.dumps(index).encode(),
        f"data/tar/year={year}/regional/regional.tar": b"regional, never fetched",
        f"data/tar/year={year}/regional/regional.index.json": b"{}",
    }


def bucket() -> FakeBucket:
    return FakeBucket(
        {
            META_2020: (FIXTURES / "metadata_tiny.parquet").read_bytes(),
            META_2021: (FIXTURES / "metadata_tiny_2021.parquet").read_bytes(),
            **_tar(2020),
            **_tar(2021),
        }
    )


def _fetch(b: FakeBucket, home: Path, tar_years):
    return fetch_corpus(client=b.client(), data_home=home, tar_years=tar_years, pacer=Pacer(0))


def test_all_metadata_and_the_chosen_years_english_tars_make_one_snapshot(tmp_path):
    b = bucket()

    run = _fetch(b, tmp_path, [2021])

    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["snapshot_id"] == run.snapshot.snapshot_id
    assert {o["key"] for o in manifest["objects"]} == {
        META_2020,
        META_2021,
        "data/tar/year=2021/english/english.tar",
        "data/tar/year=2021/english/english.index.json",
    }
    tar = next(o for o in manifest["objects"] if o["key"].endswith("2021/english/english.tar"))
    assert tar == {"key": tar["key"], "size": 800, "etag": b.etag(tar["key"])}
    for o in manifest["objects"]:
        assert (tmp_path / "raw" / o["key"]).read_bytes() == b.objects[o["key"]]


def test_a_path_repeated_across_years_is_one_judgment(tmp_path):
    run = _fetch(bucket(), tmp_path, [])

    assert run.load.counts()["rows_read"] == 8
    assert run.load.counts()["duplicates"] == 2
    assert len(run.load.judgments) == 6
    a = next(j for j in run.load.judgments if j.path == "2020_4_552_564")
    assert (a.title, a.reporter_year) == ("A v. State (2021 volume)", 2021)  # the later scrape
    assert a.source_uri == BUCKET_URL + META_2021
    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["dedup"]["judgments"] == 6
    assert manifest["dedup"]["duplicates"] == 2


def test_a_rerun_with_unchanged_etags_downloads_nothing(tmp_path):
    b = bucket()
    first = _fetch(b, tmp_path, [2020, 2021])
    downloaded = b.downloads()

    second = _fetch(b, tmp_path, [2020, 2021])

    assert len(downloaded) == 6
    assert b.downloads() == downloaded
    assert second.snapshot.snapshot_id == first.snapshot.snapshot_id
    log = [json.loads(line) for line in (tmp_path / "fetch_log.jsonl").read_text().splitlines()]
    assert len(log) == 12
    assert [r["requested"] for r in log[6:]] == [False] * 6


def test_a_wider_year_range_backfills_only_the_new_tars(tmp_path):
    b = bucket()
    narrow = _fetch(b, tmp_path, [2021])
    before = len(b.downloads())

    wide = _fetch(b, tmp_path, [2020, 2021])

    assert sorted(b.downloads()[before:]) == [
        "data/tar/year=2020/english/english.index.json",
        "data/tar/year=2020/english/english.tar",
    ]
    assert wide.snapshot.snapshot_id != narrow.snapshot.snapshot_id


def test_a_requested_year_without_an_english_tar_is_an_error(tmp_path):
    with pytest.raises(LookupError, match="year=2019"):
        _fetch(bucket(), tmp_path, [2019, 2020])


def test_tar_year_reads_the_reporter_year_from_an_english_tar_key():
    index_key, tar_key = english_tar_keys(2017)

    assert (tar_year(tar_key), tar_year(index_key)) == (2017, 2017)
    assert tar_year(META_2020) is None
