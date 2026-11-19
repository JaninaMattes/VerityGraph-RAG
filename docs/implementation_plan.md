# VerityGraph — Implementation Plan

Status: 2026-11-19 · Base: `main` @ `81254cc` · Vision: [documentation.md](documentation.md)

## 1. Vision and scope

VerityGraph turns fragmented documents into a traceable knowledge graph. Users ask
questions in natural language. Every answer shows its evidence: the document, page and
text span. The system keeps facts taken from sources apart from conclusions a model made.

**Target users:** analysts who must answer multi-hop questions across many documents, for
example market and competitor research on SEC 10-K filings.

**Core use case:** upload filings → ask "How do the five largest US tech companies invest
in each other?" → get a graph, a short answer and a source list. Each source is
highlighted in the original PDF.

**Non-goals (for now):** real-time data feeds, self-hosted GPU inference in production,
multi-region deployment, Slack integration, fine-tuning models.

**Success looks like:**
- every answer claim links to at least one evidence span, or carries the label "inferred";
- retrieval and answer quality are measured on a fixed evaluation set, and they improve
  from phase to phase;
- the demo runs mainly on free-tier services.

## 2. Where we are today

| Area | State on `main` |
| --- | --- |
| Tenants, users (CRUD) | Works. JWT bearer authentication on every endpoint except health and login |
| Presigned upload and download (MinIO) | Works. Object keys are `tenant/namespace/yyyy/mm/document_id` |
| MinIO → Kafka → Temporal workflow | Works. Idempotent: workflow ID `ingestion-job-<document_id>`, `REJECT_DUPLICATE` (one workflow per upload, also after a failure) |
| Document processing | Docling parses and chunks the file. Chunks and their page/box spans are stored in Postgres |
| Data model | The provenance model ([provenance-model.md](provenance-model.md)): chunks, spans, pipeline configs, entities, relationships, communities, embeddings |
| Tests and CI | Unit tests and Postgres integration tests (coverage gate ≥ 95 %), Ruff, frontend lint and build |
| Deploy workflow | Builds the API image and pushes it to GHCR after CI passes on `main` |
| Frontend | Vite + React 19 scaffold, not connected |
| Agents, MCP, evaluation, observability, pipelines | Empty placeholder packages |

## 3. Target architecture: principles

The diagram shows the full vision. The plan is to bild it in this order and with these rules:

1. **Postgres is the system of record.** Documents, chunks, evidence spans and jobs live
   there. Neo4j and the vector index are *derived* and can always be rebuilt from Postgres
   and MinIO.
2. **Pass IDs, not bytes.** Temporal payloads hold IDs and object keys only (Temporal limits
   payloads to about 2 MB). Large artefacts, such as parsed documents, go to MinIO.
3. **Every pipeline step is an idempotent activity**, keyed by `document_id` or
   `chunk_hash`. One can re-run a step after changes in code are made.
4. **Add a component only for a measured need.** The diagram has about 15 services. Each new
   service costs memory, money and operations time, which needs to be analysed conservatively.
5. **Every adapter sits behind a port** (`Protocol` in `domain/`). That way any 
   local and cloud services (MinIO ↔ R2, Kafka ↔ webhook, Ollama ↔ hosted LLM) can be simply swapped later.

### Component decisions

| Diagram component | Now | Add when |
| --- | --- | --- |
| FastAPI, Postgres, MinIO, Temporal | Keep | — |
| Kafka | Keep locally. Hide it behind a port | In the cloud, use storage webhook → API → Temporal if hosted Kafka is too limited |
| Nginx gateway | Leave out. The hosting platform provides ingress | Several backend services need one entry point |
| Redis cache | Leave out | Measured repeated queries are too slow or too expensive |
| Ray, vLLM | Leave out | Self-hosted inference becomes a real requirement |
| Ollama | Local development only | — |
| Neo4j | Phase 3 | — |
| Qdrant | Decide in Phase 2 (see ADR-001) | Neo4j vector search is not good enough |
| LangGraph + Postgres checkpointer | Phase 4 | — |
| MCP servers (FastMCP) | Phase 4, in-process first | Tools must scale or deploy on their own |
| Grafana, Prometheus | Phase 6 (Grafana Cloud free) | — |

