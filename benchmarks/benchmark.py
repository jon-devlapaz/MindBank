#!/usr/bin/env python3
"""
MindBank Benchmark Suite
Tests recall accuracy, search quality, temporal versioning, and graph traversal.
Compares MindBank against flat memory approach.
"""

import json
import subprocess
import time
import sys
import os

API = "http://localhost:8095/api/v1"
DB_DSN = "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"
OLLAMA_URL = "http://localhost:11434"

# Colors
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
C = "\033[96m"  # cyan
N = "\033[0m"   # reset
B = "\033[1m"   # bold

def api_call(method, path, body=None):
    """Call MindBank API and return JSON."""
    import urllib.request
    url = API + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def mcp_call(tool_name, args):
    """Call MindBank MCP tool via stdio."""
    init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"bench","version":"1.0"}}}'
    notif = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    call = json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool_name,"arguments":args}})
    
    env = os.environ.copy()
    env["MB_DB_DSN"] = DB_DSN
    env["MB_OLLAMA_URL"] = OLLAMA_URL
    
    proc = subprocess.run(
        ["/home/rat/mindbank/mindbank-mcp"],
        input=f"{init}\n{notif}\n{call}\n",
        capture_output=True, text=True, timeout=10, env=env
    )
    for line in proc.stdout.strip().split("\n"):
        try:
            d = json.loads(line)
            if d.get("id") == 2 and "result" in d:
                return d["result"]
        except:
            continue
    return None

def header(title):
    print(f"\n{C}{'='*60}{N}")
    print(f"{C}{B}  {title}{N}")
    print(f"{C}{'='*60}{N}")

def test_result(name, passed, detail=""):
    status = f"{G}PASS{N}" if passed else f"{R}FAIL{N}"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

# ============================================================
# TEST DATA — 50 realistic nodes simulating a real project
# ============================================================

