# MindBank API Reference

Base URL: `http://localhost:8095/api/v1`

All endpoints accept and return JSON unless noted.

## Authentication

Set `MB_API_KEY` in `.env` to require Bearer token auth on all endpoints.

```
Authorization: Bearer YOUR_API_KEY
```

If `MB_API_KEY` is empty, auth is disabled (development mode).

## Nodes

### Create Node

```
POST /api/v1/nodes
```

Request:
```json
{
  "label": "Use JWT for auth",
  "node_type": "decision",
  "content": "JWT with access + refresh tokens",
  "summary": "Short description (optional)",
  "namespace": "my-project",
  "importance": 0.8
}
```

Response: `201 Created` — the full node object.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| label | string | Yes | Short name (max 512 chars) |
| node_type | string | Yes | One of the 12 node types |
| content | string | No | Full content (max 50KB) |
| summary | string | No | Short summary (max 1KB) |
| namespace | string | No | Project namespace (default: "global") |
| importance | float | No | 0.0-1.0 (default: 0.5) |
| metadata | object | No | JSON metadata |

### Get Node

```
GET /api/v1/nodes/{id}
```

Returns the current version of a node. Temporal: returns 404 if node was updated (old version has `valid_to` set).

### Update Node

```
PUT /api/v1/nodes/{id}
```

Request (only these fields are updatable):
```json
{
  "content": "Updated content",
  "summary": "Updated summary",
  "importance": 0.9
}
```

**Temporal versioning:** This creates a NEW node with a new ID. The old node gets `valid_to` set. Always use the new ID from the response for subsequent operations.

### Delete Node

```
DELETE /api/v1/nodes/{id}
```

Soft-delete: sets `valid_to` to now. Node is preserved for temporal queries. Connected edges are also soft-deleted.

### List Nodes

```
GET /api/v1/nodes?namespace=my-project&type=decision&limit=50&offset=0
```

| Param | Type | Description |
|-------|------|-------------|
| namespace | string | Filter by namespace |
| type | string | Filter by node type |
| limit | int | Max results (default 50, max 100) |
| offset | int | Pagination offset |

### Batch Create

```
POST /api/v1/nodes/batch
```

```json
{
  "nodes": [
    {"label": "Node 1", "node_type": "fact", "content": "...", "namespace": "test"},
    {"label": "Node 2", "node_type": "decision", "content": "...", "namespace": "test"}
  ]
}
```

Max 100 nodes per batch.

### Auto-Connect

```
POST /api/v1/nodes/auto-connect
```

```json
{"namespace": "my-project"}
```

Creates semantic edges between related nodes based on type-matching rules. Returns count of edges created.

### Dedup

```
POST /api/v1/nodes/dedup?namespace=my-project&dry_run=true
```

Finds duplicate nodes (same label + type + namespace) and soft-deletes older versions.

| Param | Type | Description |
|-------|------|-------------|
| namespace | string | Scope to namespace (empty = all) |
| dry_run | bool | If true, report only (default: false) |

## Edges

### Create Edge

```
POST /api/v1/edges
```

```json
{
  "source_id": "node-uuid-1",
  "target_id": "node-uuid-2",
  "edge_type": "contains",
  "weight": 1.0
}
```

Valid edge types: `contains`, `relates_to`, `depends_on`, `decided_by`, `participated_in`, `produced`, `contradicts`, `supports`, `temporal_next`, `mentions`, `learned_from`

### List Edges

```
GET /api/v1/edges?type=contains&limit=500
```

### Get Node Neighbors

```
GET /api/v1/nodes/{id}/neighbors?depth=2&limit=100
```

Returns nodes connected to the given node. `depth` controls traversal depth (1-3).

### Batch Create Edges

```
POST /api/v1/edges/batch
```

```json
{
  "edges": [
    {"source_id": "...", "target_id": "...", "edge_type": "contains", "weight": 1.0},
    {"source_id": "...", "target_id": "...", "edge_type": "depends_on", "weight": 0.8}
  ]
}
```

Max 200 edges per batch.

## Search

### Full-Text Search

```
GET /api/v1/search?q=jwt+auth&namespace=my-project&limit=10
```

PostgreSQL full-text search with synonym expansion and trigram fallback.

### Hybrid Search

```
POST /api/v1/search/hybrid
```

```json
{
  "query": "how do we handle authentication",
  "namespace": "my-project",
  "limit": 10
}
```

Combines full-text search + vector semantic search via Reciprocal Rank Fusion. Includes graph expansion — finds nodes connected via edges even if text doesn't match.

### Semantic Search

```
POST /api/v1/search/semantic
```

```json
{
  "query": "database configuration",
  "namespace": "my-project",
  "limit": 10
}
```

Pure vector similarity search.

## Ask

```
POST /api/v1/ask
```

```json
{
  "query": "what database are we using?",
  "namespace": "my-project",
  "max_tokens": 500
}
```

Natural language Q&A. Returns relevant nodes and graph paths formatted as context.

## Snapshot

```
GET /api/v1/snapshot?namespace=my-project
```

Pre-computed context of the most important memories. Use this at session start to load relevant context. Results are importance-scored and deduplicated.

## Graph

```
GET /api/v1/graph?namespace=my-project
```

Returns all current nodes and edges. Used by the web dashboard.

## Export / Import

```
GET /api/v1/export?namespace=my-project
POST /api/v1/import
```

Export graph as JSON, import from JSON. Useful for backups and migrations.

## Embeddings

```
POST /api/v1/embeddings/generate
```

```json
{"text": "text to embed"}
```

Returns 768-dim vector from nomic-embed-text via Ollama.

## Health & Metrics

```
GET /api/v1/health
```
Returns: `{"status":"ok","postgres":"connected","ollama":"connected","version":"0.1.0"}`

```
GET /api/v1/metrics
```
Returns Prometheus-format metrics: node counts by namespace, edge counts, up status.

## Temporal Versioning

When you `PUT /nodes/{id}`, MindBank:
1. Creates a new node with a new UUID
2. Sets `valid_to` on the old node
3. Links new → old via `predecessor_id`
4. Increments `version`
5. Relinks all edges from old ID to new ID

This means:
- `GET /nodes/{id}` returns only current versions (`valid_to IS NULL`)
- `GET /nodes/{id}/history` returns all versions
- Old data is never lost
- Edges always point to the current version
