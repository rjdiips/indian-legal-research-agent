import argparse

import pytest

from legal_agent.cli import tar_years


@pytest.mark.parametrize(
    ("given", "years"),
    [
        ("2015-2026", tuple(range(2015, 2027))),
        ("1950-1952", (1950, 1951, 1952)),
        ("2020", (2020,)),
        ("none", ()),
    ],
)
def test_tar_years_reads_a_range_a_single_year_or_none(given, years):
    assert tar_years(given) == years


@pytest.mark.parametrize("given", ["2026-2015", "20x0", "2015-"])
def test_tar_years_rejects_a_bad_range(given):
    with pytest.raises(argparse.ArgumentTypeError):
        tar_years(given)