## 4. Knowledge and provenance model

This model is the "Verity" in VerityGraph. The full definition, with the table list and
the rebuild of Neo4j and Qdrant, is in [provenance-model.md](provenance-model.md).

```text
Document ─1:n─ Chunk ─1:n─ ChunkSpan(page, bbox, char_start, char_end, source_ref)
Chunk ─n:m─ Entity            (entity_mention, with the character range)
Entity ─[entity_relationship {type, weight}]→ Entity, supported by relationship_evidence → Chunk
Answer ─1:n─ Claim(text, kind: SOURCE | INFERRED, evidence: [chunk_id…])   (Phase 4)
```

- Each chunk has typed spans (`chunk_span`) with page, box and character range. The
  frontend uses them to highlight the source.
- Every graph edge stores the chunks that support it. An edge without evidence is not
  written.
- The answer composer may cite only evidence IDs that retrieval returned. The code checks
  this, not the prompt.

## 5. Improvements before moving forward (Phase 0)

Ordered by priority. Each item is small.

**Code health**
- [x] Apply the refactor of the local branch `wip/claude-refactor` (on
      `phase-1/provenance-model`): one exception hierarchy and handler table, `LOG_LEVEL` that really
      filters, JSON logs, worker logging, request-ID middleware, 409 for duplicates, CORS
      for the frontend.
- [x] Remove the empty placeholder packages (`agents/`, `mcp/`, `evaluation/`,
      `observability/`, `pipelines/`, `infrastructure/models/`, `neo4j/`, `qdrant/`). Create
      each one when its phase starts.
- [x] Replace `temporalio[langgraph]` with `temporalio`. Add `langgraph` in Phase 4.
- [x] Fix the image build. The current `.dockerignore` files have no effect, because the
      build context is the repository root. Run as a non-root user. Read `PORT` for Render.

**Operability**
- [x] Add `GET /health/live` (process up) and `GET /health/ready` (Postgres and MinIO
      reachable). Use them in the Compose health checks and on the hosting platform.
- [ ] Kafka poison messages: define a policy and test it (log and skip, or a dead-letter
      topic). Today there is none.
- [ ] Expose the ingestion status: `GET /documents/{id}` returns `status` and
      `current_stage`.

**Data model (before more migrations)**
- [x] Make `users.email` unique per tenant (`UNIQUE (tenant_id, email)`), not unique
      globally.
- [x] Add `tenant_id` to `document_chunk`, for direct tenant filters in every store.
- [x] Replace the free-form `source_locator` with the typed `chunk_span` table (section 4).
- [ ] Deduplicate by content: the same `checksum` in the same tenant → reuse the chunks.

**Security baseline**
- [ ] Until authentication exists, register the tenant and user write endpoints only when
      `ENVIRONMENT=development`.

**CI/CD**
- [x] Replace the AWS placeholder deploy workflow. Build the backend image on `main` and
      push it to GHCR.
- [x] Add a frontend job: `npm ci`, `oxlint`, `tsc -b`, `vite build`.
- [x] Add `.github/dependabot.yml` with grouped weekly updates (uv, npm, GitHub Actions).
- [ ] Protect `main`: require the test check and a pull request.

**Documentation**
- [ ] Create `docs/adr/`. Record the decisions in section 9 as they are made.

## 6. Roadmap

Each phase ends with a demo, tests, and an updated evaluation result.

### Phase 1 — Ingestion (parse and chunk)
- [x] Presigned upload, MinIO event, Kafka, Temporal workflow, document and job records
- [ ] `parse_document` activity: Docling → `DoclingDocument` JSON in MinIO
      (`parsed/<document_id>.json`). Start with PDF; add DOCX, PPTX and XLSX later
