"""Regenerate metadata_tiny.parquet: same columns as the bucket's metadata parquet, six rows.

Run: uv run python packages/indian-sc-judgments-mcp/tests/fixtures/make_tiny_parquet.py
"""

from pathlib import Path

import duckdb

OUT = Path(__file__).with_name("metadata_tiny.parquet")
COLUMNS = [
    "title", "petitioner", "respondent", "description", "judge", "author_judge", "citation", "case_id",
    "cnr", "decision_date", "disposal_nature", "court", "available_languages", "raw_html", "path",
    "nc_display", "scraped_at",
]  # fmt: skip
ROWS = [
    # path A twice: the later scrape wins
    dict(title="A v. State (old scrape)", path="2020_4_552_564", decision_date="13-05-2020",
         scraped_at="2025-06-12T21:51:58", judge="N.V. RAMANA", citation="[2020] 4 S.C.R. 552",
         cnr="ESCR010002942020", nc_display="2020INSC395"),
    dict(title="A v. State", path="2020_4_552_564", decision_date="13-05-2020",
         scraped_at="2025-06-13T08:00:00", judge="N.V. RAMANA", citation="[2020] 4 S.C.R. 552",
         cnr="ESCR010002942020", nc_display="2020INSC395"),
    # decided in 2019, reported in the 2020 volume
    dict(title="B v. Union", path="2020_1_10_20", decision_date="27-11-2019",
         scraped_at="2025-06-12T21:52:00"),
    dict(title="C v. D (no date)", path="2020_2_30_40", decision_date=None, scraped_at="2025-06-12T21:52:01"),
    dict(title="E v. F (impossible date)", path="2020_3_50_60", decision_date="31-02-2020",
         scraped_at="2025-06-12T21:52:02"),
    dict(title="G v. H (garbled date)", path="2020_5_70_80", decision_date="sometime in 2020",
         scraped_at="2025-06-12T21:52:03"),
]  # fmt: skip

# A second Reporter year. Path A repeats across years (as 5,181 real rows do), scraped later here.
OUT_2021 = Path(__file__).with_name("metadata_tiny_2021.parquet")
ROWS_2021 = [
    dict(title="A v. State (2021 volume)", path="2020_4_552_564", decision_date="13-05-2020",
         scraped_at="2025-07-01T09:00:00", judge="N.V. RAMANA", citation="[2020] 4 S.C.R. 552",
         cnr="ESCR010002942020", nc_display="2020INSC395"),
    dict(title="J v. K", path="2021_1_1_12", decision_date="05-01-2021", scraped_at="2025-07-01T09:00:01"),
]  # fmt: skip


def write(out: Path, rows: list[dict], year: int) -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE m (" + ", ".join(f"{c} VARCHAR" for c in COLUMNS) + ", year BIGINT)")
    for row in rows:
        values = [row.get(c, "Supreme Court of India" if c == "court" else "") for c in COLUMNS]
        values[COLUMNS.index("decision_date")] = row["decision_date"]
        con.execute(f"INSERT INTO m VALUES ({', '.join('?' * (len(COLUMNS) + 1))})", [*values, year])
    con.execute(f"COPY m TO '{out}' (FORMAT parquet)")
    print(out, con.execute("SELECT count(*) FROM m").fetchone())


if __name__ == "__main__":
    write(OUT, ROWS, 2020)
    write(OUT_2021, ROWS_2021, 2021)
