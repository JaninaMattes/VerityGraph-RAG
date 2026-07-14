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