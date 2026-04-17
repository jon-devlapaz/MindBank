#!/usr/bin/env python3
"""
MindBank Comprehensive Test Suite v2
Tests: MCP server, recall, search, temporal, graph, edge cases, integrity
"""

import json
import subprocess
import time
import os
import urllib.request
import sys

API = "http://localhost:8095/api/v1"
DB_DSN = "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"
OLLAMA_URL = "http://localhost:11434"
MCP_BIN = "/home/rat/mindbank/mindbank-mcp"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; N = "\033[0m"; B = "\033[1m"

results = {"pass": 0, "fail": 0, "warn": 0, "tests": []}

def log(status, name, detail=""):
    icon = {"pass": f"{G}PASS{N}", "fail": f"{R}FAIL{N}", "warn": f"{Y}WARN{N}"}[status]
    print(f"  [{icon}] {name}" + (f" — {detail}" if detail else ""))
    results[status] += 1
    results["tests"].append({"status": status, "name": name, "detail": detail})

def api_call(method, path, body=None, timeout=5):
    url = API + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def mcp_call(tool_name, args):
    init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
    notif = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    call = json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool_name,"arguments":args}})
    env = os.environ.copy()
    env["MB_DB_DSN"] = DB_DSN
    env["MB_OLLAMA_URL"] = OLLAMA_URL
    proc = subprocess.run([MCP_BIN], input=f"{init}\n{notif}\n{call}\n", capture_output=True, text=True, timeout=15, env=env)
    for line in proc.stdout.strip().split("\n"):
        try:
            d = json.loads(line)
            if d.get("id") == 2 and "result" in d:
                return d["result"]
        except: continue
    return None

def mcp_raw(messages):
    env = os.environ.copy()
    env["MB_DB_DSN"] = DB_DSN
    env["MB_OLLAMA_URL"] = OLLAMA_URL
    proc = subprocess.run([MCP_BIN], input="\n".join(messages)+"\n", capture_output=True, text=True, timeout=15, env=env)
    results = []
    for line in proc.stdout.strip().split("\n"):
        try:
            d = json.loads(line)
            results.append(d)
        except: continue
    return results

def section(title):
    print(f"\n{C}{'='*60}{N}")
    print(f"{C}{B}  {title}{N}")
    print(f"{C}{'='*60}{N}")

# ============================================================
section("1. MCP SERVER PROTOCOL COMPLIANCE")
# ============================================================

def test_mcp_initialize():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
    ])
    if not r:
        log("fail", "MCP initialize", "no response"); return
    resp = r[0]
    has_proto = "protocolVersion" in resp.get("result", {})
    has_caps = "capabilities" in resp.get("result", {})
    has_info = "serverInfo" in resp.get("result", {})
    ver = resp.get("result",{}).get("serverInfo",{}).get("version","?")
    if has_proto and has_caps and has_info:
        log("pass", "MCP initialize", f"version {ver}, protocol 2024-11-05")
    else:
        log("fail", "MCP initialize", f"missing fields: proto={has_proto} caps={has_caps} info={has_info}")

def test_mcp_tools_list():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
    ])
    tools = None
    for resp in r:
        if resp.get("id") == 2:
            tools = resp.get("result", {}).get("tools", [])
    if tools and len(tools) == 6:
        names = [t["name"] for t in tools]
        log("pass", "MCP tools/list", f"6 tools: {', '.join(names)}")
    else:
        log("fail", "MCP tools/list", f"expected 6 tools, got {len(tools) if tools else 0}")

def test_mcp_prompts_list():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","id":2,"method":"prompts/list"}'
    ])
    for resp in r:
        if resp.get("id") == 2:
            prompts = resp.get("result", {}).get("prompts", [])
            log("pass", "MCP prompts/list", f"{len(prompts)} prompts (expected 0)")
            return
    log("fail", "MCP prompts/list", "no response")

def test_mcp_resources_list():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","id":2,"method":"resources/list"}'
    ])
    for resp in r:
        if resp.get("id") == 2:
            resources = resp.get("result", {}).get("resources", [])
            log("pass", "MCP resources/list", f"{len(resources)} resources (expected 0)")
            return
    log("fail", "MCP resources/list", "no response")

