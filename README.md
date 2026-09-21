<!--
*** Thanks for checking out this README Template. If you have a suggestion that would
*** make this better, please fork the repo and create a pull request or simply open
*** an issue with the tag "enhancement".
*** Thanks again! Now go create something AMAZING! :D
-->





<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]



<!-- PROJECT LOGO -->
<br />
<p align="center">
  <a href="https://github.com/othneildrew/Best-README-Template">
    <img src="docs/images/logo.png" alt="Logo" width="250" height="80">
  </a>

  <h2 align="center">VerityGraph: MCP-Powered Agentic GraphRAG Pipeline</h2>

  <p align="center">
    An event-driven, enterprise-grade data pipeline for complex relational reasoning and traceable AI insights.
    <br />
    <a href="https://github.com/othneildrew/Best-README-Template"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/othneildrew/Best-README-Template">View Demo</a>
    ·
    <a href="https://github.com/othneildrew/Best-README-Template/issues">Report Bug</a>
    ·
    <a href="https://github.com/othneildrew/Best-README-Template/issues">Request Feature</a>
  </p>
</p>



<!-- TABLE OF CONTENTS -->
## Table of Contents

- [Table of Contents](#table-of-contents)
- [About The Project](#about-the-project)
- [Key Capabilities \& Demo Use Case](#key-capabilities--demo-use-case)
- [System Design](#system-design)
  - [Built With](#built-with)
- [Getting Started](#getting-started)
  - [Project Backend Structure](#project-backend-structure)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
    - [Example: Manually upload/download file](#example-manually-uploaddownload-file)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)
- [Other Relevant Resources](#other-relevant-resources)



<!-- ABOUT THE PROJECT -->
## About The Project

Vanilla RAG systems commonly fail at complex, multi-hop relational queries (e.g., "How are the Big 5 US tech companies investing in each other?") and suffer from hallucinations because they lack structured context and source traceability.

VerityGraph on the other hand is an end-to-end Agentic GraphRAG system that combines the semantic search of Vector Databases (Qdrant) with the relational reasoning of Knowledge Graphs (Neo4j). Powered by the Model Context Protocol (MCP) and orchestrated via Temporal.io, it ingests raw financial documents asynchronously and exposes them through a stateful LLM agent.

## Key Capabilities & Demo Use Case
A user can gain deeper insights into structural information and relations of unstructured files using VerityGraph. For instance, a user might want to upload 500 pages of SEC 10-K filings and investment reports for a specific range of years, before asking the system:

_"Show me graphically how much and how the investment of company 'X' relates to the largest five tech companies in the USA over a timespan of 5 years starting at 2021."_

Instead of simply returning static chunks of text or a summary of text, VerityGraph performs the following:

1. Reasons & Queries: The Agentic workflow decomposes the prompt, queries the Neo4j Knowledge Graph for relational investment data, and retrieves specific chunks from Qdrant.
2. Visualizes: It dynamically generates a React-based interactive dashboard rendering a node-edge graph of the investment flows and capital amounts.
3. Proves (Traceability): Every node and metric in the dashboard is clickable, revealing the exact source document, page number, and text snippet; just like citations that we would expect in a peer-reviewed research paper.
4. Exports: Users can export the generated visual dashboard and the citation bibliography as a PDF/Excel report.

## System Design
![System Design Schema Screen Shot](./docs/images/system_design.png)

A scalable GraphRAG pipeline, built around agents, with six core layers:

1. Data Ingestion Layer: Converts raw input data (e.g., PDFs, CSVs) into structured knowledge via document loading, chunking, and indexing; scalable with S3, RDBMS, and Ray.
2. Hybrid Retrieval: Combines Neo4j (Cypher) for topology/graph traversal and Qdrant (HNSW) for semantic vector search.
3. MCP Integration: Standardizes how the LLM agent safely calls external tools (Web Search, Python code execution for charting, Database queries).
4. Observability: Full OpenTelemetry tracing across the API, Temporal workflows, and LLM calls.

A list of commonly used resources are listed in the acknowledgements.
A list of commonly used resources are listed in the acknowledgements.

### Built With
This section should list any major frameworks that you built your project using. Leave any add-ons/plugins for the acknowledgements section. Here are a few examples.
* [Bootstrap](https://getbootstrap.com)
* [JQuery](https://jquery.com)
* [Laravel](https://laravel.com)



<!-- GETTING STARTED -->
## Getting Started

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

### Project Backend Structure

Vanilla agentic RAG pipelines are defined over a codebase that currently typically contains a single vector database, some AI models, and a simple ingestion pipeline. However, for this project the structure is broken up into smaller manageable components to avoid the complexity and coupling that is often found in a monolithic codebase. The following is a list of the components that are broken out into their own folders:

```
src/
├── api/                    # ONLINE SERVING LAYER (FastAPI HTTP/WebSocket)
│   ├── routers/            # HTTP endpoints (LLM chat, presigned URL generation, health)
│   ├── middleware.py       # Auth, CORS, Logging
│   └── dependencies.py     # FastAPI dependency injection
│
├── agents/                 # AGENTIC ORCHESTRATION (LangGraph)
├── domain/                 # CORE BUSINESS LOGIC (Domain Driven Design)
├── infrastructure/         # DATA STORAGE (MinIO/S3), EXTERNAL SYSTEMS & ADAPTERS
│   ├── database/
│   │   ├── postgres/       # SQLAlchemy setup, Repositories impl
│   │   ├── neo4j/          # Neo4j driver, session, Cypher queries
│   │   └── qdrant/         # Qdrant client, vector search
│   ├── message_broker/     # Kafka/Redpanda producers & consumers
│   ├── storage/            # MinIO/S3 client
│   └── models/             # AI models (LLM, Embedding, Reranker clients)
│
├── pipelines/              # OFFLINE DATA PROCESSING
│   └── ingestion/
│       ├── config.py       # Chunk sizes, batch sizes
│       ├── loaders/        # PDF, DOCX, HTML parsers
│       ├── chunking/       # Semantic splitters, metadata enrichment
│       ├── embedding/      # Batch embedders (calls infrastructure/ai)
│       ├── graph/          # Entity extraction & Ontology schema
│       └── indexing/       # Writers for Postgres, Qdrant, Neo4j
│
├── mcp/                    # MODEL CONTEXT PROTOCOL (Agent Interface)
├── evaluation/             # QUALITY & BENCHMARKS
├── observability/          # MONITORING
└── shared/                 # SHARED UTILITIES
    ├── core/               # Pydantic Settings (config.py)
    ├── schemas/            # Pydantic models for API requests/responses
    ├── enums/              # Enums (DocumentStatus, etc.)
    └── exceptions/         # Custom exceptions
```

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.
* npm
```sh
npm install npm@latest -g
```

### Installation

1. Get a free API Key at [https://example.com](https://example.com)
2. Clone the repo
```sh
git clone https://github.com/your_username_/Project-Name.git
```
3. Install NPM packages
```sh
npm install
```
4. Enter your API in `config.js`
```JS
const API_KEY = 'ENTER YOUR API';
```



<!-- USAGE EXAMPLES -->
## Usage

Use this space to show useful examples of how a project can be used. Additional screenshots, code examples and demos work well in this space. You may also link to more resources.

_For more examples, please refer to the [Documentation](https://example.com)_


#### Example: Manually upload/download file

1. Upload file
```
curl -v \
  -X PUT \
  -H "Content-Type: application/pdf" \
  --upload-file <your-file-path> \
  <presigned-URL-from-MinIO-S3-bucket>
```

2. Download file
``` 
  curl -o <filename> \
  <presigned-URL-from-MinIO-S3-bucket>
```


<!-- ROADMAP -->
## Roadmap

See the [open issues](https://github.com/othneildrew/Best-README-Template/issues) for a list of proposed features (and known issues).



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.



<!-- CONTACT -->
## Contact

Your Name - [@your_twitter](https://twitter.com/your_username) - email@example.com
Project Link: [https://github.com/your_username/repo_name](https://github.com/your_username/repo_name)



<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
* [Aiokafka - Apache Kafka client for asyncio](https://aiokafka.readthedocs.io/en/stable/consumer.html)



## Other Relevant Resources
* [Medium Article - Building Enterprise Python Microservices with FastAPI in 2025](https://blog.devops.dev/building-enterprise-python-microservices-with-fastapi-in-2025-10-10-kafka-saga-choreography-aeb9781b00a6)
* [Temporal.io - Set up PostgreSQL Visibility store](https://docs.temporal.io/self-hosted-guide/visibility/postgresql)



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/othneildrew/Best-README-Template.svg?style=flat-square
[contributors-url]: https://github.com/othneildrew/Best-README-Template/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/othneildrew/Best-README-Template.svg?style=flat-square
[forks-url]: https://github.com/othneildrew/Best-README-Template/network/members
[stars-shield]: https://img.shields.io/github/stars/othneildrew/Best-README-Template.svg?style=flat-square
[stars-url]: https://github.com/othneildrew/Best-README-Template/stargazers
[issues-shield]: https://img.shields.io/github/issues/othneildrew/Best-README-Template.svg?style=flat-square
[issues-url]: https://github.com/othneildrew/Best-README-Template/issues
[license-shield]: https://img.shields.io/github/license/othneildrew/Best-README-Template.svg?style=flat-square
[license-url]: https://github.com/othneildrew/Best-README-Template/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=flat-square&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/othneildrew
[product-screenshot]: docs/system_design.png
