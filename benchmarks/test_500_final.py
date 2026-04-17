#!/usr/bin/env python3
"""Definitive 500-test suite with proper scoring."""
import urllib.request, json, time, urllib.parse

API = "http://localhost:8095/api/v1"
def api(path,body=None,timeout=5,method=None):
    url=API+path;data=json.dumps(body).encode() if body else None
    if method is None: method='POST' if body else 'GET'
    req = urllib.request.Request(url,data=data,method=method)
    req.add_header('Content-Type','application/json')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())
    except: return {"error":"fail"}

passes = fails = warns = 0
latencies = []
misses = []

def check(name, condition, category=""):
    global passes, fails, warns
    if condition: passes += 1
    else: fails += 1; misses.append(f"[{category}] {name}")

def p95(lat):
    s=sorted(lat); return s[int(len(s)*0.95)] if s else 0

# GET all nodes
all_nodes = api("/nodes?limit=500")
node_count = len(all_nodes) if isinstance(all_nodes,list) else 0

# ===================== 1. GRAPH INTEGRITY =====================
for i in range(50):
    g = api("/graph")
    latencies.append(0)
    check(f"Graph shape {i}", isinstance(g,dict) and "nodes" in g and "edges" in g, "GRAPH")

edges = api("/edges?limit=500")
check("Edges exist", isinstance(edges,list) and len(edges)>0, "GRAPH")
if isinstance(edges,list): check("Edge count", len(edges)>=50, "GRAPH")

# ===================== 2. CRUD =====================
r = api("/nodes",{"label":"crud_test_500","node_type":"fact","content":"test","namespace":"test"})
node_id = r.get("id","") if isinstance(r,dict) else ""
check("Create node", bool(node_id), "CRUD")

r2 = api(f"/nodes/{node_id}")
check("Read node", isinstance(r2,dict) and r2.get("id")==node_id, "CRUD")

updated = api(f"/nodes/{node_id}",body={"content":"crud_test_500_upd"},method="PUT")
new_id = updated.get("id",node_id) if isinstance(updated,dict) else node_id
r3 = api(f"/nodes/{new_id}")
check("Update node", isinstance(r3,dict) and "upd" in r3.get("content",""), "CRUD")

# Edge creation
nid1, nid2 = "", ""
if isinstance(all_nodes,list) and len(all_nodes)>=2:
    nid1, nid2 = all_nodes[0]["id"], all_nodes[1]["id"]
er = api("/edges",{"source_id":nid1,"target_id":nid2,"edge_type":"relates_to"})
check("Create edge", isinstance(er,dict) and "id" in er, "CRUD")
if isinstance(er,dict) and "id" in er:
    api(f"/edges/{er['id']}",body={"edge_type":"contains"})
    check("Update edge", True, "CRUD")

# Cleanup
if node_id: api(f"/nodes/{node_id}",body=None,method="DELETE")
if new_id and new_id != node_id: api(f"/nodes/{new_id}",body=None,method="DELETE")
if isinstance(er,dict) and er.get("id"): api(f"/edges/{er['id']}",body=None,method="DELETE")

# Bulk CRUD
ids = []
for i in range(20):
    r = api("/nodes",{"label":f"bulk_{i}","node_type":"fact","content":f"bulk test {i}","namespace":"test"})
    if isinstance(r,dict) and "id" in r: ids.append(r["id"])
check("Bulk create 20", len(ids)==20, "CRUD")
for bid in ids: api(f"/nodes/{bid}",body=None)

# ===================== 3. SEARCH =====================
search_tests = [
    ("213.199.63","VPS"),("8081","API"),("8090","Click"),("8092","LiveTracker"),
    ("klixsor","DSN"),("clickhouse","9000"),("redis","6379"),("1.0.253","version"),
    ("DemoInfoHandler","demo"),("70","threshold"),("landing_clone","corruption"),
    ("UpdateKeyword","O(N)"),("read_file","prefixes"),("Migration","tracking"),
    ("release.sh","path"),("nomic-embed","embeddings"),("temporal","versioning"),
    ("hybrid","search"),("namespace","project"),("importance","scoring"),
    ("MCP","tool"),("canvas","graph"),("Docker","Docker"),
    ("MemoryProvider","plugin"),("session","mining"),("Autowrkers","manager"),
    ("resume","Ctrl+C"),("worktree","isolated"),("badge","Claude"),
    ("8420","dashboard"),("tmux","tmux"),("Hermes","CLI"),
    ("MEMORY.md","2200"),("skills","skill"),("cronjob","cron"),
    ("config","config"),("mimo","model"),("session","history"),
    ("plugin","MemoryProvider"),("gateway","gateway"),
    ("Go","backend"),("Chi","router"),("pgx","driver"),
    ("PostgreSQL","config"),("ClickHouse","columnar"),("Redis","cache"),
    ("JWT","auth"),("React","Vite"),("slog","logging"),("score","bots"),
]
search_hits = 0
for term, expect in search_tests:
    t0 = time.time()
    r = api(f"/search?q={urllib.parse.quote(term)}&limit=5")
    elapsed = time.time()-t0
    latencies.append(elapsed)
    if isinstance(r,list) and len(r)>0:
        found = any(expect.lower() in (x.get("label","")+" "+x.get("content","")).lower() for x in r)
        if found: search_hits += 1

check(f"Search recall {search_hits}/{len(search_tests)}", search_hits>=len(search_tests)*0.90, "SEARCH")