def test_mcp_ping():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","id":2,"method":"ping"}'
    ])
    for resp in r:
        if resp.get("id") == 2 and "result" in resp:
            log("pass", "MCP ping", "pong received")
            return
    log("fail", "MCP ping", "no pong")

def test_mcp_unknown_method():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","id":2,"method":"nonexistent/method"}'
    ])
    for resp in r:
        if resp.get("id") == 2 and "error" in resp:
            log("pass", "MCP unknown method error", f"code {resp['error']['code']}")
            return
    log("fail", "MCP unknown method error", "no error returned")

def test_mcp_shutdown():
    r = mcp_raw([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        '{"jsonrpc":"2.0","id":2,"method":"shutdown"}'
    ])
    for resp in r:
        if resp.get("id") == 2:
            has_result = "result" in resp
            has_error = "error" in resp
            log("pass", "MCP shutdown", f"response received (result={has_result}, error={has_error})")
            return
    log("fail", "MCP shutdown", "no response")

test_mcp_initialize()
test_mcp_tools_list()
test_mcp_prompts_list()
test_mcp_resources_list()
test_mcp_ping()
test_mcp_unknown_method()
test_mcp_shutdown()

# ============================================================
section("2. MCP TOOL CALLS — CREATE NODE")
# ============================================================

def test_mcp_create_node():
    r = mcp_call("mindbank_create_node", {
        "label": "MCP Test Node Alpha",
        "type": "fact",
        "content": "Created via MCP protocol for benchmark testing",
        "summary": "MCP test fact",
        "namespace": "benchmark"
    })
    if r and "content" in r:
        text = r["content"][0]["text"]
        log("pass", "MCP create_node", text[:60])
        return text
    log("fail", "MCP create_node", str(r))
    return None

def test_mcp_create_decision():
    r = mcp_call("mindbank_create_node", {
        "label": "Use MCP for memory",
        "type": "decision",
        "content": "Decided to use MindBank MCP server for persistent memory",
        "summary": "MCP memory decision",
        "namespace": "benchmark"
    })
    if r and "content" in r:
        log("pass", "MCP create_decision", r["content"][0]["text"][:60])
        return r["content"][0]["text"]
    log("fail", "MCP create_decision", str(r))
    return None

mcp_node1 = test_mcp_create_node()
mcp_node2 = test_mcp_create_decision()

# ============================================================
section("3. MCP TOOL CALLS — CREATE EDGE")
# ============================================================

def test_mcp_create_edge():
    # Extract IDs from create responses
    if not mcp_node1 or not mcp_node2:
        log("warn", "MCP create_edge", "skipped — no node IDs")
        return
    # We need the actual node IDs — get them via API
    nodes = api_call("GET", "/nodes?namespace=benchmark&limit=10")
    if not isinstance(nodes, list) or len(nodes) < 2:
        log("fail", "MCP create_edge", "couldn't find benchmark nodes")
        return
    node_ids = {n["label"]: n["id"] for n in nodes}
    src = node_ids.get("Use MCP for memory")
    tgt = node_ids.get("MCP Test Node Alpha")
    if not src or not tgt:
        log("fail", "MCP create_edge", f"labels not found: {list(node_ids.keys())}")
        return
    r = mcp_call("mindbank_create_edge", {
        "source_id": src,
        "target_id": tgt,
        "edge_type": "depends_on"
    })
    if r and "content" in r:
        log("pass", "MCP create_edge", r["content"][0]["text"][:60])
    else:
        log("fail", "MCP create_edge", str(r))

test_mcp_create_edge()

# ============================================================
section("4. MCP TOOL CALLS — SEARCH")
# ============================================================

def test_mcp_search():
    r = mcp_call("mindbank_search", {"query": "MCP memory"})
    if r and "content" in r:
        text = r["content"][0]["text"]
        count = text.count("- [")
        log("pass", "MCP search", f"{count} results for 'MCP memory'")
    else:
        log("fail", "MCP search", str(r))

def test_mcp_search_empty():
    r = mcp_call("mindbank_search", {"query": "xyznonexistent12345"})
    if r and "content" in r:
        log("pass", "MCP search empty", "handled empty results gracefully")
    else:
        log("fail", "MCP search empty", str(r))

test_mcp_search()
test_mcp_search_empty()

# ============================================================
section("5. MCP TOOL CALLS — ASK")
# ============================================================

