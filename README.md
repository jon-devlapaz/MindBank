# MindBank — AI Memory Bank for Hermes

Go + PostgreSQL mindmap memory system with semantic search, temporal versioning, and graph traversal.

## Quick Start (Docker)

```bash
docker compose up -d
docker compose exec mindbank-ollama ollama pull nomic-embed-text
curl http://localhost:8095/api/v1/health
```

## Native Install

Requires: PostgreSQL 15+ with pgvector, Go 1.23+, Ollama

```bash
# Install pgvector
cd /tmp && git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector && make && sudo make install

# Install Ollama + embedding model
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull nomic-embed-text

# Create database
createdb mindbank

# Build and run
make build
MB_DB_DSN="postgres://localhost:5432/mindbank?sslmode=disable" ./mindbank
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check (postgres + ollama status) |
| **Nodes** | | |
| POST | `/api/v1/nodes` | Create a node |
| GET | `/api/v1/nodes` | List nodes (?workspace, ?namespace, ?type) |
| GET | `/api/v1/nodes/{id}` | Get node by ID (bumps access count) |
| PUT | `/api/v1/nodes/{id}` | Update node (creates new temporal version) |
| DELETE | `/api/v1/nodes/{id}` | Soft-delete node (valid_to set) |
| GET | `/api/v1/nodes/{id}/neighbors` | Connected nodes (?depth=N for multi-hop) |
| GET | `/api/v1/nodes/{id}/path/{target}` | Shortest path between nodes |
| GET | `/api/v1/nodes/{id}/history` | Temporal version history |
| **Edges** | | |
| POST | `/api/v1/edges` | Create an edge |
| GET | `/api/v1/edges` | List edges (?type=...) |
| DELETE | `/api/v1/edges/{id}` | Delete an edge |
| **Batch** | | |
| POST | `/api/v1/nodes/batch` | Batch create nodes (array) |
| POST | `/api/v1/edges/batch` | Batch create edges (array) |
| **Maintenance** | | |
| POST | `/api/v1/nodes/{id}/relink` | Relink edges after node update |
| POST | `/api/v1/nodes/{id}/purge` | Purge old temporal versions |
| POST | `/api/v1/connect` | Auto-connect nodes by similarity |
| POST | `/api/v1/nodes/dedup` | Deduplicate similar nodes |
| POST | `/api/v1/export` | Export graph to JSON |
| POST | `/api/v1/import` | Import graph from JSON |
| **Search** | | |
| GET | `/api/v1/search?q=...` | Full-text search (ts_rank_cd) |
| POST | `/api/v1/search/semantic` | Semantic search (pgvector) |
| POST | `/api/v1/search/hybrid` | Hybrid search (FTS + vector RRF) |
| **Sessions** | | |
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions` | List sessions (?workspace, ?active) |
| GET | `/api/v1/sessions/{id}` | Get session |
| POST | `/api/v1/sessions/{id}/messages` | Add messages (+ auto-extraction) |
| GET | `/api/v1/sessions/{id}/context` | Get token-limited context |
| POST | `/api/v1/sessions/{id}/close` | Close session |
| **Ask + Snapshot** | | |
| POST | `/api/v1/ask` | Natural language query → structured context |
| GET | `/api/v1/snapshot` | Pre-computed wake-up context |
| POST | `/api/v1/snapshot/rebuild` | Regenerate snapshot |

## Architecture

- **Temporal versioning**: Never delete. `valid_from`/`valid_to` + version chains (dual history path).
- **Hybrid search**: FTS (tsvector/ts_rank_cd) + semantic (pgvector HNSW) with Reciprocal Rank Fusion.
- **Local embeddings**: nomic-embed-text:v1.5 via Ollama (768 dims, ~270MB, no API keys).
- **Graph traversal**: Recursive CTEs for N-hop neighbors + BFS shortest path.
- **Per-project namespaces**: Isolated or unified graph modes.
- **Importance scoring**: 5-factor (recency 30%, frequency 25%, connectivity 20%, explicit 15%, type 10%).
- **Rule-based extraction**: Auto-extracts decisions, questions, preferences, problems, advice, URLs, IPs from messages.
- **LLM-based extraction**: Optional background LLM extraction (pluggable, OpenAI-compatible).
- **Ask API**: Natural language query → hybrid search → structured context (no LLM cost on mindbank side).
- **Snapshots**: Pre-computed wake-up context of top-N important nodes.
- **MCP server**: Stdio MCP protocol — 6 tools for any AI agent to query mindbank.
- **Background embedding worker**: Async queue processor with retry (3 attempts max).

## MCP Tools (for AI agents)

| Tool | Description |
|------|-------------|
| `mindbank_create_node` | Create a node in the mindmap |
| `mindbank_search` | Hybrid FTS + semantic search |
| `mindbank_ask` | Natural language question → context |
| `mindbank_snapshot` | Get pre-computed wake-up context |
| `mindbank_neighbors` | Get connected nodes (graph traversal) |
| `mindbank_create_edge` | Create a connection between nodes |

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MB_PORT` | 8095 | HTTP server port |
| `MB_DB_DSN` | `postgres://mindbank:mindbank@localhost:5432/mindbank?sslmode=disable` | PostgreSQL DSN |
| `MB_OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `MB_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `MB_LOG_LEVEL` | `info` | Log level (debug/info/warn/error) |
