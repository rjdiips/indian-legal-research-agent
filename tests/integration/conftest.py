from collections.abc import Iterator

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    # Throwaway data: skip fsync so initdb and tests don't wait on a busy disk.
    container = (
        PostgresContainer("pgvector/pgvector:pg17", driver=None)
        .with_env("POSTGRES_INITDB_ARGS", "--no-sync")
        .with_command("postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off")
    )
    with container as pg:
        yield pg.get_connection_url()


@pytest.fixture
def conn(postgres_url: str) -> Iterator[psycopg.Connection]:
    """A connection to an empty database (every table dropped after each test)."""
    with psycopg.connect(postgres_url, autocommit=True) as c:
        yield c
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
