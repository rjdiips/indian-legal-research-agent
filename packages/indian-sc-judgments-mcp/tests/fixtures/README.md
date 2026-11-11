Test fixtures. No test touches the network.

- `s3_list_metadata_year2020.xml`: a real anonymous ListObjectsV2 response for
  `metadata/parquet/year=2020/`, recorded 2026-11-11.
- `s3_list_paged_{1,2}.xml`: two hand-built pages in the same format, to test continuation tokens.
- `s3_list_empty.xml`: an empty listing (a prefix with no objects).
- `metadata_tiny.parquet`: built by `make_tiny_parquet.py`; rerun it to regenerate.
