# Indian Legal Research Agent

Built from [PRD-004](docs/PRD-004-Indian-Legal-Research-Agent.md). Skeleton only: modules are empty.

## Layout

```text
packages/indian-sc-judgments-mcp/   MCP server package (publishing optional)
  src/indian_sc_judgments_mcp/
    corpus/       download, snapshot, loader, cleaning, parsing
    citations/    extraction, resolution, crosswalk, short names and (supra)
    treatment/    pattern labels
    search/       local store, BM25, dense + reranker
    server.py     MCP tools and resource
    cli.py        init and serve
  tests/
src/legal_agent/                    research system; uses the package above
  llm/            LiteLLM client, 4090 guard
  decisions/      decision-model port, validity, answer-or-abstain
  graphdb/        Postgres citation graph
  retrieval/      chunking, embedding, hybrid search, graph expansion
  agents/         LangGraph state, nodes, graph
  mcp_statutes/   internal statutes MCP server
  api/            FastAPI (PRD §9)
  eval/           masking, metrics, evaluations
migrations/       Postgres schema
tests/            unit, golden, integration, fixtures
data/  reports/   local only; not committed
```

## Setup

Needs Docker: Postgres 17 with pgvector is the app's only database and runs in a container ([ADR-0001](docs/adr/0001-postgres-in-docker-single-store.md)). Integration tests also start a throwaway Postgres container.

```bash
cp .env.example .env
uv sync                 # add --extra full for bge-m3 + reranker (pulls torch)
make db-up              # Postgres 17 + pgvector on :5440
```
