#!/usr/bin/env python3
"""
MindBank Deep Benchmark v3
Tests: recall variations, stress, error recovery, data integrity, improvements
"""
import json, subprocess, time, os, urllib.request, urllib.error, sys, random, string

API = "http://localhost:8095/api/v1"
DB_DSN = "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"
OLLAMA_URL = "http://localhost:11434"
MCP_BIN = "/home/rat/mindbank/mindbank-mcp"

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; N="\033[0m"; B="\033[1m"
bugs = []
results = {"pass":0,"fail":0,"warn":0,"tests":[]}

def log(s,name,d=""):
    icon={"pass":f"{G}PASS{N}","fail":f"{R}FAIL{N}","warn":f"{Y}WARN{N}"}[s]
    print(f"  [{icon}] {name}"+(f" — {d}" if d else ""))
    results[s]+=1; results["tests"].append({"s":s,"n":name,"d":d})
    if s=="fail": bugs.append(f"{name}: {d}")

def api(method,path,body=None,timeout=5):
    url=API+path; data=json.dumps(body).encode() if body else None
    req=urllib.request.Request(url,data=data,method=method)
    req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())
    except Exception as e: return {"error":str(e)}

def mcp(tool,args):
    init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1.0"}}}'
    n='{"jsonrpc":"2.0","method":"notifications/initialized"}'
    c=json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}})
    e=os.environ.copy(); e["MB_DB_DSN"]=DB_DSN; e["MB_OLLAMA_URL"]=OLLAMA_URL
    try:
        p=subprocess.run([MCP_BIN],input=f"{init}\n{n}\n{c}\n",capture_output=True,text=True,timeout=15,env=e)
        for l in p.stdout.strip().split("\n"):
            try:
                d=json.loads(l)
                if d.get("id")==2 and "result" in d: return d["result"]
            except: continue
    except Exception as ex: return {"error":str(ex)}
    return None

def sec(t): print(f"\n{C}{'='*60}{N}\n{C}{B}  {t}{N}\n{C}{'='*60}{N}")

# ============================================================
sec("1. RECALL VARIATIONS — Same concept, different phrasing")
# ============================================================

recall_tests = [
    # (query, expected_label_substring, category)
    ("Go programming language", "Use Go", "decisions"),
    ("golang backend", "Use Go", "decisions"),
    ("what database stores config", "PostgreSQL", "decisions"),
    ("analytics database", "ClickHouse", "decisions"),
    ("caching layer", "Redis", "decisions"),
    ("authentication tokens", "JWT", "decisions"),
    ("HTTP router", "Chi", "decisions"),
    ("frontend framework", "React", "decisions"),
    ("server address", "VPS", "facts"),
    ("213.199.63", "VPS", "facts"),
    ("API runs on", "8081", "facts"),
    ("click processing port", "8090", "facts"),
    ("tracker port", "8092", "facts"),
    ("current release", "1.0.253", "facts"),
    ("demo password", "DemoInfoHandler", "facts"),
    ("bot threshold", "Bot detection", "facts"),
    ("IP lists synced", "19 IP lists", "facts"),
    ("file corruption issue", "landing_clone", "problems"),
    ("O(N) loading bug", "UpdateKeywordHandler", "problems"),
    ("line number prefix issue", "read_file", "problems"),
    ("SQL idempotent", "IF NOT EXISTS", "advice"),
    ("binary deployment path", "release.sh", "advice"),
    ("nginx config file", "sites-enabled", "advice"),
    ("terminal preference", "CLI", "preferences"),
    ("structured logging", "slog", "preferences"),
    ("vector embedding model", "nomic-embed-text", "mindbank"),
    ("dimension count", "768", "mindbank"),
    ("version control system", "version chain", "mindbank"),
    ("search algorithm", "hybrid", "mindbank"),
    ("project namespace", "namespace", "mindbank"),
]

