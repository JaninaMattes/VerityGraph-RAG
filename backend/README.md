## Backend project structure

```
backend/
├── Dockerfile
├── pyproject.toml
├── README.md
│
└── src/
    │
    ├── main.py
    ├── config.py
    ├── dependencies.py
    ├── exceptions.py
    │
    ├── api/
    │   ├── router.py
    │   ├── middleware.py
    │   │
    │   └── routers/
    │       ├── chat.py
    │       ├── documents.py
    │       ├── ingestion.py
    │       ├── knowledge.py
    │       ├── agents.py
    │       ├── workflows.py
    │       └── health.py
    │
    ├── domain/
    │   │
    │   ├── documents/
    │   │   ├── models.py
    │   │   ├── schemas.py
    │   │   └── services.py
    │   │
    │   ├── knowledge/
    │   │   ├── entities.py
    │   │   ├── ontology.py
    │   │   ├── relationships.py
    │   │   └── provenance.py
    │   │
    │   ├── conversations/
    │   │   ├── models.py
    │   │   └── schemas.py
    │   │
    │   └── users/
    │       ├── models.py
    │       └── permissions.py
    │
    ├── ingestion/
    │   │
    │   ├── pipelines.py
    │   ├── parsers.py
    │   ├── chunking.py
    │   ├── metadata.py
    │   ├── extraction.py
    │   └── enrichment.py
    │
    ├── knowledge/
    │   │
    │   ├── graph/
    │   │   ├── neo4j_client.py
    │   │   ├── graph_builder.py
    │   │   ├── cypher.py
    │   │   └── community_detection.py
    │   │
    │   ├── retrieval/
    │   │   ├── vector.py
    │   │   ├── graph.py
    │   │   ├── hybrid.py
    │   │   ├── reranker.py
    │   │   └── planner.py
    │   │
    │   ├── embeddings/
    │   │   ├── encoder.py
    │   │   └── models.py
    │   │
    │   └── citations/
    │       ├── resolver.py
    │       └── provenance.py
    │
    ├── agents/
    │   │
    │   ├── graph.py
    │   ├── state.py
    │   ├── nodes.py
    │   ├── prompts/
    │   │
    │   ├── planner/
    │   │   └── agent.py
    │   │
    │   ├── research/
    │   │   └── agent.py
    │   │
    │   ├── analyst/
    │   │   └── agent.py
    │   │
    │   ├── visualization/
    │   │   └── agent.py
    │   │
    │   └── report/
    │       └── agent.py
    │
    ├── workflows/
    │   │
    │   ├── temporal.py
    │   │
    │   ├── ingestion/
    │   │   ├── workflow.py
    │   │   └── activities.py
    │   │
    │   ├── research/
    │   │   ├── workflow.py
    │   │   └── activities.py
    │   │
    │   └── evaluation/
    │       ├── workflow.py
    │       └── activities.py
    │
    ├── tools/
    │   │
    │   ├── mcp/
    │   │   ├── client.py
    │   │   └── registry.py
    │   │
    │   ├── web/
    │   │   ├── scraper.py
    │   │   └── search.py
    │   │
    │   ├── financial/
    │   │   └── sec.py
    │   │
    │   ├── analytics/
    │   │   └── python.py
    │   │
    │   └── export/
    │       ├── powerpoint.py
    │       └── excel.py
    │
    ├── infrastructure/
    │   │
    │   ├── database/
    │   │   ├── postgres.py
    │   │   └── migrations/
    │   │
    │   ├── vectorstore/
    │   │   └── qdrant.py
    │   │
    │   ├── graphdb/
    │   │   └── neo4j.py
    │   │
    │   ├── storage/
    │   │   └── minio.py
    │   │
    │   ├── llm/
    │   │   ├── ollama.py
    │   │   ├── vllm.py
    │   │   └── providers.py
    │   │
    │   └── cache/
    │       └── redis.py
    │
    ├── evaluation/
    │   │
    │   ├── datasets.py
    │   ├── ragas.py
    │   ├── benchmarks.py
    │   └── scoring.py
    │
    └── observability/
        ├── tracing.py
        ├── metrics.py
        └── logging.py
```

### Project Structure

```
src/
├── api/                    # ONLINE SERVING LAYER (FastAPI HTTP/WebSocket)
│   ├── routers/            # HTTP endpoints (chat, upload, health)
│   ├── middleware.py       # Auth, CORS, Logging
│   └── dependencies.py     # FastAPI dependency injection
│
├── agents/                 # AGENTIC ORCHESTRATION (LangGraph)
│   ├── state.py            # AgentState (TypedDict)
│   ├── workflows/          # Graph definitions (e.g., rag_graph.py)
│   └── nodes/              # Planner, Retriever, Responder, Tool nodes
│
├── domain/                 # CORE BUSINESS LOGIC (DDD - Keep as is)
│   ├── documents/          # Entities, Repositories (Interfaces), Services
│   ├── chunks/             # Entities, Repositories, Services
│   ├── ingestions/         # Job tracking, state management
│   ├── graph/              #  Graph entities (Nodes, Edges) & logic
│   ├── tenants/            # Multi-tenancy logic
│   └── users/              # User logic
│
├── infrastructure/         #  EXTERNAL SYSTEMS & ADAPTERS
│   ├── database/
│   │   ├── postgres/       # SQLAlchemy setup, Repositories impl
│   │   ├── neo4j/          # Neo4j driver, session, Cypher queries
│   │   └── qdrant/         # Qdrant client, vector search
│   ├── message_broker/     # Kafka/Redpanda producers & consumers
│   ├── storage/            # MinIO/S3 client
│   └── ai/                 # LLM, Embedding, Reranker clients (from article)
│       ├── llm.py
│       ├── embeddings.py
│       └── rerankers.py
│
├── pipelines/              # OFFLINE DATA PROCESSING (From Article)
│   └── ingestion/
│       ├── config.py       # Chunk sizes, batch sizes
│       ├── loaders/        # PDF, DOCX, HTML parsers
│       ├── chunking/       # Semantic splitters, metadata enrichment
│       ├── embedding/      # Batch embedders (calls infrastructure/ai)
│       ├── graph/          # Entity extraction & Ontology schema
│       └── indexing/       # Writers for Postgres, Qdrant, Neo4j
│
├── mcp/                    #  MODEL CONTEXT PROTOCOL (Agent Interface)
│   ├── server.py           # MCP Server definition
│   └── tools/              # Exposed tools (graph_search, vector_search)
│
├── evaluation/             # QUALITY & BENCHMARKS
│   ├── datasets.py
│   ├── ragas.py
│   └── scoring.py
│
── observability/          # MONITORING (Moved from shared for visibility)
│   ├── logging.py
│   ├── metrics.py
│   └── tracing.py
│
└── shared/                 # SHARED UTILITIES (Kept to minimize refactoring)
    ├── core/               # Pydantic Settings (config.py)
    ├── schemas/            # Pydantic models for API requests/responses
    ├── enums/              # Enums (DocumentStatus, etc.)
    └── exceptions/         # Custom exceptions
```

## Event-driven Pattern

To maintain scalability and remove potential bottleneck form FastAPI, this project entirely decouple upload from processing of the uploaded file.

```
1. User uploads → FastAPI creates presigned URL
2. FastAPI creates Document record: status="UPLOAD_PENDING"
3. Client uploads directly to MinIO
4. MinIO triggers Kafka event: "file.uploaded"
5. Kafka Consumer updates: status="UPLOADED"
6. Kafka Consumer triggers Temporal workflow
7. Temporal workflow updates: status="PROCESSING" → "COMPLETED"
```