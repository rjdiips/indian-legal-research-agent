---
Status: accepted
---

# Postgres in Docker is the single store for the whole app

Postgres 17 with pgvector holds everything the app stores: corpus (Snapshots, Judgments, paragraphs), citation graph, treatments, vectors, keyword indexes and LangGraph checkpoints. We won't add DuckDB or SQLite stores, or switch stores later in the project. Postgres runs from the `pgvector/pgvector:pg17` image through `docker-compose.yml`. Integration tests use a throwaway testcontainers Postgres. This keeps `gpu4090` and `laptop4060` on the same version and extensions, and keeps them apart from the Postgres 13 already installed on the host. The schema is plain numbered SQL in `migrations/`, with no ORM.

Corpus text is the one exception (spec decision 7): raw text, cleaned text and offset maps are files on disk under `DATA_DIR`, one per Judgment. Postgres holds their metadata, paragraph offsets and text hashes, not the text.

The package's `corpus/` code stays storage-agnostic: it produces plain Python records and iterators, and only `legal_agent` writes them to Postgres.

## Considered options

- **DuckDB as the single store:** it needs no server. But there's no LangGraph checkpoint saver for it, so checkpoints would need a second database (SQLite). It allows only one writer at a time, so the API can't serve while an ingest runs. And its saved vector index is experimental.
- **Postgres installed directly on each machine:** no Docker. But pgvector has to be installed by hand and kept in step on both machines, and tests would share a long-lived database instead of starting clean.

## Consequences

- Docker must be running to use the app or run integration tests (`make db-up`).
- If the MCP server is ever published (optional, PRD §7), its users need Postgres too.
