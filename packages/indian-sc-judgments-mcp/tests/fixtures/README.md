Test fixtures. No test touches the network.

- `s3_list_metadata_year2020.xml`: a real anonymous ListObjectsV2 response for
  `metadata/parquet/year=2020/`, recorded 2026-11-11.
- `s3_list_paged_{1,2}.xml`: two hand-built pages in the same format, to test continuation tokens.
- `s3_list_empty.xml`: an empty listing (a prefix with no objects).
- `metadata_tiny.parquet`, `metadata_tiny_2021.parquet`: built by `make_tiny_parquet.py`; rerun it to
  regenerate. The 2021 file repeats one 2020 `path` (a cross-year duplicate) and adds one new Judgment.
- Whole-bucket tests serve objects from memory with `../fake_bucket.py` instead of recorded XML.
- `english_mini.tar`, `english_mini.index.json`: built by `make_mini_tar.py` from four data-gate sample PDFs
  (scanned 1996, 2003 and 2017; born-digital 2024), one unreadable entry (`2099_1_1_1_EN.pdf`), one entry
  not in the index (`README.txt`), and one index name absent from the tar (`2099_1_2_2_EN.pdf`). ~250 KB.
  Golden Text quality for these PDFs was checked page by page against their structure.