- [x] Separate worker image for parsing (Docling is CPU- and memory-heavy). The API
      image stays small (Dockerfile targets `api` and `worker`)
- [x] Separate Temporal task queue for parsing, so heavy files do not block short
      activities
- [x] Chunking in `process_document_activity`: Docling `HybridChunker` (structure- and
      token-aware) → `document_chunk` and `chunk_span` in one transaction, idempotent
- [ ] Update `current_stage` after each activity
- [ ] Frontend: upload page (presigned PUT) and a document list with status polling
- **Exit:** upload a 10-K PDF → `GET /documents/{id}/chunks` returns chunks with page and
  box

### Phase 2 — Retrieval
- [ ] `Embedder` port. Adapter: a small local model (for example a BGE or E5 variant) or
      a hosted API
- [ ] `VectorIndex` port and adapter (ADR-001). `embed_chunks` activity: batched,
      idempotent upsert by `chunk_id`
- [ ] Keyword search with Postgres full-text search (`tsvector`). Hybrid ranking with
      reciprocal rank fusion. No new service needed
- [ ] `POST /api/v1/search` → chunks with evidence spans
- [ ] **Evaluation set v0:** 30–50 questions on 3–5 filings, each with gold evidence
      chunks. Metrics: recall@k and MRR. Run them as a script
- [ ] Frontend: search page, source list, PDF viewer (pdf.js) with highlighted boxes
- **Exit:** a baseline recall@10 is recorded in `docs/evaluation.md`

### Phase 3 — GraphRAG
- [ ] Ontology v0 for the demo: `Company`, `Person`, `Product`, `Market`, `Event`; relations
      such as `INVESTS_IN`, `ACQUIRED`, `SUPPLIES`, `COMPETES_WITH`, `EMPLOYS`
- [ ] `extract_graph` activity: LLM structured output into Pydantic models (ADR-004).
      Cache by `chunk_hash` + `prompt_version` to control cost
- [ ] Entity resolution: normalised names, aliases, and external IDs (ticker, CIK) for
      companies
- [ ] Neo4j writer: `MERGE` only, uniqueness constraints, evidence on every edge
- [ ] Graph retrieval: link query entities → k-hop subgraph → evidence chunks
- [ ] Graph analytics: communities (Leiden), centrality (PageRank), shortest path. Check
      whether the chosen Neo4j tier has Graph Data Science. If not, compute in the worker
      (`igraph` + `leidenalg`) and write the results back
- [ ] Evaluation: extraction precision on a hand-labelled sample. Multi-hop questions in
      the evaluation set
- [ ] Frontend: D3 force graph. Click a node or edge → its evidence → PDF highlight
- **Exit:** multi-hop questions beat the Phase 2 baseline

### Phase 4 — Agentic querying
- [ ] LangGraph state machine: router → clarification (human-in-the-loop interrupt) →
      planner → tools → answer composer. Postgres checkpointer
- [ ] Tools: `vector_search`, `graph_query` (fixed Cypher templates first, read-only DB
      user), `get_evidence`. Later: text-to-Cypher
- [ ] Structured answer: `{answer, claims: [{text, kind, evidence_ids}]}`, validated
      against the retrieved evidence
- [ ] `POST /api/v1/chat` with SSE streaming
- [ ] MCP: expose the same tools through FastMCP. Add `search_web` and `extract_file`;
      a fetched file goes through the normal ingestion workflow (Temporal, `job_id`,
      progress via SSE)
- [ ] Frontend: chat panel. Master view (graph or chart) and detail view (sources)
- **Exit:** the demo questions are answered with valid citations

### Phase 5 — Application layer
- [ ] Visualisation planning: the LLM picks from a fixed set of chart specs (JSON). React
      and D3 render them
- [ ] Saved dashboards in Postgres
- [ ] Reports: a Temporal activity makes PPTX (`python-pptx`) and XLSX (`pandas`), writes
      them to MinIO and returns a presigned URL

