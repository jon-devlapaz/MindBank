#!/usr/bin/env python3
"""
MindBank Python Example
Demonstrates basic operations: create, search, ask, graph traversal.
"""

import json
import urllib.request

API = "http://localhost:8095/api/v1"


def api(path, body=None, method=None):
    """Make an API call to MindBank."""
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    if method is None:
        method = "POST" if body else "GET"
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    # Check health
    health = api("/health")
    print(f"Status: {health['status']}")
    print(f"Postgres: {health['postgres']}")
    print(f"Ollama: {health['ollama']}")
    print()

    # Create nodes
    project = api("/nodes", {
        "label": "My Web App",
        "node_type": "project",
        "content": "A web application built with Go and React",
        "namespace": "example",
    })
    print(f"Created project: {project['label']} ({project['id'][:8]}...)")

    decision = api("/nodes", {
        "label": "Use PostgreSQL for data",
        "node_type": "decision",
        "content": "PostgreSQL with pgvector for both relational and vector data",
        "namespace": "example",
        "importance": 0.8,
    })
    print(f"Created decision: {decision['label']} ({decision['id'][:8]}...)")

    fact = api("/nodes", {
        "label": "API runs on port 8080",
        "node_type": "fact",
        "content": "The Go API server listens on port 8080",
        "namespace": "example",
    })
    print(f"Created fact: {fact['label']} ({fact['id'][:8]}...)")
    print()

    # Connect them
    edge = api("/edges", {
        "source_id": project["id"],
        "target_id": decision["id"],
        "edge_type": "contains",
    })
    print(f"Created edge: {edge['source_id'][:8]}... --{edge['edge_type']}--> {edge['target_id'][:8]}...")

    edge2 = api("/edges", {
        "source_id": project["id"],
        "target_id": fact["id"],
        "edge_type": "contains",
    })
    print(f"Created edge: {edge2['source_id'][:8]}... --{edge2['edge_type']}--> {edge2['target_id'][:8]}...")
    print()

    # Search
    results = api("/search/hybrid", {
        "query": "what database are we using",
        "namespace": "example",
        "limit": 5,
    })
    print(f"Search 'what database are we using':")
    for r in results:
        print(f"  [{r.get('node_type')}] {r.get('label')}")
    print()

    # Ask
    answer = api("/ask", {
        "query": "what is my web app?",
        "namespace": "example",
        "max_tokens": 500,
    })
    print(f"Ask 'what is my web app?':")
    print(f"  {answer}")
    print()

    # Get neighbors
    neighbors = api(f"/nodes/{project['id']}/neighbors")
    print(f"Neighbors of '{project['label']}':")
    for n in neighbors:
        print(f"  [{n.get('node_type')}] {n.get('label')} (via {n.get('edge_type')})")
    print()

    # Snapshot
    snapshot = api("/snapshot?namespace=example")
    print("Morning snapshot:")
    print(f"  {snapshot[:200]}...")
    print()

    # Cleanup
    api(f"/nodes/{project['id']}", method="DELETE")
    api(f"/nodes/{decision['id']}", method="DELETE")
    api(f"/nodes/{fact['id']}", method="DELETE")
    print("Cleaned up example nodes.")


if __name__ == "__main__":
    main()