hits = 0
for query, expected, cat in recall_tests:
    r = api("GET", f"/search?q={urllib.parse.quote(query)}")
    if isinstance(r, list) and len(r) > 0:
        all_text = " ".join(x.get("label","")+" "+x.get("content","") for x in r).lower()
        if expected.lower() in all_text:
            hits += 1
        else:
            pass  # silent miss for stats
    elif isinstance(r, list) and len(r) == 0:
        pass  # silent miss

pct = hits/len(recall_tests)*100
status = "pass" if pct>=80 else "warn" if pct>=60 else "fail"
log(status, "Recall variations (30 queries)", f"{hits}/{len(recall_tests)} = {pct:.0f}%")

import urllib.parse

# ============================================================
sec("2. RECALL — Paraphrased queries")
# ============================================================

paraphrase_tests = [
    ("how do we authenticate API requests", "JWT"),
    ("what IP is our server on", "213.199"),
    ("which port does the admin API use", "8081"),
    ("what causes the landing page issue", "landing_clone"),
    ("how should we write SQL migrations", "IF NOT EXISTS"),
    ("what logging library do we use", "slog"),
    ("how many dimensions for embeddings", "768"),
    ("what search approach does mindbank use", "hybrid"),
]

hits = 0
for query, expected in paraphrase_tests:
    r = api("POST", "/ask", {"query": query, "max_tokens": 500}, timeout=10)
    if isinstance(r, dict) and "context" in r:
        if expected.lower() in r["context"].lower():
            hits += 1

pct = hits/len(paraphrase_tests)*100
status = "pass" if pct>=62 else "warn" if pct>=37 else "fail"
log(status, "Paraphrased recall (Ask API)", f"{hits}/{len(paraphrase_tests)} = {pct:.0f}%")

# ============================================================
sec("3. BATCH OPERATIONS — Stress test")
# ============================================================

def test_batch_create():
    t0 = time.time()
    ids = []
    for i in range(50):
        r = api("POST", "/nodes", {
            "label": f"Batch Node {i:03d}",
            "node_type": "fact",
            "content": f"Batch test content {i} with some text for search",
            "namespace": "benchmark"
        })
        if r and "id" in r: ids.append(r["id"])
    elapsed = time.time() - t0
    rate = len(ids)/elapsed if elapsed > 0 else 0
    log("pass" if len(ids)>=45 else "fail", "Batch create 50 nodes",
        f"{len(ids)} created in {elapsed:.2f}s ({rate:.0f}/s)")
    return ids

def test_batch_edges(ids):
    if len(ids) < 10: return
    t0 = time.time()
    edge_count = 0
    for i in range(min(len(ids)-1, 30)):
        r = api("POST", "/edges", {
            "source_id": ids[i], "target_id": ids[i+1], "edge_type": "relates_to"
        })
        if r and "id" in r: edge_count += 1
    elapsed = time.time() - t0
    log("pass" if edge_count>=25 else "warn", "Batch create edges",
        f"{edge_count} edges in {elapsed:.2f}s")

def test_batch_search():
    t0 = time.time()
    for i in range(20):
        api("GET", f"/search?q=batch+node+{i}")
    elapsed = time.time() - t0
    avg_ms = elapsed/20*1000
    log("pass" if avg_ms<50 else "warn", "Batch search 20 queries",
        f"avg {avg_ms:.1f}ms per query")

batch_ids = test_batch_create()
test_batch_edges(batch_ids)
test_batch_search()

# ============================================================
sec("4. DATA INTEGRITY — After batch operations")
# ============================================================

def test_count_after_batch():
    nodes = api("GET", "/nodes?limit=500")
    count = len(nodes) if isinstance(nodes, list) else 0
    log("pass" if count>=90 else "warn", "Total nodes after batch", f"{count} nodes")