### Phase 6 — Evaluation and observability
- [ ] RAGAS (faithfulness, context precision and recall) and an LLM judge on the
      evaluation set. Run nightly or by hand, not on every pull request (cost)
- [ ] OpenTelemetry: FastAPI, Temporal interceptors, LangGraph spans. Export to Grafana
      Cloud
- [ ] Track tokens, cost and latency per query and per ingestion job

### Phase 7 — Production
- [ ] Authentication: an OIDC provider and JWT validation. The tenant comes from the token
- [ ] Authorisation: roles per tenant
- [ ] Tenant isolation in every store: Postgres filters (later row-level security), vector
      payload filter, Neo4j tenant property
- [ ] Rate limits, secret management, database backups
- [ ] Deployment (section 8)

## 7. Evaluation plan (summary)

| Level | Metric | From phase |
| --- | --- | --- |
| Retrieval | recall@k, MRR on gold evidence | 2 |
| Extraction | precision and recall on labelled chunks | 3 |
| Answers | faithfulness, citation validity, LLM judge | 4 |
| System | latency p95, cost per query, ingestion time per page | 6 |

The evaluation set lives in the repository. It changes only through a pull request, so
results stay comparable.

## 8. Deployment (free tier, checked Nov 2026: verify before use)

| Component | Option | Limit to know |
| --- | --- | --- |
| API | Render free web service | Sleeps after 15 min idle (cold start) |
| Frontend | Static hosting (for example a Render static site) | — |
| Postgres | Neon free | 1 GB per project, scales to zero |
| Object storage | Cloudflare R2 (10 GB, no egress fees) | Sends events to Cloudflare Queues, not Kafka → use the webhook path |
| Kafka | Aiven free | 5 topics, low throughput, powers off after 24 h idle |
| Temporal + workers | Self-host on an Oracle Always Free VM | No free Temporal Cloud tier |
| Neo4j | AuraDB Free | 200k nodes, 400k relationships |
| Vector store (if Qdrant) | Qdrant Cloud free | 1 GB RAM, suspended when inactive |
| LLM | Groq or Gemini free tiers; Ollama locally | Rate limits change often |
| Observability | Grafana Cloud free | 14-day retention |

## 9. Decisions to record (ADRs)

1. **ADR-001 Vector store:** Neo4j vector index (one store, no sync) or Qdrant (better
   vector features). *Note:* we start with Neo4j and keep the `VectorIndex` port.
2. **ADR-002 Embedding model** and its dimension. Changing it later means re-embedding
   every chunk.
3. **ADR-003 LLM provider** for extraction and for chat.
4. **ADR-004 Extraction library:** LangExtract or Instructor with Pydantic.
5. **ADR-005 Event path in the cloud:** Kafka, or storage webhook → API.
6. **ADR-006 Agent runtime:** inside the API process, or as its own service.
7. **ADR-007 Auth provider.**

## 10. Risks

| Risk | Mitigation |
| --- | --- |
| LLM extraction cost on long filings | Cache by chunk hash; small model for extraction; limit pages in the demo |
| Duplicate or wrong entities | Entity resolution with external IDs; precision measured in Phase 3 |
| Hallucinated citations | Validate evidence IDs in code |
| Free-tier sleep and limits | Demo mode with warm-up; ports allow a quick provider change |
| Scope creep from the full diagram | Exit criteria per phase; add components only for a measured need |

## 11. Demonstration scenario: market ecosystem intelligence

Corpus: 10-K filings of five large US tech companies, two years each.

Example questions:
- "Which companies does Microsoft list as competitors, and which of them does it also
  partner with?"
- "Show the investment relationships between these five companies."
- "Which risk factors appear in all five filings?"

Example output: a graph of companies and relations, a three-sentence answer whose claims
are marked as source or inferred, and a source list that opens each PDF at the
highlighted span.