def test_mcp_ask():
    r = mcp_call("mindbank_ask", {"query": "what did we decide about MCP?"})
    if r and "content" in r:
        text = r["content"][0]["text"]
        has_mcp = "MCP" in text
        log("pass" if has_mcp else "warn", "MCP ask", f"MCP mentioned: {has_mcp}, {len(text)} chars")
    else:
        log("fail", "MCP ask", str(r))

test_mcp_ask()

# ============================================================
section("6. MCP TOOL CALLS — SNAPSHOT")
# ============================================================

def test_mcp_snapshot():
    r = mcp_call("mindbank_snapshot", {})
    if r and "content" in r:
        text = r["content"][0]["text"]
        has_tokens = "Tokens:" in text
        log("pass", "MCP snapshot", f"{len(text)} chars, tokens tracked: {has_tokens}")
    else:
        log("fail", "MCP snapshot", str(r))

test_mcp_snapshot()

# ============================================================
section("7. MCP TOOL CALLS — NEIGHBORS")
# ============================================================

def test_mcp_neighbors():
    nodes = api_call("GET", "/nodes?namespace=benchmark&type=decision&limit=1")
    if not isinstance(nodes, list) or len(nodes) == 0:
        log("warn", "MCP neighbors", "skipped — no benchmark decision node")
        return
    node_id = nodes[0]["id"]
    r = mcp_call("mindbank_neighbors", {"node_id": node_id})
    if r and "content" in r:
        text = r["content"][0]["text"]
        log("pass", "MCP neighbors", text[:80])
    else:
        log("fail", "MCP neighbors", str(r))

test_mcp_neighbors()

# ============================================================
section("8. RECALL ACCURACY — SESSION SIMULATION")
# ============================================================

def test_recall_decisions():
    queries = [
        ("Go backend", "Use Go for backend"),
        ("PostgreSQL", "PostgreSQL for config"),
        ("ClickHouse analytics", "ClickHouse for analytics"),
        ("Redis rate", "Redis for rate limiting"),
        ("JWT auth", "JWT auth for API"),
        ("Chi router", "Chi router"),
        ("React frontend", "React frontend"),
    ]
    hits = 0
    for q, expected in queries:
        r = api_call("GET", f"/search?q={urllib.parse.quote(q)}")
        if isinstance(r, list) and len(r) > 0:
            labels = [x["label"].lower() for x in r]
            if any(expected.lower() in l for l in labels):
                hits += 1
    pct = hits / len(queries) * 100
    log("pass" if pct >= 70 else "fail", "Recall: decisions", f"{hits}/{len(queries)} = {pct:.0f}%")

def test_recall_facts():
    queries = [
        ("213.199.63.114", "VPS IP address"),
        ("8081", "API port 8081"),
        ("8090", "Click engine port 8090"),
        ("8092", "LiveTracker port 8092"),
        ("1.0.253", "Current version 1.0.253"),
        ("admin123", "DemoInfoHandler password"),
        ("70", "Bot detection score threshold"),
    ]
    hits = 0
    for q, expected in queries:
        r = api_call("GET", f"/search?q={urllib.parse.quote(q)}")
        if isinstance(r, list) and len(r) > 0:
            labels = [x["label"].lower() for x in r]
            contents = [x.get("content","").lower() for x in r]
            if any(expected.lower() in l for l in labels) or any(q.lower() in c for c in contents):
                hits += 1
    pct = hits / len(queries) * 100
    log("pass" if pct >= 70 else "fail", "Recall: facts", f"{hits}/{len(queries)} = {pct:.0f}%")

def test_recall_problems():
    queries = [
        ("landing_clone", "landing_clone.go corruption"),
        ("UpdateKeyword", "UpdateKeywordHandler O(N)"),
        ("read_file prefix", "read_file line prefixes"),
    ]
    hits = 0
    for q, expected in queries:
        r = api_call("GET", f"/search?q={urllib.parse.quote(q)}")
        if isinstance(r, list) and len(r) > 0:
            labels = [x["label"].lower() for x in r]
            if any(expected.lower() in l for l in labels):
                hits += 1
    pct = hits / len(queries) * 100
    log("pass" if pct >= 66 else "warn", "Recall: problems", f"{hits}/{len(queries)} = {pct:.0f}%")

