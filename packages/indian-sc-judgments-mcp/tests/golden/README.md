Golden raw texts for cleaning, paragraph and Bench size tests: PyMuPDF page text joined by `\f`,
exactly as `corpus/raw_text.py` writes it. Named `<path>.txt`.

- `S_1996_4_314_315`, `S_2003_2_63_65`, `2017_7_348_348` (`ocr`), `2024_4_598_605` (`born_digital`):
  extracted from the PDFs in `../fixtures/english_mini.tar`.
- `1950_1_453_459`, `1961_3_813_820` (main sample), `1983_3_321_336` (dev sample): data-gate texts
  (`project-prds/data-gates/raw/legal/text/`), all `ocr`.
- `2015_2_37_50`, `2015_7_1_9`, `2016_4_157_170` (`ocr`), `2019_18_990_994`, `2023_1_1105_1110`,
  `2023_4_585_595` (`born_digital`): ticket 03's extraction of the real corpus.
- `2014_14_185_186` (`ocr`): ticket 09's example, from the real corpus; a stamp on page 2 comes out
  as a block of symbol lines, and its margin letters are misread (`h`, `s·`, `B Nidhi Jain`).
- `2025_4_2742_2752` (`born_digital`): ticket 07, paragraphs numbered `1)` on a line of their own.
- `2023_16_1209_1524` (`born_digital`, trimmed): ticket 10, the same-sex marriage Judgment with four
  Opinions, each numbered from 1. Page 1 is whole. Each later page keeps only its lines that start
  with a paragraph marker or name an author, cut to 60 characters and closed with a full stop
  (41 KB of the 757 KB raw text).