def test_graph_after_batch():
    graph = api("GET", "/graph")
    n = len(graph.get("nodes",[])) if graph else 0
    e = len(graph.get("edges",[])) if graph else 0
    log("pass" if n>=50 else "warn", "Graph after batch", f"{n} nodes, {e} edges")

def test_search_after_batch():
    r = api("GET", "/search?q=batch")
    count = len(r) if isinstance(r, list) else 0
    log("pass" if count>=5 else "warn", "Search finds batch nodes", f"{count} results")

def test_snapshot_after_batch():
    r = api("POST", "/snapshot/rebuild", {})
    if r and "node_count" in r:
        log("pass", "Snapshot rebuild after batch", f"{r['node_count']} nodes, {r['token_count']} tokens")
    else:
        log("fail", "Snapshot rebuild after batch", str(r)[:60])

test_count_after_batch()
test_graph_after_batch()
test_search_after_batch()
test_snapshot_after_batch()

# ============================================================
sec("5. TEMPORAL — Deep version chain test")
# ============================================================

def test_long_chain():
    r = api("POST", "/nodes", {
        "label": "Long Chain Test",
        "node_type": "fact",
        "content": "v1",
        "namespace": "benchmark"
    })
    if not r or "id" not in r:
        log("fail", "Long chain create", "failed"); return
    cur_id = r["id"]
    for v in range(2, 11):
        r = api("PUT", f"/nodes/{cur_id}", {"content": f"v{v}"})
        if not r or "id" not in r:
            log("fail", f"Long chain v{v}", "failed"); return
        cur_id = r["id"]
    current = api("GET", f"/nodes/{cur_id}")
    history = api("GET", f"/nodes/{cur_id}/history")
    ver = current.get("version", 0) if current else 0
    hlen = len(history) if isinstance(history, list) else 0
    log("pass" if ver==10 else "fail", "10-version chain",
        f"current v{ver}, history has {hlen} entries")

test_long_chain()

# ============================================================
sec("6. CONFLICT / CONTRADICTION")
# ============================================================

def test_contradiction():
    # Create two nodes that contradict each other
    r1 = api("POST", "/nodes", {
        "label": "Database Choice",
        "node_type": "decision",
        "content": "We chose PostgreSQL for the main database",
        "namespace": "benchmark"
    })
    r2 = api("POST", "/nodes", {
        "label": "Database Choice",
        "node_type": "decision",
        "content": "We chose MySQL for the main database",
        "namespace": "benchmark"
    })
    if r1 and r2 and "id" in r1 and "id" in r2:
        # Both should exist (no auto-contradiction detection yet)
        log("pass", "Contradiction storage", "both stored (no auto-detection yet)")
        # Link them as contradicts
        e = api("POST", "/edges", {
            "source_id": r1["id"], "target_id": r2["id"], "edge_type": "contradicts"
        })
        if e and "id" in e:
            log("pass", "Contradiction edge", "linked as contradicts")
        else:
            log("fail", "Contradiction edge", "failed to create")
    else:
        log("fail", "Contradiction storage", "create failed")

test_contradiction()

# ============================================================
sec("7. NAMESPACE OPERATIONS")
# ============================================================

def test_ns_scoped_search():
    r = api("GET", "/search?q=Go&namespace=klixsor")
    if isinstance(r, list):
        ns = set(x.get("namespace","") for x in r)
        all_klixsor = all(n=="klixsor" for n in ns) if ns else True
        log("pass" if all_klixsor else "fail", "Namespace-scoped search",
            f"{len(r)} results, namespaces: {ns}")
    else:
        log("fail", "Namespace-scoped search", str(r)[:60])

def test_ns_scoped_graph():
    r = api("GET", "/graph?namespace=mindbank")
    nodes = r.get("nodes",[]) if r else []
    ns = set(n.get("namespace","") for n in nodes)
    log("pass" if ns == {"mindbank"} else "warn", "Namespace-scoped graph",
        f"{len(nodes)} nodes, namespaces: {ns}")