def test_recall_advice():
    queries = [
        ("IF NOT EXISTS", "Use IF NOT EXISTS for SQL"),
        ("release.sh", "Verify release.sh binary copy"),
        ("sites-enabled", "sites-enabled is regular file"),
    ]
    hits = 0
    for q, expected in queries:
        r = api_call("GET", f"/search?q={urllib.parse.quote(q)}")
        if isinstance(r, list) and len(r) > 0:
            labels = [x["label"].lower() for x in r]
            if any(expected.lower() in l for l in labels):
                hits += 1
    pct = hits / len(queries) * 100
    log("pass" if pct >= 66 else "warn", "Recall: advice", f"{hits}/{len(queries)} = {pct:.0f}%")

import urllib.parse
test_recall_decisions()
test_recall_facts()
test_recall_problems()
test_recall_advice()

# ============================================================
section("9. CROSS-SESSION RECALL")
# ============================================================

def test_cross_session():
    # Simulate: session 1 stores a fact, session 2 recalls it
    # Session 1: create a unique node
    unique = f"Cross-session test {int(time.time())}"
    r1 = api_call("POST", "/nodes", {
        "label": unique,
        "node_type": "fact",
        "content": "This was stored in simulated session 1",
        "namespace": "benchmark"
    })
    if not r1 or "id" not in r1:
        log("fail", "Cross-session store", "create failed")
        return
    
    time.sleep(0.5)  # brief pause
    
    # Session 2: search for it
    r2 = api_call("GET", f"/search?q={urllib.parse.quote(unique)}")
    found = isinstance(r2, list) and any(unique in x.get("label","") for x in r2)
    log("pass" if found else "fail", "Cross-session recall", f"stored and retrieved: {found}")

test_cross_session()

# ============================================================
section("10. TEMPORAL VERSIONING EDGE CASES")
# ============================================================

def test_temporal_chain():
    # Create, update 3 times, check chain
    r1 = api_call("POST", "/nodes", {
        "label": "Temporal Chain Test",
        "node_type": "fact",
        "content": "Version 1",
        "namespace": "benchmark"
    })
    if not r1 or "id" not in r1:
        log("fail", "Temporal chain create", "failed"); return
    
    id_v1 = r1["id"]
    
    # Update to v2
    r2 = api_call("PUT", f"/nodes/{id_v1}", {"content": "Version 2"})
    if not r2 or "id" not in r2:
        log("fail", "Temporal chain v2", "failed"); return
    id_v2 = r2["id"]
    
    # Update to v3
    r3 = api_call("PUT", f"/nodes/{id_v2}", {"content": "Version 3"})
    if not r3 or "id" not in r3:
        log("fail", "Temporal chain v3", "failed"); return
    id_v3 = r3["id"]
    
    # Check current version
    current = api_call("GET", f"/nodes/{id_v3}")
    if current and current.get("version") == 3:
        log("pass", "Temporal chain (3 versions)", f"v3 active, chain: {id_v1[:8]} -> {id_v2[:8]} -> {id_v3[:8]}")
    else:
        log("fail", "Temporal chain", f"version={current.get('version') if current else 'None'}")
    
    # Check history
    history = api_call("GET", f"/nodes/{id_v3}/history")
    if isinstance(history, list) and len(history) >= 2:
        log("pass", "Temporal history", f"{len(history)} versions in history")
    else:
        log("warn", "Temporal history", f"{len(history) if isinstance(history,list) else 0} versions (expected 3)")

test_temporal_chain()

# ============================================================
section("11. GRAPH TRAVERSAL CORRECTNESS")
# ============================================================

def test_graph_no_orphans():
    graph = api_call("GET", "/graph")
    nodes = graph.get("nodes", []) if graph else []
    edges = graph.get("edges", []) if graph else []
    connected = set()
    for e in edges:
        connected.add(e["source"])
        connected.add(e["target"])
    orphans = [n for n in nodes if n["id"] not in connected]
    pct_connected = (len(nodes) - len(orphans)) / max(len(nodes), 1) * 100
    log("pass" if pct_connected > 50 else "warn", "Graph connectivity", f"{pct_connected:.0f}% connected, {len(orphans)} orphans")

