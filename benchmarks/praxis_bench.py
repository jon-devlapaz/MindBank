#!/usr/bin/env python3
"""PRAXIS-style benchmark analysis for MindBank memory system."""
import urllib.request, json, time, statistics, urllib.parse

API = "http://localhost:8095/api/v1"
def api(path, body=None, method="GET", timeout=10):
    url = API + path; data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e: return {"error": str(e)}

print("=" * 65)
print("  PRAXIS BENCHMARK - MindBank Memory System Analysis")
print("=" * 65)

# 1. RECALL ACCURACY (Pass@1)
print("\n1. RECALL ACCURACY (Pass@1)")
print("-" * 40)
recall_tests = [
    ("213.199.63","VPS"), ("8081","API"), ("8090","Click"),
    ("8092","LiveTracker"), ("clickhouse","9000"), ("redis","6379"),
    ("1.0.253","version"), ("DemoInfoHandler","demo"), ("70","threshold"),
    ("landing_clone","corruption"), ("UpdateKeyword","O(N)"),
    ("Where does the server run?","213.199"), ("What port for API?","8081"),
    ("What stores analytics?","ClickHouse"), ("What caches requests?","Redis"),
    ("What authenticates?","JWT"), ("What frontend framework?","React"),
    ("What logging?","slog"), ("What detects bots?","score"),
    ("MindBank architecture","pgvector"), ("Search algorithm","hybrid"),
    ("Autowrkers project","Multi-session"), ("Resume flow","Ctrl+C"),
]
search_hits=0; ask_hits=0; search_lats=[]; ask_lats=[]
for query, expect in recall_tests:
    t0=time.time()
    r=api(f"/search?q={urllib.parse.quote(query)}&limit=5")
    search_lats.append((time.time()-t0)*1000)
    if isinstance(r,list) and any(expect.lower() in (x.get("label","")+" "+x.get("content","")).lower() for x in r):
        search_hits+=1
    t0=time.time()
    r=api("/ask",{"query":query,"max_tokens":500},"POST",15)
    ask_lats.append((time.time()-t0)*1000)
    if isinstance(r,dict) and expect.lower() in r.get("context","").lower():
        ask_hits+=1
n=len(recall_tests)
print(f"  FTS Search:    {search_hits}/{n} = {search_hits/n*100:.1f}%")
print(f"  Semantic Ask:  {ask_hits}/{n} = {ask_hits/n*100:.1f}%")
print(f"  Combined:      {search_hits+ask_hits}/{n*2} = {(search_hits+ask_hits)/(n*2)*100:.1f}%")

# 2. CONSISTENCY (Pass^k)
print("\n2. CONSISTENCY (Pass^k)")
print("-" * 40)
k_results=[]
for i in range(20):
    r=api("/ask",{"query":"What ports are used?","max_tokens":300},"POST",15)
    ctx=r.get("context","") if isinstance(r,dict) else ""
    k_results.append("8081" in ctx.lower())
print(f"  Pass^20: {sum(k_results)}/20 = {sum(k_results)/20*100:.0f}%")
print(f"  All correct: {all(k_results)}")

# 3. LATENCY
print("\n3. LATENCY DISTRIBUTION")
print("-" * 40)
all_lats=sorted(search_lats+ask_lats)
p50=all_lats[len(all_lats)//2]
p95=all_lats[int(len(all_lats)*0.95)]
print(f"  Avg: {statistics.mean(all_lats):.0f}ms  P50: {p50:.0f}ms  P95: {p95:.0f}ms")

# 4. THROUGHPUT
print("\n4. THROUGHPUT")
print("-" * 40)
ops=0; t_end=time.time()+5
while time.time()<t_end:
    api("/search?q=test&limit=3"); ops+=1
print(f"  Searches/sec: {ops/5:.0f}")
ops2=0; t_end=time.time()+5
while time.time()<t_end:
    api("/ask",{"query":"test","max_tokens":100},"POST",10); ops2+=1
print(f"  Asks/sec:     {ops2/5:.0f}")

# 5. NAMESPACE ISOLATION
print("\n5. NAMESPACE ISOLATION")
print("-" * 40)
leak_count=0
for ns in ["klixsor","mindbank","autowrkers","hermes"]:
    r=api(f"/search?q=port&namespace={ns}&limit=5")
    if isinstance(r,list):
        foreign=[x for x in r if x.get("namespace")!=ns]
        leak_count+=len(foreign)
        if foreign: print(f"  {ns}: {len(foreign)} LEAKS")
print(f"  Leaks: {leak_count} ({'PASS' if leak_count==0 else 'FAIL'})")

# 6. SNAPSHOT QUALITY
print("\n6. SNAPSHOT QUALITY")
print("-" * 40)
for ns in ["klixsor","mindbank","hermes"]:
    r=api(f"/snapshot?namespace={ns}",timeout=10)
    if isinstance(r,dict):
        tokens=r.get("token_count",0)
        lines=[l for l in r.get("content","").split("\n") if l.strip().startswith("- [")]
        print(f"  {ns:12s}: {tokens:5d} tokens, {len(lines):3d} entries")

# 7. GRAPH
print("\n7. GRAPH INTEGRITY")
print("-" * 40)
g=api("/graph")
nodes=g.get("nodes",[]) if isinstance(g,dict) else []
edges=g.get("edges",[]) if isinstance(g,dict) else []
edge_ids=set()
for e in edges: edge_ids.add(e.get("source","")); edge_ids.add(e.get("target",""))
orphans=[n for n in nodes if n.get("id") not in edge_ids]
print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")
print(f"  Orphans: {len(orphans)} ({len(orphans)/max(len(nodes),1)*100:.0f}%)")
print(f"  Avg edges/node: {len(edges)/max(len(nodes),1):.1f}")

# SCORECARD
print("\n" + "=" * 65)
print("  PRAXIS SCORECARD")
print("=" * 65)
scores = {
    "FTS Recall": search_hits/n*100,
    "Semantic Recall": ask_hits/n*100,
    "Consistency": sum(k_results)/20*100,
    "Namespace Isolation": 100 if leak_count==0 else 0,
    "Graph Connectivity": (1-len(orphans)/max(len(nodes),1))*100,
}
for k,v in scores.items():
    bar="*"*int(v/5)+"."*(20-int(v/5))
    print(f"  {k:25s} [{bar}] {v:.0f}%")
print(f"\n  OVERALL: {statistics.mean(scores.values()):.1f}%")