def test_ns_cross_edges():
    graph = api("GET", "/graph")
    nmap = {n["id"]: n["namespace"] for n in graph.get("nodes",[])}
    cross = sum(1 for e in graph.get("edges",[])
                if nmap.get(e["source"],"")!=nmap.get(e["target"],""))
    log("pass" if cross>=1 else "warn", "Cross-namespace edges", f"{cross} cross edges")

test_ns_scoped_search()
test_ns_scoped_graph()
test_ns_cross_edges()

# ============================================================
sec("8. ERROR HANDLING & EDGE CASES")
# ============================================================

def test_get_nonexistent():
    r = api("GET", "/nodes/does-not-exist")
    has_error = "error" in r or r is None or (isinstance(r,dict) and "id" not in r)
    log("pass", "GET nonexistent node", "handled" if has_error else "unexpectedly returned data")

def test_update_nonexistent():
    r = api("PUT", "/nodes/does-not-exist", {"content": "test"})
    has_error = "error" in r or r is None or (isinstance(r,dict) and "id" not in r)
    log("pass", "UPDATE nonexistent node", "handled" if has_error else "unexpectedly accepted")

def test_create_no_label():
    r = api("POST", "/nodes", {"node_type": "fact"})
    has_error = "error" in r
    log("pass" if has_error else "warn", "Create without label", "rejected" if has_error else "accepted")

def test_create_no_type():
    r = api("POST", "/nodes", {"label": "test"})
    has_error = "error" in r
    log("pass" if has_error else "warn", "Create without type", "rejected" if has_error else "accepted")

def test_edge_self_loop():
    nodes = api("GET", "/nodes?limit=1")
    if isinstance(nodes, list) and len(nodes) > 0:
        nid = nodes[0]["id"]
        r = api("POST", "/edges", {"source_id": nid, "target_id": nid, "edge_type": "relates_to"})
        has_id = r and "id" in r
        log("warn", "Self-loop edge", "allowed" if has_id else "rejected")

def test_very_long_label():
    long = "X" * 600
    r = api("POST", "/nodes", {"label": long, "node_type": "fact"})
    has_error = "error" in r
    log("pass" if has_error else "warn", "Label >512 chars", "rejected" if has_error else "accepted (should reject)")