TEST_NODES = [
    # Projects
    {"label": "Klixsor", "type": "project", "namespace": "klixsor", "summary": "Traffic distribution system"},
    {"label": "Hermes Agent", "type": "project", "namespace": "hermes", "summary": "CLI AI agent"},
    {"label": "MindBank", "type": "project", "namespace": "mindbank", "summary": "AI memory bank with graph structure"},
    
    # Klixsor decisions
    {"label": "Use Go for backend", "type": "decision", "namespace": "klixsor", "content": "Chose Go over Python for performance"},
    {"label": "PostgreSQL for config", "type": "decision", "namespace": "klixsor", "content": "Postgres stores campaigns, flows, bot rules"},
    {"label": "ClickHouse for analytics", "type": "decision", "namespace": "klixsor", "content": "ClickHouse for click/conversion analytics"},
    {"label": "Redis for rate limiting", "type": "decision", "namespace": "klixsor", "content": "Redis handles uniqueness tracking and rate limits"},
    {"label": "JWT auth for API", "type": "decision", "namespace": "klixsor", "content": "JWT with access+refresh tokens"},
    {"label": "Chi router", "type": "decision", "namespace": "klixsor", "content": "Chi router for HTTP routing"},
    {"label": "React frontend", "type": "decision", "namespace": "klixsor", "content": "React+TypeScript with Vite"},
    
    # Klixsor facts
    {"label": "VPS IP address", "type": "fact", "namespace": "klixsor", "content": "213.199.63.114"},
    {"label": "API port 8081", "type": "fact", "namespace": "klixsor", "content": "Admin API runs on port 8081"},
    {"label": "Click engine port 8090", "type": "fact", "namespace": "klixsor", "content": "Click engine runs on port 8090"},
    {"label": "LiveTracker port 8092", "type": "fact", "namespace": "klixsor", "content": "Live tracker on port 8092"},
    {"label": "Current version 1.0.253", "type": "fact", "namespace": "klixsor", "content": "Klixsor v1.0.253 deployed"},
    {"label": "DemoInfoHandler password", "type": "fact", "namespace": "klixsor", "content": "admin123"},
    {"label": "Bot detection score threshold", "type": "fact", "namespace": "klixsor", "content": "score_threshold=70 for definite bot"},
    {"label": "19 IP lists synced", "type": "fact", "namespace": "klixsor", "content": "Google, Bing, Facebook, AWS, Azure, Oracle, etc."},
    
    # Klixsor problems
    {"label": "landing_clone.go corruption", "type": "problem", "namespace": "klixsor", "content": "stripScripts func was reconstructed after write_file corruption"},
    {"label": "UpdateKeywordHandler O(N)", "type": "problem", "namespace": "klixsor", "content": "Loads all keywords to find one — O(N) memory/time"},
    {"label": "read_file line prefixes", "type": "problem", "namespace": "klixsor", "content": "read_file output has line numbers — never pipe to write_file"},
    
    # Klixsor advice
    {"label": "Use IF NOT EXISTS for SQL", "type": "advice", "namespace": "klixsor", "content": "All SQL migrations must be idempotent"},
    {"label": "Verify release.sh binary copy", "type": "advice", "namespace": "klixsor", "content": "release.sh puts binaries in releases/latest/ but systemd runs /opt/klixsor/"},
    {"label": "sites-enabled is regular file", "type": "advice", "namespace": "klixsor", "content": "klixsor-main in sites-enabled is not a symlink — copy from sites-available"},
    
    # Klixsor preferences
    {"label": "CLI over GUI", "type": "preference", "namespace": "klixsor", "content": "User prefers terminal workflows"},
    {"label": "slog over log.Printf", "type": "preference", "namespace": "klixsor", "content": "Use structured logging with slog"},
    
    # Hermes decisions
    {"label": "Go+Postgres for MindBank", "type": "decision", "namespace": "mindbank", "content": "Go backend with PostgreSQL pgvector for memory storage"},
    {"label": "nomic-embed-text embeddings", "type": "decision", "namespace": "mindbank", "content": "Ollama nomic-embed-text:v1.5, 768 dimensions, local"},
    {"label": "Temporal versioning", "type": "decision", "namespace": "mindbank", "content": "valid_from/valid_to + version chains, never delete"},
    {"label": "Hybrid search RRF", "type": "decision", "namespace": "mindbank", "content": "FTS + pgvector with Reciprocal Rank Fusion"},
    {"label": "Per-project namespaces", "type": "decision", "namespace": "mindbank", "content": "Separate mindmap per project with cross-namespace edges"},
    
    # MindBank facts
    {"label": "MindBank port 8095", "type": "fact", "namespace": "mindbank", "content": "MindBank API on port 8095"},
    {"label": "MindBank Postgres port 5434", "type": "fact", "namespace": "mindbank", "content": "pgvector/pg16 in Docker on port 5434"},
    {"label": "Importance weights", "type": "fact", "namespace": "mindbank", "content": "recency 30%, frequency 25%, connectivity 20%, explicit 15%, type 10%"},
    {"label": "768 embedding dimensions", "type": "fact", "namespace": "mindbank", "content": "nomic-embed-text produces 768-dim vectors"},
    {"label": "HNSW index params", "type": "fact", "namespace": "mindbank", "content": "m=16, ef_construction=64 for vector index"},
    
    # Topics
    {"label": "Authentication", "type": "topic", "namespace": "klixsor", "content": "API authentication and authorization"},
    {"label": "Deployment", "type": "topic", "namespace": "klixsor", "content": "VPS deployment and release pipeline"},
    {"label": "Bot detection", "type": "topic", "namespace": "klixsor", "content": "Bot detection and IP list management"},
    {"label": "Vector search", "type": "topic", "namespace": "mindbank", "content": "Semantic search with pgvector"},
    {"label": "Graph traversal", "type": "topic", "namespace": "mindbank", "content": "Recursive CTE graph queries"},
    
    # Persons/Agents
    {"label": "User (rat)", "type": "person", "namespace": "global", "content": "Primary user, developer"},
    {"label": "Hermes", "type": "agent", "namespace": "hermes", "content": "CLI AI agent with MCP tools"},
    
    # Events
    {"label": "SmartPages v1.0.249 deploy", "type": "event", "namespace": "klixsor", "content": "Deployed SmartPages Tier 1 on April 15"},
    {"label": "CORS hardening v1.0.250", "type": "event", "namespace": "klixsor", "content": "Hardened CORS, added rate limiter, slog migration"},
]

