# PRD-004 — Indian Legal Research Agent

| Field | Value |
|---|---|
| **Status** | Draft; data gate passed on 2026-11-06. Publishing the MCP server (§7) is optional, after the main build |
| **Version** | 0.7 |
| **Date** | 2026-11-11 |
| **Owner** | Rajdeep Sen |
| **Rank** | 3 |
| **Type** | Learning and portfolio build on open judgment data |
| **Related** | [Shared constraints](../../project-prds/README.md) |

## 1. Summary

The agent answers Indian legal research questions from Supreme Court judgments, cites specific passages, and warns when a cited judgment may no longer be good law. It abstains when evidence is weak.

Finding a relevant judgment isn't enough, because a reranker can surface a passage that has since been overruled. This project combines retrieval with a citation graph and a typed decision model to address that.

The paid Indian Kanoon API is replaced by free [AWS Open Data judgment sets](https://registry.opendata.aws/indian-supreme-court-judgments/). The project works without hand-labelled relevance data, because judgments' own citations supply test cases.

The Supreme Court judgments MCP server could later be published as a public package listed in the official MCP registry. Searches found no MCP server for Indian legal data, so it would fill a real gap. This is optional and comes after the main build.

The whole app uses one store: Postgres 17 with pgvector, run in Docker ([ADR-0001](adr/0001-postgres-in-docker-single-store.md)).

## 2. Goals and non-goals

| ID | Goal | Measure |
|---|---|---|
| G1 | Retrieve cited precedents | Reported recall@50, nDCG@10 and MRR on masked citations, with a reranking gain |
| G2 | Avoid future law | 100% of retrieved judgments predate the query's `as_of_date` |
| G3 | Flag overruled law | Precision ≥ 90% for "overruled" on a reviewed sample, with recall reported. The basic pattern starts at 54% |
| G4 | Ground answers | 100% of quoted passages match the stored text exactly. For OCR judgments that means the OCR text, not the page image |
| G5 | Abstain sensibly | Answer quality rises as coverage falls on the abstention curve |
| G6 | Stay free | Zero cash cost on either machine with local inference. The optional OpenCode backups, Go for the LLM and hosted Jev for decisions ([§8](#llm-backends)), are the only paid services, and nothing depends on them |
| G7 | Publish the MCP server (optional) | Package on PyPI, listed in the official MCP registry. Not required for the project to be done |

**Non-goals:** legal advice; replacing a lawyer or commercial citator; all 15.9M High Court PDFs; regional-language retrieval in the MVP; live case status; a public legal-advice product; a hosted server, since hosting costs money.

## 3. Use cases

- **UC-1, research:** "What test applies to anticipatory bail where X?" returns a cited answer, with related authorities.
- **UC-2, validity check:** Given a judgment, show later cases that follow, distinguish or overrule it, with the sentences that say so.
- **UC-3, historical view:** Answer as of a date, so a case overruled later appears as good law at that time.
- **UC-4, abstention:** If evidence conflicts or retrieval is weak, ask for clarification or decline, explaining why.

## 4. Data

### Sources

| Need | Source | Notes |
|---|---|---|
| Supreme Court judgments | [AWS Open Data](https://registry.opendata.aws/indian-supreme-court-judgments/), [repo](https://github.com/vanga/indian-supreme-court-judgments) | Measured: 38,392 unique English judgments from 1950 to 2026, with English tars totalling 22.69 GB. CC-BY-4.0, Parquet metadata, no AWS account needed. Covers SCR-reported judgments only |
| High Courts, later | [AWS Open Data](https://registry.opendata.aws/indian-high-court-judgments/) | CC-BY-4.0; reported about 15.9M PDFs, so one court at most |
| Statutes | [Annotated Central Acts](https://zenodo.org/records/5088102) | Working source: 858 acts, up to 2020 |
| Statutes, optional | [Nyaykosh](https://negd.gov.in/our_projects/nyaykosh-law-as-code/) | Responds without a login, but lists only four instruments, so it's a narrow addition. API not tested |
| Loader, optional | [`bharat-courts`](https://pypi.org/project/bharat-courts/) | Not used for the Supreme Court corpus; a candidate for the High Court stage ([ADR-0002](adr/0002-own-httpx-downloader-not-bharat-courts.md)) |

Credit the data source to meet CC-BY-4.0. Read each dataset's current licence before release. The data gate couldn't determine whether the maintainers can license everything scraped from `scr.sci.gov.in`, so check this, with legal advice if needed, before any public release.

### Loader rules

- Deduplicate on `path`, since 5,181 metadata rows are repeats.
- Use `decision_date` for all date logic, because the S3 `year` is the reporter year.
- Record the snapshot used, because the bucket updates about twice a month.

### Data gate result

The gate passed on 2026-11-06 using 200 judgments stratified by decade. The [full report](../../project-prds/data-gates/REPORT.md) has the method and limits.

| Check | Threshold | Measured | Result |
|---|---|---|---|
| Usable text | ≥ 80% | 100% (lower bound 98.2%) | Pass |
| Citation extraction | ≥ 70% | 90.3% (85.8–94.3) | Pass |
| Citation resolution | ≥ 50% | 61.4% (54.7–67.6); string match alone 28.8% | Pass |
| Treatment language | Projected ≥ 300 sentences | 7,375 (1,097–18,611) | Pass |
| Metadata | ≥ 90% | 99.83% across all 38,392 judgments | Pass |

**What the pass doesn't show:**
- **Treatment volume is overstated:** 42 of 78 candidates came from one judgment. A steadier figure is about 1,705 judgments (669–2,987) with a true sentence.
- **Linking is the hard part:** Only 6 of 45 true sentences contained a parseable citation.
- **Older citations resolve poorly:** Resolution runs from 15% in the 1950s to 75% in the 2020s.
- **Text isn't clean:** About 80% of the corpus is OCR over scans. Hand checks were done by the agent, not a lawyer.

**For any rerun:** Replace the treatment check with distinct overruled decisions that resolve to a corpus judgment. Report citation resolution by decade, and keep foreign and High Court citations as their own category.

### Scope

Start with English Supreme Court judgments, scaling from recent years backward as storage and time permit. Add one High Court only after the main evaluation is complete.

## 5. Automatically generated labels

### Retrieval: citation masking

1. Find a citation in a judgment.
2. Remove the citation and case name from the surrounding passage.
3. Use that passage as a query, restricted to judgments before the citing date.
4. Treat the cited judgment as relevant.

This yields thousands of test cases. It's a proxy: uncited cases can also be relevant, so absolute scores are pessimistic. It's best for comparing retrieval configurations.

Metadata holds only SCR and INSC citations, so build an SCC and AIR to SCR crosswalk by mining parallel citation chains across the corpus. Foreign and High Court citations resolved at about 3%, so give them their own category.

### Treatment: pattern-based labels

Extract sentences that mention a resolved citation near treatment language.

| Label | Example signals |
|---|---|
| `overruled` | "overruled", "no longer good law" |
| `followed` | "followed", "relied upon", "affirmed" |
| `distinguished` | "distinguished", "not applicable on facts" |
| `doubted` | "doubted", "referred to a larger Bench" |
| `neutral` | Citation with no treatment signal |

Patterns must exclude negated uses such as "not overruled", references to a third case, and overruled objections and pleas. In the gate, the basic pattern was only 54% precise. A simple filter reached 69% with no true sentence lost, but it was tuned on those same 78 sentences, so that isn't an independent result.

These labels test the decision model; they don't train it. To check that it isn't just spotting keywords, also test it on sentences with the signal words hidden.

**Linking sentences to cases:** Add short-name and `(supra)` resolution, scoped to cases cited earlier in the same judgment. Without it, most treatment sentences can't be linked to a case.

**Headnote labels:** Evaluate editorial labels as a separate signal, such as suffixes like "– overruled" and `Case Law Reference` tables. Sampled judgments with such a heading rose from 5 of 25 in the 2000s to 19 of 25 in the 2020s. Most say "relied on" or "referred to", so they help `followed` and `neutral` more than `overruled`. This came from a post-hoc observation, so test it before relying on it.

**Manual audit:** Review about 100 "overruled" predictions and 100 sentences from other classes. This is the only hand labelling, and it's required to state precision.

The research for this PRD found no published Indian dataset labelling negative treatment, so a documented silver-label set could be an original contribution. IL-PCR isn't assumed as a second test set: its parent dataset is gated with a non-commercial licence, and access hasn't been checked.

## 6. Decision models

A typed decision model handles choices that can be resolved from the text, as explained in the [shared rules](../../project-prds/README.md#decision-model). A small trained classifier makes the final answer-or-abstain call, because it combines numeric signals and typed-model probabilities may be overconfident.

| Decision | Method | Input | Output |
|---|---|---|---|
| Citation treatment | Decision model, `choice` | Sentence, citation context | `followed`, `distinguished`, `doubted`, `overruled`, `neutral` |
| Passage relevance | Decision model, `noul`, batched | Question, reranked passages | Relevant or not |
| Current validity | Rules over the graph and treatment decisions | Later treatment events, bench sizes if available | `good`, `caution`, `overruled`, `unknown` |
| Retrieval sufficiency | Decision model, `choice` | Question, evidence | `sufficient`, `retrieve_more`, `clarify` |
| Claim support | Decision model, `noul` per claim | Claim, cited passage | Supported or not |
| Answer or abstain | Calibrated logistic regression | Reranker scores, source agreement, validity flags, sufficiency probability | `answer`, `abstain` |

Train the answer-or-abstain model on earlier cases where a known cited authority was or wasn't found, and test it on later ones. Its limits must be stated, because this is a proxy for answer quality.

The LLM carries out agent reasoning and writes answers, but these models handle the decisions.

The decision model runs locally when possible, with hosted Jev 1.13 as the backup. See [§8, Decision model backends](#decision-model-backends).

`unknown` is the required result when evidence is missing. Never present the absence of a negative citation as proof that a case is good law.

## 7. Architecture

```text
download -> parse -> extract citations -> resolve citations -> build graph
                                    \-> treatment decisions -> test against silver labels
                    \-> chunk -> embed -> index

question -> supervisor -> researcher -> retrieval and reranking
         -> citation checker -> sceptic -> decision -> answer or abstain
```

### LangGraph agents

| Agent | Job | Tools |
|---|---|---|
| Supervisor | Plans sub-questions and limits budget | State only |
| Researcher | Finds passages and statutes | `search_judgments`, `get_statute_section` |
| Citation checker | Traces the graph and validity | `get_citations`, `get_treatment` |
| Sceptic | Looks for contrary authority and larger-bench decisions | `search_judgments`, `get_citations` |
| Writer | Writes only from approved evidence | State only |
| Verifier | Checks quotes and citations against stored text | `get_judgment` |

The sceptic has a real job: searching for contrary authority rather than rephrasing the researcher's output. Limit retrieval retries to two.

The MVP runs these agents in sequence. Parallel researchers and citation checkers are planned for after the MVP; see [§15](#15-later-phase-parallel-research).

### Non-naive RAG

1. **Cleaning and structured parsing:** Remove page heads, margin letters and the judgment's own citation first. Then separate headnote if present, facts, arguments, reasoning and order where feasible. Keep paragraph numbers for pinpoint citations.
2. **Hybrid retrieval:** Combine dense search, BM25 and exact matching for citation strings and statute sections.
3. **Graph expansion:** Add closely linked authorities and later treatment events.
4. **Reranking:** Rerank up to 50 candidates with `bge-reranker-v2-m3`, and limit passages per judgment for diversity.
5. **Corrective loop:** Grade evidence, rewrite weak queries, then abstain.

### Store

One Postgres 17 database with pgvector holds everything: corpus, citation graph, treatments, vectors, keyword indexes and LangGraph checkpoints. It runs from the `pgvector/pgvector:pg17` image via `docker-compose.yml` (`make db-up`), and the schema comes from plain numbered SQL in `migrations/`. Don't add a second store such as DuckDB or SQLite. The loader may still use DuckDB to read the source Parquet files, because that only reads input and stores nothing ([ADR-0001](adr/0001-postgres-in-docker-single-store.md)).

### Graph tables

```sql
CREATE TABLE judgments (
  judgment_id TEXT PRIMARY KEY,
  title TEXT,
  decision_date DATE,
  court TEXT,
  bench_size INT,
  source_uri TEXT NOT NULL,
  text_quality TEXT NOT NULL -- ocr | born_digital
);

CREATE TABLE citations (
  citation_id UUID PRIMARY KEY,
  citing_id TEXT NOT NULL REFERENCES judgments,
  cited_id TEXT REFERENCES judgments, -- null if unresolved
  raw_citation TEXT NOT NULL,
  resolution_method TEXT, -- string | name | parallel | crosswalk | short_name | supra
  paragraph INT,
  context TEXT NOT NULL
);

CREATE TABLE treatments (
  citation_id UUID NOT NULL REFERENCES citations,
  label TEXT NOT NULL,
  source TEXT NOT NULL, -- pattern | decision_model | human
  probability NUMERIC,
  model_version TEXT
);
```

### MCP servers

| Server | Tools |
|---|---|
| `judgment-corpus` | `search_judgments(query, court, as_of_date)`, `get_judgment`, `get_passage` |
| `citation-graph` | `get_citations(id, direction, as_of_date)`, `get_treatment(id, as_of_date)` |
| `statutes` | `get_statute_section(act, section, as_of_date)` |

All tools are read-only and enforce `as_of_date`. This replaces the [existing Indian Kanoon MCP server](https://pypi.org/project/indian-kanoon-mcp/), and it teaches more than wrapping an API.

### Published MCP server (optional)

Publishing is optional and comes after §12's main milestones. The project's own agents use this package either way, so there's one codebase rather than an internal copy and a public fork. The decisions below apply only if it is published.

| Item | Decision |
|---|---|
| Scope | `judgment-corpus` and `citation-graph`, combined into one server. `statutes` stays internal until its source licence is checked |
| Name | Working name `indian-sc-judgments-mcp`. Check that it is free on PyPI and in the registry before release |
| Distribution | PyPI package, run with `uvx`. Listed in the [official MCP registry](https://registry.modelcontextprotocol.io/) under a GitHub-verified namespace (`io.github.<owner>/…`), published with the free `mcp-publisher` CLI and a `server.json` |
| Transport | `stdio` by default; Streamable HTTP for anyone who wants to host it themselves. No hosted instance |
| Spec | Current MCP spec at release, using the official Python SDK. Every tool marked read-only through tool annotations |
| Data | The package ships no judgments. On first run, `init` downloads the metadata Parquet and selected years from the public AWS bucket, which needs no account, then builds a local index. The user chooses year ranges to control disk use |
| Store | Same Postgres as the app, so users need Postgres too, for example via the project's Docker setup. A lighter package-only store isn't planned; revisit only if publishing goes ahead ([ADR-0001](adr/0001-postgres-in-docker-single-store.md)). `bge-m3` dense search and `bge-reranker-v2-m3` stay an optional `full` extra |
| Citation graph | Built locally by the same deterministic extractor. Treatment labels in the package come from patterns only, and are marked `source: pattern`. Typed-model labels stay internal unless the derived data is cleared for release |
| Attribution | Every result includes the original source URI and a CC-BY-4.0 credit line for the dataset |

**Public tools:**

| Tool | Purpose |
|---|---|
| `search_judgments(query, as_of_date, year_from, year_to, limit)` | Hybrid or BM25 search with pinpoint paragraphs |
| `get_judgment(id)` | Metadata, text quality and source link |
| `get_passage(id, paragraph)` | Exact paragraph text for quoting |
| `lookup_citation(citation)` | Resolve a citation string such as an SCR, SCC or AIR reference, or a case name, to a judgment, with the resolution method |
| `get_citations(id, direction, as_of_date)` | Cases this judgment cites, or cases that cite it |
| `get_treatment(id, as_of_date)` | Later treatment events with supporting sentences, label source and confidence. Returns `unknown` when nothing is found, never "good law" |

Also expose each judgment as an MCP resource (`sc-judgment://{id}`), so clients can attach one to a conversation.

**Release checklist:**
- README with install steps and config snippets for Claude Desktop, Claude Code and Cursor.
- Disclaimer that this is not legal advice, and that treatment labels are machine-generated.
- Contract tests for every tool, plus a manual pass with the MCP Inspector.
- Semantic versioning and a changelog. The index format is versioned, so upgrades rebuild or migrate it.
- The licensing position from §4 is checked before any derived data, such as a prebuilt index or citation graph, is published. Code-only release doesn't depend on it.

### Scraping

Most data comes as a bulk download, so scraping is the project's weak spot. Add a small polite collector for one public source of new judgments or statute changes only if its terms permit it. Don't scrape Indian Kanoon, which is [reported to sit behind Cloudflare](https://scrape.do/industries/ai-llm/indiankanoon-scraper/) and may have terms against it.

## 8. Runtime

| Job | `gpu4090` | `laptop4060` |
|---|---|---|
| LLM | Local: the shared vLLM model. Backup: OpenCode Go (see [LLM backends](#llm-backends)) | Local: a small model on the GPU when memory allows. Backup: OpenCode Go |
| Parse and citation extraction | CPU | CPU |
| Embedding | CPU; possibly over several nights | GPU; faster |
| Reranking | CPU, as a batch | GPU |
| OCR | Not planned: every PDF has an embedded text layer, which is used as is. About 80% of judgments are scans whose layer is existing OCR; `text_quality` marks them | Same |
| Typed decision model | Local: CPU; measure latency, then size batch runs. Backup: hosted Jev 1.13 (see [Decision model backends](#decision-model-backends)) | Local: GPU, sharing memory with retrieval. Backup: hosted Jev 1.13 |
| Answer-or-abstain classifier | CPU | CPU |
| Agent evaluation | Overnight on the shared model | On the local model if it's good enough; otherwise on OpenCode Go within its allowance |

Retrieval and treatment evaluations use no LLM, so they can run across thousands of cases on either machine, subject to measured decision-model latency. Keep agent evaluation to about 50–100 questions.

### LLM backends

Use local inference whenever possible. Use OpenCode only when local isn't available. The same rule applies to the LLM and to the typed decision model, which use different OpenCode services.

| Order | Backend | When | Cost |
|---|---|---|---|
| 1 | Local | `gpu4090`: the shared vLLM model, following the shared-4090 rules. `laptop4060`: a small local model, run one job at a time so it doesn't compete with embedding and reranking for the 8 GB of VRAM | Free |
| 2 | OpenCode Go, a chat model from the [Go list](https://opencode.ai/docs/console/go/) | Local is unavailable: the 4090 model isn't listed at `GET /v1/models`, the server is busy with FinAssure, or the 4060 can't fit a useful model | Included in the $10/month Go subscription |
| 3 | OpenRouter free tier | Optional zero-cost fallback if Go is dropped | Free, about 50 requests a day |

**About OpenCode Go:**
- The project must still work end to end without it, so G6 holds for the default setup. Go is an optional paid backup.
- Pick one Go model with 0-day retention and no training, such as a Qwen, GLM or Kimi model, and record its ID in local `.env`. Check the live list at `https://opencode.ai/inference/go/v1/models`.
- Limits are dollar allowances per model, not request counts: the 5-hour limit is 20% of the monthly allowance, the weekly limit 50%. Each response reports what it counted (`opencode.allowance`). Keep **Extra Usage** off, so hitting the limit stops calls instead of charging credit.
- Go is meant for coding-agent traffic and is monitored for abuse. Send a project-specific user agent, such as `indian-legal-research-agent/0.1`, and a stable `x-opencode-session` header per research run. Run large batches locally, not on Go.
- Check privacy terms per model: most Go models are listed as 0-day retention and no training. Don't enable the "train on request data" models (Muse Spark Contributor, Iceman Contributor Free). Send public data only, as with OpenRouter.
- Route Go through LiteLLM like every other backend. Only `LLM_BASE_URL`, `LLM_MODEL` and the key change.
- The response cache and evaluation records store the exact backend and model per response. Don't switch backends in the middle of an evaluation run.

### Decision model backends

Jev 1.13 is a TypeSafe AI "System One" typed decision model, hosted on OpenCode. It answers `noul`, `choice` and `score` questions about a `state` and returns values and probabilities, which is what §6 needs. See the [OpenCode Console models docs](https://opencode.ai/docs/console/models/) and the [TypeSafe AI docs](https://docs.typesafe.ai/).

| Order | Backend | When | Cost |
|---|---|---|---|
| 1 | Local open-weights typed decision model ([shared rules](../../project-prds/README.md#typed-decision-model-rules); not chosen yet) | Default whenever a local model is available and fits | Free |
| 2 | Hosted `jev-1.13-free` | No usable local model, while the free tier lasts | Free for a limited time |
| 3 | Hosted `jev-1.13` | No usable local model, and the free tier has ended or is unavailable | $0.042 per 1M input tokens, output free, pay-as-you-go |

**About hosted Jev:**
- This is a project-specific exception to the shared rule that the decision model "must run locally on open weights". The exception applies only as a backup, and the project must still run on a local model.
- Jev is on the Console's pay-as-you-go model list, not the Go plan list. Expect `jev-1.13` to be billed from Console credit, not the Go allowance. Check the Console Activity page after the first call to confirm.
- The endpoint is `https://opencode.ai/inference/systemone/v1/systemone`, with the Console API key. It isn't OpenAI-compatible, so it doesn't go through LiteLLM. It needs its own adapter in `src/legal_agent/decisions/`, next to `local.py` and `fake.py`, behind the same interface.
- One request can carry several questions about the same `state`, and Jev evaluates them in parallel. Use that to batch passage relevance and claim support.
- OpenCode publishes no retention or training terms for Jev. Send public judgment text only, and check the terms before any non-public input.
- Treat Jev probabilities as uncalibrated, as with any decision model. Hosted and local models are different models, so record which one produced each decision, and don't mix them within one evaluation run.

Set the embedding plan from the measured corpus: 38,392 judgments and 22.69 GB of English tars. Use quantised vectors if storage or memory is tight.

Estimated full English corpus footprint is about 45–50 GB with float32 vectors and raw tars kept. This is an estimate, not a measurement. If disk becomes tight, measure a sample first, then quantise vectors in pgvector (`halfvec`) or drop raw tars after parsing.

Parse `bench_size` from the PDF, since only 12.7% of `judge` metadata values contain more than one name.

## 9. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/research` | Start a research run |
| `GET` | `/v1/research/{id}` | Answer, evidence or abstention |
| `GET` | `/v1/judgments/{id}` | Judgment and passages |
| `GET` | `/v1/judgments/{id}/treatment?as_of=` | Validity and supporting sentences |
| `GET` | `/v1/search?q=&as_of=` | Direct retrieval, without agents |

## 10. Evaluation

### Retrieval comparison

| Configuration | Metrics |
|---|---|
| BM25 | recall@50, nDCG@10, MRR |
| Dense | Same |
| Hybrid | Same |
| Hybrid plus reranker | Same, with latency |
| Plus graph expansion | Same |

Report results by decade, or limit the headline result to 1990 onward and disclose that, because citation resolution is weak in earlier decades. Also compare at least two rerankers if time permits. No public comparison on Indian case law was found, so a published comparison would be useful.

### Treatment

- Per-class precision, recall and confusion matrix.
- Distinct overruled decisions that resolve to a corpus judgment, not only sentence counts.
- Results for headnote labels, reported separately.
- Results on the audited sample, separate from pattern labels.
- Results on sentences without the obvious signal words.

### Agent

- **Test questions:** Convert masked citation contexts into research questions with an LLM, and record that they're generated.
- **Metrics:** Known authority found, citation validity, overruled-case warning rate, abstention curve, calls and tokens per question.
- **Baseline:** One prompt over hybrid retrieval, without agents or the graph. A [related paper](https://arxiv.org/abs/2602.23371) reports 70% vs 37.5% for hybrid RAG and knowledge graph vs RAG alone, on only 40 synthetic questions, so test this comparison at larger scale.

**Deliverables:** data gate report, retrieval comparison, silver-label documentation, treatment audit, abstention curve, and sample answers with evidence.

## 11. Testing

| Layer | Test |
|---|---|
| Unit | Citation parser, name normalisation, negation rules |
| Golden | Hand-checked judgments with expected citations and paragraphs |
| Date logic | Property test: no result postdates `as_of_date` |
| Masking | Query text doesn't contain the masked case name or citation |
| Verifier | Altered quotes are rejected |
| Graph | Retry and budget limits; abstain path |
| Replay | Stored responses reproduce an answer |
| Integration | Throwaway Postgres via `testcontainers`, so Docker must be running; recorded LLM responses |

## 12. Milestones

| Day | Deliverable |
|---|---|
| 1 | Repo, snapshot record, corpus downloader and deduplicating loader |
| 2 | Metadata, text cleaning, parser and `bench_size` extraction |
| 3 | Citation extraction, resolution, crosswalk, and short-name and `(supra)` handling |
| 4 | Citation graph and treatment patterns |
| 5 | Masked retrieval evaluation set |
| 6 | Chunking, embedding, BM25 and dense search |
| 7 | Hybrid search, reranking, retrieval report |
| 8 | Decision-model port confirmed, treatment decisions and audit |
| 9 | MCP servers with date enforcement |
| 10–11 | LangGraph agents, verifier and validity flags |
| 12 | Answer-or-abstain classifier and agent evaluation |
| 13 | API and simple research UI |
| 14 | README, results and limits |
| 15, optional | Package the MCP server: `init` command, contract tests, README and client snippets |
| 16, optional | Publish to PyPI and the MCP registry; test a fresh install on a clean machine |

**Done when:** a reviewer can ask a question as of a date, inspect pinpoint citations and validity warnings, see an abstention case, and read the retrieval and treatment reports. Days 15–16 aren't needed for this.

The parallel research phase in §15 starts only after these milestones are done.

## 13. Risks

| Risk | Mitigation |
|---|---|
| About 80% of the corpus is OCR over scans | Cleaning stage; `text_quality` field; OCR-aware quote checks; narrower time range if needed |
| Citation formats vary widely | Parser fixtures; crosswalk; resolution rate reported by method and decade |
| Noisy treatment labels | Negation and objection filters, audit, `unknown` state, and counting distinct decisions |
| Treatment sentences can't be linked to a case | Short-name and `(supra)` resolution; report the linked share |
| Public release of scraped court data | Check the dataset's licensing position first |
| Decision model only spots keywords | Masked-signal testing and separate evaluation |
| Good-law warnings give false comfort | Explicit `unknown`; no claim of citator coverage |
| Overruling depends on context | Show supporting sentences; treat partial overruling carefully; recommend checking the source |
| Corpus too large for hardware | Scale by year; quantise vectors; defer High Courts |
| Personal details in judgments | Query original public data only; don't publish derived personal profiles; exclude sensitive cases from demos |
| Output treated as legal advice | Prominent notice; evidence-first UI; abstention |
| Published server users trust pattern-only treatment labels | Label source and confidence on every result; `unknown` instead of "good law"; disclaimer in the README and tool descriptions |
| First-run download too large for users | Year-range selection in `init`; dense models are an optional extra |
| Published package goes unmaintained | Pin dependencies; index format version; state the support level in the README |

## 14. Open questions

1. How reliably can bench size be parsed from the PDFs?
2. Does Nyaykosh's coverage grow enough to matter?
3. Should High Court data enter the evaluation, or only serve as a later scale test?
4. Can a prebuilt index or citation graph be published, so users skip the local build? This depends on the licensing check in §4.

## 15. Later phase: parallel research

**Status:** planned. Start only after the milestones in §12 are done and the sequential agent has been evaluated. Until then, this section is for reference only.

### Why

The MVP runs one chain: supervisor, researcher, citation checker, sceptic, writer, verifier. Two parts of that chain are naturally independent:

- **Issues.** Legal questions often raise several separate issues, such as limitation, jurisdiction and the merits. One researcher covering all of them gets a crowded context.
- **Authorities.** Each candidate judgment's later treatment and validity can be checked without looking at the others.

Fanning out on both is the main multi-agent lesson for this project, and it keeps each worker's context small.

### Graph

```text
supervisor -> Send per issue: [researcher -> rerank] x N -> join (reducer merges evidence)
           -> Send per authority: [citation checker] x M -> join
           -> sceptic -> sufficiency (loop back at most twice) -> writer -> verifier -> answer or abstain
```

| Change | How |
|---|---|
| Researcher per issue | The supervisor splits the question into issues and caps them at 4. LangGraph `Send` starts one researcher per issue. A reducer merges evidence and removes duplicate passages. |
| Citation checker per authority | Fan out over the candidate judgments after the researcher join. Each worker traces later treatment and validity in the graph. |
| Retrieval channels | Inside `search_judgments`, run dense, BM25, exact citation and graph expansion concurrently. This is plain async code, not agent parallelism. |
| Unchanged | The sceptic stays after the join, because it needs the researchers' candidates to look for contrary and larger-bench decisions. Claim-support checks stay batched as typed-model questions. |

### Limits

- **Speed:** The 4090 rules allow at most 2 parallel LLM calls, OpenCode Go has a 5-hour dollar allowance, and OpenRouter allows 20 requests a minute and 50 a day. In the `gpu4090` profile the reranker runs on CPU, so branches compete for it. The gain is in structure and context size, not latency.
- **Budget:** Give each worker a token and call budget. The supervisor caps N issues and M authorities, so a vague question can't fan out into many calls.
- **Checkpoints:** Each worker writes to its own keyed slot in the merged state. A resume after an interrupt must not rerun finished branches. Add a test for this.

### Evaluation

The masked-citation questions in §10 have one issue each, so they don't exercise the fan-out. Build multi-issue questions from real citations, without hand labelling:

1. Take a judgment that cites several authorities in different paragraphs.
2. Mask every citation, and combine 2–4 of those passages into one question.
3. Treat the set of judgments actually cited as the gold answer.

| Configuration | Metrics |
|---|---|
| Sequential MVP agent | Recall of the gold set, citation validity, calls, tokens, latency |
| Per-issue researchers | Same |
| Per-issue researchers plus per-authority checkers | Same |

Report results on single-issue questions too, to show the fan-out doesn't hurt them. If parallelism doesn't improve recall or cost, say so and keep the sequential agent as the default.

### Tests

| Layer | Test |
|---|---|
| Graph | Issue and authority caps hold; empty fan-out goes straight to the sufficiency check |
| Reducer | Merged evidence has no duplicate passages and keeps each issue's source |
| Checkpoint | Resuming after an interrupt doesn't rerun finished branches |
| Budget | A worker that runs out of budget returns partial evidence and is marked as incomplete |

### Milestones

| Day | Deliverable |
|---|---|
| P1 | Multi-issue evaluation set from real citations |
| P2 | Per-issue researcher fan-out with reducer and caps |
| P3 | Per-authority citation checker fan-out; checkpoint and budget tests |
| P4 | Comparison against the sequential agent; results added to the README |