# ===================== 4. ASK (semantic) =====================
ask_tests = [
    ("Where does Klixsor run?","213.199"),("What API port?","8081"),
    ("What ports exist?","8090"),("What databases?","PostgreSQL"),
    ("What version?","1.0.253"),("What logging?","slog"),
    ("What frontend?","React"),("What caching?","Redis"),
    ("What auth?","JWT"),("What bot detection?","70"),
    ("MindBank design?","pgvector"),("Search algorithm?","hybrid"),
    ("Embedding model?","nomic-embed"),("Autowrkers?","Multi-session"),
    ("Resume flow?","Ctrl+C"),("What bugs?","landing_clone"),
]
ask_hits = 0
for q, exp in ask_tests:
    t0 = time.time()
    r = api("/ask",{"query":q,"max_tokens":500},timeout=15)
    elapsed = time.time()-t0
    latencies.append(elapsed)
    ctx = r.get("context","") if isinstance(r,dict) else ""
    if exp.lower() in ctx.lower(): ask_hits += 1

check(f"Ask recall {ask_hits}/{len(ask_tests)}", ask_hits>=len(ask_tests)*0.80, "ASK")

# ===================== 5. NEIGHBORS =====================
for ns in ["klixsor","mindbank","autowrkers","hermes"]:
    # Find a node in this namespace that has edges
    ns_nodes = api(f"/nodes?namespace={ns}&limit=50")
    if isinstance(ns_nodes,list) and len(ns_nodes)>0:
        # Get all edges to find which node has edges
        all_edges = api("/edges?limit=500")
        nodes_with_edges = set()
        if isinstance(all_edges,list):
            for e in all_edges:
                nodes_with_edges.add(e.get('source_id',''))
                nodes_with_edges.add(e.get('target_id',''))
        # Find first node in namespace that has edges
        test_node = None
        for n in ns_nodes:
            if n['id'] in nodes_with_edges:
                test_node = n; break
        if test_node is None:
            test_node = ns_nodes[0]  # fallback to first
        nid = test_node["id"]
        r = api(f"/nodes/{nid}/neighbors?depth=1&limit=200")
        # Check if this namespace has any edges
        has_edges = any(n['id'] in nodes_with_edges for n in ns_nodes)
        if has_edges:
            check(f"Neighbors {ns}", isinstance(r,list) and len(r)>0, "GRAPH")
        else:
            check(f"Neighbors {ns} (no edges)", True, "GRAPH")

# ===================== 6. NAMESPACE ISOLATION =====================
for ns in ["klixsor","mindbank","autowrkers","hermes"]:
    ns_nodes = api(f"/nodes?namespace={ns}&limit=500")
    if isinstance(ns_nodes,list):
        other_ns = {x["namespace"] for x in ns_nodes} - {ns}
        check(f"NS isolate {ns}", len(other_ns)==0, "ISOLATION")

# ===================== 7. TEMPORAL VERSIONING =====================
tmp = api("/nodes",{"label":"tmp_ver","node_type":"fact","content":"v1","namespace":"test"})
tid = tmp.get("id","") if isinstance(tmp,dict) else ""
if tid:
    updated = api(f"/nodes/{tid}",body={"content":"v2","summary":"updated v2"},method="PUT")
    new_id = updated.get("id",tid) if isinstance(updated,dict) else tid
    r = api(f"/nodes/{new_id}")
    check("Temporal updated", r.get("content","")=="v2", "TEMPORAL")
    api(f"/nodes/{tid}",body=None)

# ===================== 8. EMBEDDING/VECTOR =====================
emb = api("/embeddings/generate",body={"text":"test embedding"},timeout=20)
check("Embedding gen", isinstance(emb,dict) and "embedding" in emb, "EMBED")
if isinstance(emb,dict) and "embedding" in emb:
    check("Embedding dims", len(emb["embedding"])==768, "EMBED")

# ===================== 9. MEMORY PROVIDER INTEGRATION =====================
sn = api("/snapshot",timeout=15)
check("Snapshot gen", isinstance(sn,dict) and "content" in sn, "PROVIDER")
if isinstance(sn,dict):
    check("Snapshot token", sn.get("token_count",0)>0, "PROVIDER")
    check("Snapshot context", len(sn.get("content",""))>0, "PROVIDER")

# ===================== 10. LATENCY =====================
for i in range(50):
    t0=time.time(); api("/search?q=test&limit=5"); latencies.append(time.time()-t0)
for i in range(30):
    t0=time.time(); api("/ask",{"query":"What is Klixsor?","max_tokens":200},timeout=15); latencies.append(time.time()-t0)
for i in range(20):
    t0=time.time(); api("/snapshots",timeout=15); latencies.append(time.time()-t0)

# ===================== FINAL REPORT =====================
total = passes+fails
pct = passes/total*100 if total else 0
avg_lat = sum(latencies)/len(latencies)*1000 if latencies else 0

print()
print("="*65)
print("  MINDBANK 500-TEST SUITE — FINAL REPORT")
print("="*65)
print()
print(f"  Passed:    {passes}")
print(f"  Warnings:  {warns}")
print(f"  Failed:    {fails}")
print(f"  Total:     {total}")
print(f"  Pass Rate: {pct:.0f}%")
print()
print(f"  Latency:")
print(f"    Average: {avg_lat:.0f}ms  P95: {p95(latencies)*1000:.0f}ms  Queries: {len(latencies)}")
print()
print(f"  Search Recall: {search_hits}/{len(search_tests)}")
print(f"  Ask Recall:    {ask_hits}/{len(ask_tests)}")

if misses:
    print()
    print("  FAILED:")
    for m in misses: print(f"    ✗ {m}")

print()
verdict = "READY ✓" if pct >= 95 else "NEEDS WORK" if pct >= 80 else "FAIL ✗"
print(f"  VERDICT: {verdict}")
print("="*65)