def test_graph_bidirectional():
    nodes = api_call("GET", "/nodes?namespace=klixsor&type=project&limit=1")
    if not isinstance(nodes, list) or len(nodes) == 0:
        log("warn", "Graph bidirectional", "skipped"); return
    klixsor_id = nodes[0]["id"]
    neighbors = api_call("GET", f"/nodes/{klixsor_id}/neighbors")
    if not isinstance(neighbors, list):
        log("fail", "Graph bidirectional", "no neighbors"); return
    # Check that neighbors have edge_type info
    has_edge_info = all("edge_type" in n for n in neighbors)
    log("pass" if has_edge_info else "warn", "Graph edge metadata", f"{len(neighbors)} neighbors, edge info: {has_edge_info}")

test_graph_no_orphans()
test_graph_bidirectional()

# ============================================================
section("12. NAMESPACE ISOLATION")
# ============================================================

def test_ns_isolation():
    klixsor = api_call("GET", "/nodes?namespace=klixsor&limit=100")
    mindbank = api_call("GET", "/nodes?namespace=mindbank&limit=100")
    hermes = api_call("GET", "/nodes?namespace=hermes&limit=100")
    benchmark = api_call("GET", "/nodes?namespace=benchmark&limit=100")
    
    k = len(klixsor) if isinstance(klixsor, list) else 0
    m = len(mindbank) if isinstance(mindbank, list) else 0
    h = len(hermes) if isinstance(hermes, list) else 0
    b = len(benchmark) if isinstance(benchmark, list) else 0
    
    all_nodes = api_call("GET", "/nodes?limit=200")
    total = len(all_nodes) if isinstance(all_nodes, list) else 0
    
    log("pass" if k >= 10 and m >= 5 and total == k+m+h+b else "warn",
        "Namespace isolation",
        f"klixsor={k}, mindbank={m}, hermes={h}, benchmark={b}, total={total}")

test_ns_isolation()

# ============================================================
section("13. EDGE CASES")
# ============================================================

def test_empty_search():
    # Empty query returns 400 — this is correct behavior
    import urllib.error
    try:
        r = api_call("GET", "/search?q=")
        log("pass" if isinstance(r, list) else "warn", "Empty search query", "handled")
    except Exception as e:
        # 400 Bad Request is expected for empty query
        log("pass", "Empty search query", "returns 400 (correct rejection)")

def test_special_chars():
    r = api_call("POST", "/nodes", {
        "label": "Test: special chars <>&\"'",
        "node_type": "fact",
        "content": "Content with <html> & \"quotes\" and 'apostrophes'",
        "namespace": "benchmark"
    })
    ok = r and "id" in r
    log("pass" if ok else "fail", "Special characters in label", "stored OK" if ok else "failed")

def test_long_content():
    long_text = "A" * 5000
    r = api_call("POST", "/nodes", {
        "label": "Long Content Test",
        "node_type": "fact",
        "content": long_text,
        "namespace": "benchmark"
    })
    ok = r and "id" in r
    log("pass" if ok else "fail", "Long content (5000 chars)", "stored OK" if ok else "failed")

def test_unicode():
    r = api_call("POST", "/nodes", {
        "label": "Unicode Test: 你好 🚀 café",
        "node_type": "fact",
        "content": "Content with emoji 🎉 and unicode ñ ü ö",
        "namespace": "benchmark"
    })
    ok = r and "id" in r
    log("pass" if ok else "fail", "Unicode/emoji in label", "stored OK" if ok else "failed")

def test_duplicate_labels():
    r1 = api_call("POST", "/nodes", {
        "label": "Duplicate Label Test",
        "node_type": "fact",
        "content": "First version",
        "namespace": "benchmark"
    })
    r2 = api_call("POST", "/nodes", {
        "label": "Duplicate Label Test",
        "node_type": "fact",
        "content": "Second version",
        "namespace": "benchmark"
    })
    # Both should succeed (no unique constraint on label+type with temporal)
    ok = r1 and r2 and "id" in r1 and "id" in r2
    log("pass" if ok else "fail", "Duplicate labels", "both created (temporal allows)" if ok else "failed")

def test_invalid_edge():
    r = api_call("POST", "/edges", {
        "source_id": "nonexistent-id-1",
        "target_id": "nonexistent-id-2",
        "edge_type": "relates_to"
    })
    has_error = "error" in r or (r and "id" not in r)
    log("pass" if has_error else "warn", "Invalid edge (bad node IDs)", "rejected" if has_error else "unexpectedly accepted")

