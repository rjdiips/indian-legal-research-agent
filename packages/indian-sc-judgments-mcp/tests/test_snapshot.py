import json

from indian_sc_judgments_mcp.corpus.download import S3Object
from indian_sc_judgments_mcp.corpus.snapshot import Snapshot

A = S3Object("metadata/parquet/year=2020/metadata.parquet", 627923, '"21db805de751fc62a16d02b3026a5f6f"')
B = S3Object("metadata/parquet/year=2021/metadata.parquet", 700000, '"aaaa"')


def test_same_listing_gives_same_snapshot_id_whenever_it_was_fetched():
    first = Snapshot.from_listing([A, B], fetched_at="2026-11-11T10:00:00+00:00")
    later = Snapshot.from_listing([B, A], fetched_at="2026-11-12T09:30:00+00:00")

    assert first.snapshot_id == later.snapshot_id
    assert len(first.snapshot_id) == 64


def test_changed_etag_gives_different_snapshot_id():
    changed = S3Object(A.key, A.size, '"ffffffffffffffffffffffffffffffff"')

    assert Snapshot.from_listing([A]).snapshot_id != Snapshot.from_listing([changed]).snapshot_id


def test_manifest_is_saved_under_the_data_home(tmp_path):
    snapshot = Snapshot.from_listing([A], fetched_at="2026-11-11T10:00:00+00:00")

    path = snapshot.save(tmp_path, dedup={"rows_read": 5, "duplicates": 1})

    assert path == tmp_path / "snapshots" / f"{snapshot.snapshot_id}.json"
    manifest = json.loads(path.read_text())
    assert manifest["snapshot_id"] == snapshot.snapshot_id
    assert manifest["fetched_at"] == "2026-11-11T10:00:00+00:00"
    assert manifest["objects"] == [{"key": A.key, "size": A.size, "etag": A.etag}]
    assert manifest["dedup"] == {"rows_read": 5, "duplicates": 1}