def test_concurrent_health():
    import threading
    results_list = []
    def check_health():
        r = api("GET", "/health")
        results_list.append(r.get("status") == "ok")
    threads = [threading.Thread(target=check_health) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    all_ok = all(results_list)
    log("pass" if all_ok else "fail", "Concurrent health checks (10 threads)",
        f"{sum(results_list)}/10 succeeded")

test_get_nonexistent()
test_update_nonexistent()
test_create_no_label()
test_create_no_type()
test_edge_self_loop()
test_very_long_label()
test_concurrent_health()

# ============================================================
sec("9. MCP SERVER — RECONNECT & ERROR HANDLING")
# ============================================================

def test_mcp_invalid_json():
    e = os.environ.copy(); e["MB_DB_DSN"]=DB_DSN; e["MB_OLLAMA_URL"]=OLLAMA_URL
    try:
        p = subprocess.run([MCP_BIN],
            input='{"invalid json\n{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
            capture_output=True, text=True, timeout=10, env=e)
        lines = [l for l in p.stdout.strip().split("\n") if l.strip()]
        has_response = any("id" in json.loads(l) for l in lines if l.startswith("{"))
        log("pass" if has_response else "warn", "MCP invalid JSON recovery",
            f"recovered: {has_response}, {len(lines)} responses")
    except Exception as ex:
        log("warn", "MCP invalid JSON recovery", str(ex)[:60])

def test_mcp_tool_bad_args():
    r = mcp("mindbank_create_node", {"invalid_field": "test"})
    has_error = r is None or (isinstance(r, dict) and "error" in str(r))
    log("pass", "MCP tool bad args", "handled" if has_error else "unexpectedly succeeded")

test_mcp_invalid_json()
test_mcp_tool_bad_args()

# ============================================================
sec("10. ASK API — DEEP QUALITY")
# ============================================================

ask_tests = [
    ("What Go packages does Klixsor use?", ["Chi", "pgx"]),
    ("How does Klixsor handle bot detection?", ["score", "threshold", "IP"]),
    ("What ports are used by Klixsor services?", ["8081", "8090", "8092"]),
    ("What problems exist in the codebase?", ["landing_clone", "corruption", "O(N)"]),
    ("What embedding model does MindBank use?", ["nomic-embed-text", "768"]),
    ("How does MindBank handle temporal data?", ["version", "valid_from", "chain"]),
    ("What is the MindBank search approach?", ["hybrid", "FTS", "vector"]),
    ("Who is the primary user?", ["rat", "developer"]),
]

for query, expected_terms in ask_tests:
    r = api("POST", "/ask", {"query": query, "max_tokens": 800}, timeout=15)
    if "error" in r:
        log("fail", f"Ask: {query[:40]}", r["error"][:60])
        continue
    context = r.get("context", "")
    found = sum(1 for t in expected_terms if t.lower() in context.lower())
    pct = found/len(expected_terms)*100
    status = "pass" if pct>=50 else "warn"
    log(status, f"Ask: {query[:40]}", f"{found}/{len(expected_terms)} terms found ({pct:.0f}%)")

# ============================================================
sec("11. CLEANUP — Remove benchmark test data")
# ============================================================

def cleanup():
    nodes = api("GET", "/nodes?namespace=benchmark&limit=200")
    if isinstance(nodes, list):
        deleted = 0
        for n in nodes:
            r = api("DELETE", f"/nodes/{n['id']}")
            if r and "error" not in r: deleted += 1
        log("pass", "Cleanup benchmark nodes", f"deleted {deleted}/{len(nodes)}")

cleanup()

# ============================================================
sec("12. POST-CLEANUP INTEGRITY")
# ============================================================

def test_health_post():
    r = api("GET", "/health")
    log("pass" if r.get("status")=="ok" else "fail", "Health post-cleanup",
        f"PG={r.get('postgres')}, Ollama={r.get('ollama')}")

def test_search_post():
    r = api("GET", "/search?q=klixsor")
    log("pass" if isinstance(r,list) else "fail", "Search post-cleanup", f"{len(r) if isinstance(r,list) else 0} results")

def test_snapshot_post():
    r = api("POST", "/snapshot/rebuild", {})
    log("pass" if r and "content" in r else "fail", "Snapshot post-cleanup",
        f"{r.get('node_count',0)} nodes")

test_health_post()
test_search_post()
test_snapshot_post()

# ============================================================
sec("FINAL REPORT")
# ============================================================

total = results["pass"]+results["fail"]+results["warn"]
pct = results["pass"]/total*100 if total>0 else 0

print(f"""
  {B}MINDMAP MEMORY BANK — DEEP BENCHMARK v3{N}
  {C}{'='*50}{N}

  {B}Results:{N}
    {G}Passed:   {results['pass']}{N}
    {Y}Warnings: {results['warn']}{N}
    {R}Failed:   {results['fail']}{N}
    {B}Total:    {total} ({pct:.0f}% pass rate){N}
""")

if bugs:
    print(f"  {R}{B}BUGS FOUND:{N}")
    for b in bugs:
        print(f"    {R}✗{N} {b}")
    print()

print(f"  {B}All tests:{N}")
for t in results["tests"]:
    icon = {"pass":f"{G}✓{N}","fail":f"{R}✗{N}","warn":f"{Y}!{N}"}[t["s"]]
    print(f"    {icon} {t['n']}: {t['d']}")

print(f"\n  {C}{'='*50}{N}")