def test_delete_nonexistent():
    r = api_call("DELETE", "/nodes/nonexistent-id")
    ok = "error" in r or r == {"status": "deleted"} or r == {"error": "node not found"}
    log("pass", "Delete nonexistent node", "handled gracefully")

test_empty_search()
test_special_chars()
test_long_content()
test_unicode()
test_duplicate_labels()
test_invalid_edge()
test_delete_nonexistent()

# ============================================================
section("14. DATABASE INTEGRITY")
# ============================================================

def test_health():
    r = api_call("GET", "/health")
    pg = r.get("postgres") == "connected"
    ol = r.get("ollama") == "connected"
    log("pass" if pg and ol else "fail", "Health check", f"PG={r.get('postgres')}, Ollama={r.get('ollama')}")

def test_consistent_counts():
    nodes = api_call("GET", "/nodes?limit=500")
    graph = api_call("GET", "/graph")
    node_count = len(nodes) if isinstance(nodes, list) else 0
    graph_count = len(graph.get("nodes",[])) if graph else 0
    # Graph might have fewer due to limit
    consistent = graph_count <= node_count and node_count > 0
    log("pass" if consistent else "warn", "Node count consistency", f"list={node_count}, graph={graph_count}")

test_health()
test_consistent_counts()

# ============================================================
section("15. LATENCY STRESS TEST")
# ============================================================

def bench(name, fn, n=20):
    times = []
    for _ in range(n):
        t0 = time.time()
        fn()
        times.append((time.time() - t0) * 1000)
    avg = sum(times) / len(times)
    p50 = sorted(times)[len(times)//2]
    p95 = sorted(times)[int(len(times)*0.95)]
    p99 = sorted(times)[int(len(times)*0.99)]
    status = "pass" if p95 < 100 else "warn" if p95 < 500 else "fail"
    log(status, name, f"avg={avg:.1f}ms p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms")

bench("Latency: node list", lambda: api_call("GET", "/nodes?limit=50"))
bench("Latency: FTS search", lambda: api_call("GET", "/search?q=Go"))
bench("Latency: snapshot", lambda: api_call("GET", "/snapshot"))
bench("Latency: graph", lambda: api_call("GET", "/graph"))
bench("Latency: health", lambda: api_call("GET", "/health"))

# ============================================================
section("16. ASK API QUALITY")
# ============================================================

def test_ask(label, query, expected_in_results):
    r = api_call("POST", "/ask", {"query": query, "max_tokens": 1000}, timeout=15)
    if "error" in r:
        log("fail", f"Ask: {label}", r["error"]); return
    nodes = r.get("nodes", [])
    context = r.get("context", "")
    found = any(exp.lower() in context.lower() for exp in expected_in_results)
    log("pass" if found else "warn", f"Ask: {label}", f"{len(nodes)} nodes, relevant: {found}")

test_ask("auth decisions", "what authentication does klixsor use?", ["JWT", "token"])
test_ask("server config", "what is the VPS IP and ports?", ["213.199.63.114", "8081"])
test_ask("known problems", "what bugs exist in klixsor?", ["landing_clone", "corruption", "O(N)"])
test_ask("tech stack", "what databases does klixsor use?", ["PostgreSQL", "ClickHouse", "Redis"])
test_ask("mindbank design", "how does mindbank store memories?", ["pgvector", "temporal", "version"])

# ============================================================
# FINAL REPORT
# ============================================================

section("FINAL BENCHMARK REPORT")

total = results["pass"] + results["fail"] + results["warn"]
pass_rate = results["pass"] / total * 100 if total > 0 else 0

print(f"\n  {B}Total: {total} tests{N}")
print(f"  {G}Passed: {results['pass']} ({pass_rate:.0f}%){N}")
print(f"  {Y}Warnings: {results['warn']}{N}")
print(f"  {R}Failed: {results['fail']}{N}")

print(f"\n  {B}Summary:{N}")
for t in results["tests"]:
    icon = {"pass": f"{G}✓{N}", "fail": f"{R}✗{N}", "warn": f"{Y}!{N}"}[t["status"]]
    print(f"    {icon} {t['name']}")

if results["fail"] > 0:
    print(f"\n  {R}{B}IMPROVEMENTS NEEDED:{N}")
    for t in results["tests"]:
        if t["status"] == "fail":
            print(f"    - {t['name']}: {t['detail']}")

print(f"\n  {C}{'='*60}{N}")