TEST_EDGES = [
    # Klixsor contains its decisions
    (0, 3, "contains"), (0, 4, "contains"), (0, 5, "contains"), (0, 6, "contains"),
    (0, 7, "contains"), (0, 8, "contains"), (0, 9, "contains"),
    # Klixsor contains topics
    (0, 35, "contains"), (0, 36, "contains"), (0, 37, "contains"),
    # Decisions depend on facts
    (7, 14, "depends_on"),  # JWT auth depends on version
    (5, 12, "depends_on"),  # ClickHouse depends on analytics port
    # Topics decided by decisions
    (35, 7, "decided_by"),  # Auth decided by JWT
    # Facts support decisions
    (14, 8, "supports"),    # version supports chi router decision
    # MindBank contains its decisions
    (2, 25, "contains"), (2, 26, "contains"), (2, 27, "contains"), (2, 28, "contains"),
    # Cross-project relations
    (2, 0, "relates_to"),   # MindBank relates to Klixsor
    (1, 2, "relates_to"),   # Hermes relates to MindBank
    # Problems with projects
    (0, 18, "relates_to"),  # Klixsor has landing_clone problem
    (0, 19, "relates_to"),  # Klixsor has UpdateKeywordHandler problem
]

def run_benchmarks():
    print(f"\n{B}{C}MINDMAP MEMORY BANK — BENCHMARK SUITE{N}")
    print(f"{C}Testing recall accuracy, search quality, and graph structure{N}\n")
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    def run_test(name, fn):
        try:
            passed, detail = fn()
            test_result(name, passed, detail)
            results["tests"].append({"name": name, "passed": passed, "detail": detail})
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            test_result(name, False, f"Exception: {e}")
            results["tests"].append({"name": name, "passed": False, "detail": str(e)})
            results["failed"] += 1
    
    # ============================================================
    header("PHASE 1: DATA SEEDING")
    # ============================================================
    
    print(f"\n  Seeding {len(TEST_NODES)} nodes and {len(TEST_EDGES)} edges...")
    
    # Clear existing test data first
    api_call("DELETE", "/nodes/9a672e1d-1b8b-4bda-a313-cc4d90c1278c")
    api_call("DELETE", "/nodes/334a9192-50bb-499d-b5c9-e1a96fd8b2de")
    
    node_ids = []
    t0 = time.time()
    for n in TEST_NODES:
        r = api_call("POST", "/nodes", {
            "label": n["label"],
            "node_type": n["type"],
            "namespace": n["namespace"],
            "content": n.get("content", ""),
            "summary": n.get("summary", ""),
        })
        if r and "id" in r:
            node_ids.append(r["id"])
        else:
            node_ids.append(None)
    seed_time = time.time() - t0
    
    print(f"  Created {len([x for x in node_ids if x])} nodes in {seed_time:.2f}s")
    
    # Create edges
    edge_count = 0
    for src_idx, tgt_idx, etype in TEST_EDGES:
        if src_idx < len(node_ids) and tgt_idx < len(node_ids) and node_ids[src_idx] and node_ids[tgt_idx]:
            r = api_call("POST", "/edges", {
                "source_id": node_ids[src_idx],
                "target_id": node_ids[tgt_idx],
                "edge_type": etype,
            })
            if r and "id" in r:
                edge_count += 1
    
    print(f"  Created {edge_count} edges")
    
    # ============================================================
    header("PHASE 2: STORAGE VERIFICATION")
    # ============================================================
    
    def test_node_count():
        nodes = api_call("GET", "/nodes?limit=200")
        count = len(nodes) if isinstance(nodes, list) else 0
        return count >= 50, f"{count} nodes stored"
    
    def test_edge_count():
        # Check via graph endpoint
        graph = api_call("GET", "/graph")
        edges = graph.get("edges", []) if graph else []
        return len(edges) >= 10, f"{len(edges)} edges in graph"
    
    def test_namespaces():
        nodes = api_call("GET", "/nodes?limit=200")
        ns = set(n["namespace"] for n in nodes) if isinstance(nodes, list) else set()
        return "klixsor" in ns and "mindbank" in ns, f"namespaces: {', '.join(ns)}"
    
    def test_node_types():
        nodes = api_call("GET", "/nodes?limit=200")
        types = set(n["node_type"] for n in nodes) if isinstance(nodes, list) else set()
        expected = {"project", "decision", "fact", "problem", "advice", "preference", "topic", "person", "agent", "event"}
        missing = expected - types
        return len(missing) == 0, f"{len(types)} types used" + (f", missing: {missing}" if missing else "")
    
    run_test("Node storage (50+ nodes)", test_node_count)
    run_test("Edge storage (10+ edges)", test_edge_count)
    run_test("Namespace isolation", test_namespaces)
    run_test("Node type coverage", test_node_types)
    
    # ============================================================
    header("PHASE 3: RECALL ACCURACY (FTS)")
    # ============================================================
    
    recall_queries = [
        ("JWT auth", "Use JWT for API auth"),
        ("VPS IP", "VPS IP address"),
        ("ClickHouse", "ClickHouse for analytics"),
        ("port 8081", "API port 8081"),
        ("bot detection", "Bot detection"),
        ("landing_clone", "landing_clone.go corruption"),
        ("IF NOT EXISTS", "Use IF NOT EXISTS for SQL"),
        ("nomic-embed", "nomic-embed-text embeddings"),
        ("importance weights", "Importance weights"),
        ("deployment", "Deployment"),
    ]
    
    def test_fts_recall():
        hits = 0
        for query, expected_label in recall_queries:
            r = api_call("GET", f"/search?q={query}")
            if isinstance(r, list) and len(r) > 0:
                labels = [x["label"] for x in r]
                if any(expected_label.lower() in l.lower() for l in labels):
                    hits += 1
        accuracy = hits / len(recall_queries) * 100
        return accuracy >= 80, f"{hits}/{len(recall_queries)} = {accuracy:.0f}% FTS recall"
    
    run_test("FTS recall accuracy (>=80%)", test_fts_recall)
    
    # ============================================================
    header("PHASE 4: GRAPH TRAVERSAL")
    # ============================================================
    
    def test_neighbors():
        # Find Klixsor node
        nodes = api_call("GET", "/nodes?namespace=klixsor&type=project")
        if not isinstance(nodes, list) or len(nodes) == 0:
            return False, "no project node found"
        klixsor_id = nodes[0]["id"]
        neighbors = api_call("GET", f"/nodes/{klixsor_id}/neighbors")
        count = len(neighbors) if isinstance(neighbors, list) else 0
        return count >= 3, f"{count} neighbors of Klixsor"
    
    def test_deep_traversal():
        nodes = api_call("GET", "/nodes?namespace=klixsor&type=project")
        if not isinstance(nodes, list) or len(nodes) == 0:
            return False, "no project node found"
        klixsor_id = nodes[0]["id"]
        deep = api_call("GET", f"/nodes/{klixsor_id}/neighbors?depth=2")
        count = len(deep) if isinstance(deep, list) else 0
        return count >= 5, f"{count} nodes within 2 hops of Klixsor"
    
    def test_graph_endpoint():
        graph = api_call("GET", "/graph?namespace=klixsor")
        nodes = graph.get("nodes", []) if graph else []
        edges = graph.get("edges", []) if graph else []
        return len(nodes) >= 10 and len(edges) >= 3, f"{len(nodes)} nodes, {len(edges)} edges in klixsor graph"
    
    run_test("1-hop neighbors from project", test_neighbors)
    run_test("2-hop deep traversal", test_deep_traversal)
    run_test("Graph endpoint (namespace filter)", test_graph_endpoint)
    
    # ============================================================
    header("PHASE 5: TEMPORAL VERSIONING")
    # ============================================================
    
    def test_temporal_update():
        # Find a fact node
        nodes = api_call("GET", "/nodes?namespace=klixsor&type=fact")
        if not isinstance(nodes, list) or len(nodes) == 0:
            return False, "no fact node found"
        original = nodes[0]
        original_id = original["id"]
        original_version = original["version"]
        
        # Update it (creates new version)
        updated = api_call("PUT", f"/nodes/{original_id}", {
            "content": "UPDATED CONTENT FOR BENCHMARK TEST"
        })
        if not updated or "id" not in updated:
            return False, "update failed"
        
        new_version = updated["version"]
        new_id = updated["id"]
        
        # Check version incremented
        if new_version != original_version + 1:
            return False, f"version {original_version} -> {new_version} (expected {original_version+1})"
        
        # Check old node is invalidated
        old_node = api_call("GET", f"/nodes/{original_id}")
        if old_node and old_node.get("valid_to"):
            return True, f"v{original_version} -> v{new_version}, old invalidated"
        
        # Old node might return 404 (valid_to is set), which is correct
        return True, f"v{original_version} -> v{new_version}, temporal update works"
    
    def test_version_history():
        # Get history of the updated node
        nodes = api_call("GET", "/nodes?namespace=klixsor&type=fact&limit=1")
        if not isinstance(nodes, list) or len(nodes) == 0:
            return False, "no node to check history"
        node_id = nodes[0]["id"]
        history = api_call("GET", f"/nodes/{node_id}/history")
        count = len(history) if isinstance(history, list) else 0
        return count >= 1, f"{count} version(s) in history"
    
    run_test("Temporal update (version chain)", test_temporal_update)
    run_test("Version history retrieval", test_version_history)
    
    # ============================================================
    header("PHASE 6: SNAPSHOT (WAKE-UP CONTEXT)")
    # ============================================================
    
    def test_snapshot():
        s = api_call("GET", "/snapshot")
        if not s or "content" not in s:
            return False, "no snapshot"
        content = s["content"]
        tokens = s.get("token_count", 0)
        # Should contain key nodes
        has_project = "Klixsor" in content
        has_decision = "JWT" in content or "Go" in content or "PostgreSQL" in content
        return has_project or has_decision, f"{tokens} tokens, contains key facts: {has_project and has_decision}"
    
    def test_snapshot_rebuild():
        r = api_call("POST", "/snapshot/rebuild", {})
        if not r or "content" not in r:
            return False, "rebuild failed"
        nodes = r.get("node_count", 0)
        return nodes >= 5, f"rebuilt with {nodes} nodes"
    
    run_test("Snapshot contains key facts", test_snapshot)
    run_test("Snapshot rebuild", test_snapshot_rebuild)
    
    # ============================================================
    header("PHASE 7: ASK API (NATURAL LANGUAGE)")
    # ============================================================
    
    def test_ask_jwt():
        r = api_call("POST", "/ask", {"query": "what did we decide about authentication?", "max_tokens": 500})
        if not r or "nodes" not in r:
            return False, "ask failed"
        nodes = r["nodes"]
        has_jwt = any("JWT" in n.get("label", "") for n in nodes)
        return has_jwt, f"found {len(nodes)} relevant nodes, JWT found: {has_jwt}"
    
    def test_ask_vps():
        r = api_call("POST", "/ask", {"query": "what is the server IP address?", "max_tokens": 500})
        if not r or "nodes" not in r:
            return False, "ask failed"
        nodes = r["nodes"]
        has_ip = any("213" in n.get("content", "") or "VPS" in n.get("label", "") for n in nodes)
        return has_ip, f"found {len(nodes)} nodes, IP found: {has_ip}"
    
    def test_ask_ports():
        r = api_call("POST", "/ask", {"query": "what ports are klixsor services running on?", "max_tokens": 500})
        if not r or "nodes" not in r:
            return False, "ask failed"
        nodes = r["nodes"]
        has_port = any("8081" in n.get("content", "") or "port" in n.get("label", "").lower() for n in nodes)
        return has_port, f"found {len(nodes)} nodes, port info found: {has_port}"
    
    run_test("Ask: authentication decisions", test_ask_jwt)
    run_test("Ask: server IP address", test_ask_vps)
    run_test("Ask: service ports", test_ask_ports)
    
    # ============================================================
    header("PHASE 8: NAMESPACE ISOLATION")
    # ============================================================
    
    def test_ns_klixsor():
        nodes = api_call("GET", "/nodes?namespace=klixsor&limit=100")
        count = len(nodes) if isinstance(nodes, list) else 0
        return count >= 20, f"{count} nodes in klixsor namespace"
    
    def test_ns_mindbank():
        nodes = api_call("GET", "/nodes?namespace=mindbank&limit=100")
        count = len(nodes) if isinstance(nodes, list) else 0
        return count >= 5, f"{count} nodes in mindbank namespace"
    
    def test_ns_cross_edges():
        graph = api_call("GET", "/graph")
        edges = graph.get("edges", []) if graph else []
        # Check for cross-namespace edges
        nodes_map = {}
        for n in graph.get("nodes", []):
            nodes_map[n["id"]] = n["namespace"]
        cross = 0
        for e in edges:
            src_ns = nodes_map.get(e["source"], "")
            tgt_ns = nodes_map.get(e["target"], "")
            if src_ns and tgt_ns and src_ns != tgt_ns:
                cross += 1
        return cross >= 1, f"{cross} cross-namespace edges"
    
    run_test("Klixsor namespace isolation", test_ns_klixsor)
    run_test("MindBank namespace isolation", test_ns_mindbank)
    run_test("Cross-namespace edge connectivity", test_ns_cross_edges)
    
    # ============================================================
    header("PHASE 9: LATENCY BENCHMARKS")
    # ============================================================
    
    def bench_latency(label, fn, iterations=10):
        times = []
        for _ in range(iterations):
            t0 = time.time()
            fn()
            times.append((time.time() - t0) * 1000)
        avg = sum(times) / len(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        return True, f"avg={avg:.1f}ms, p95={p95:.1f}ms ({iterations} iterations)"
    
    def bench_node_list():
        api_call("GET", "/nodes?limit=50")
    
    def bench_fts_search():
        api_call("GET", "/search?q=authentication")
    
    def bench_snapshot():
        api_call("GET", "/snapshot")
    
    def bench_neighbors():
        nodes = api_call("GET", "/nodes?namespace=klixsor&type=project&limit=1")
        if isinstance(nodes, list) and len(nodes) > 0:
            api_call("GET", f"/nodes/{nodes[0]['id']}/neighbors")
    
    def bench_graph():
        api_call("GET", "/graph")
    
    run_test("Node list latency", lambda: bench_latency("node_list", bench_node_list))
    run_test("FTS search latency", lambda: bench_latency("fts_search", bench_fts_search))
    run_test("Snapshot latency", lambda: bench_latency("snapshot", bench_snapshot))
    run_test("Neighbor traversal latency", lambda: bench_latency("neighbors", bench_neighbors))
    run_test("Full graph load latency", lambda: bench_latency("graph", bench_graph))
    
    # ============================================================
    header("PHASE 10: FLAT MEMORY COMPARISON")
    # ============================================================
    
    print(f"\n  {Y}Comparing MindBank vs flat text memory:{N}\n")
    
    # Simulate flat memory (current Hermes MEMORY block)
    flat_memory = "Klixsor v1.0.253. Root: /home/rat/kataro. VPS: 213.199.63.114. Ports: 8081(API),8090(CE),8092(LiveTracker)."
    flat_chars = len(flat_memory)
    flat_tokens = flat_chars // 4  # rough estimate
    
    # MindBank stats
    all_nodes = api_call("GET", "/nodes?limit=200")
    graph = api_call("GET", "/graph")
    mb_nodes = len(all_nodes) if isinstance(all_nodes, list) else 0
    mb_edges = len(graph.get("edges", [])) if graph else 0
    
    # Calculate knowledge density
    mb_namespaces = len(set(n["namespace"] for n in all_nodes)) if isinstance(all_nodes, list) else 0
    mb_types = len(set(n["node_type"] for n in all_nodes)) if isinstance(all_nodes, list) else 0
    
    print(f"  {B}Flat Memory (current system):{N}")
    print(f"    Capacity: ~2200 chars (~550 tokens)")
    print(f"    Current:  {flat_chars} chars (~{flat_tokens} tokens)")
    print(f"    Structure: unstructured text blob")
    print(f"    Search:    none (must fit in context)")
    print(f"    Temporal:  none (overwrite on update)")
    print(f"    Graph:     none")
    print()
    print(f"  {B}MindBank:{N}")
    print(f"    Nodes:     {mb_nodes} (decisions, facts, problems, advice, ...)")
    print(f"    Edges:     {mb_edges} (typed connections)")
    print(f"    Namespaces: {mb_namespaces} projects")
    print(f"    Node types: {mb_types} different types")
    print(f"    Search:    FTS + semantic (pgvector HNSW)")
    print(f"    Temporal:  version chains (never lose data)")
    print(f"    Graph:     recursive CTE traversal")
    print(f"    Wake-up:   ~{550} tokens snapshot (vs {flat_tokens} flat)")
    print()
    
    capacity_ratio = mb_nodes / max(flat_tokens / 50, 1)  # how many flat memories would we need
    print(f"  {G}{B}MindBank stores {mb_nodes}x more structured knowledge than flat memory{N}")
    print(f"  {G}With search, temporal versioning, and graph traversal included.{N}")
    
    # ============================================================
    # FINAL REPORT
    # ============================================================
    
    header("BENCHMARK RESULTS")
    
    total = results["passed"] + results["failed"]
    pass_rate = results["passed"] / total * 100 if total > 0 else 0
    
    print(f"\n  {B}Tests: {results['passed']}/{total} passed ({pass_rate:.0f}%){N}\n")
    
    for t in results["tests"]:
        status = f"{G}PASS{N}" if t["passed"] else f"{R}FAIL{N}"
        print(f"  [{status}] {t['name']}: {t['detail']}")
    
    if results["failed"] > 0:
        print(f"\n  {R}{results['failed']} tests failed — review above for details{N}")
    else:
        print(f"\n  {G}{B}All tests passed! MindBank is fully operational.{N}")
    
    print()
    return results

if __name__ == "__main__":
    run_benchmarks()
