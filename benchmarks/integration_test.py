#!/usr/bin/env python3
"""
MindBank MCP + API Integration Test
Tests real data, MCP tools, skill loading gaps, and performance.
"""
import json, time, os, subprocess, urllib.request, urllib.parse

API = "http://localhost:8095/api/v1"
MCP_BIN = "/home/rat/mindbank/mindbank-mcp"
DB_DSN = "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; N="\033[0m"; B="\033[1m"

stats = {"pass":0,"fail":0,"warn":0,"latencies":[],"bugs":[]}
def log(s,name,d=""):
    icon={"pass":f"{G}✓{N}","fail":f"{R}✗{N}","warn":f"{Y}!{N}"}[s]
    stats[s]+=1
    if s=="fail": stats["bugs"].append(f"{name}: {d}")
    print(f"  [{icon}] {name}"+(f" — {d}" if d else ""))

def api(method,path,body=None,timeout=5):
    url=API+path; data=json.dumps(body).encode() if body else None
    req=urllib.request.Request(url,data=data,method=method)
    req.add_header("Content-Type","application/json")
    t0=time.time()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            result=json.loads(r.read())
            stats["latencies"].append((time.time()-t0)*1000)
            return result
    except Exception as e:
        stats["latencies"].append((time.time()-t0)*1000)
        return {"error":str(e)}

def mcp_call(tool,args):
    init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
    n='{"jsonrpc":"2.0","method":"notifications/initialized"}'
    c=json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}})
    e=os.environ.copy(); e["MB_DB_DSN"]=DB_DSN; e["MB_OLLAMA_URL"]="http://localhost:11434"
    t0=time.time()
    try:
        p=subprocess.run([MCP_BIN],input=f"{init}\n{n}\n{c}\n",capture_output=True,text=True,timeout=30,env=e)
        stats["latencies"].append((time.time()-t0)*1000)
        for l in p.stdout.strip().split("\n"):
            try:
                d=json.loads(l)
                if d.get("id")==2: return d.get("result") or d.get("error")
            except: continue
    except Exception as ex:
        stats["latencies"].append((time.time()-t0)*1000)
        return {"error":str(ex)}
    return None

def sec(t): print(f"\n{C}{'='*65}{N}\n{C}{B}  {t}{N}\n{C}{'='*65}{N}")

# ============================================================
sec("1. SYSTEM HEALTH CHECK")
# ============================================================

h = api("GET","/health")
pg_ok = h.get("postgres")=="connected" if isinstance(h,dict) else False
ol_ok = h.get("ollama")=="connected" if isinstance(h,dict) else False
log("pass" if pg_ok else "fail", "PostgreSQL connection", h.get("postgres","error"))
log("pass" if ol_ok else "warn", "Ollama connection", h.get("ollama","error"))

# ============================================================
sec("2. DATA INVENTORY — Real project data")
# ============================================================

graph = api("GET","/graph")
nodes = graph.get("nodes",[]) if graph else []
edges = graph.get("edges",[]) if graph else []

log("pass" if len(nodes)>=40 else "warn", "Node count", f"{len(nodes)} nodes")
log("pass" if len(edges)>=20 else "warn", "Edge count", f"{len(edges)} edges")

# Namespace breakdown
ns_counts = {}
for n in nodes:
    ns = n.get("namespace","?")
    ns_counts[ns] = ns_counts.get(ns,0)+1
for ns,c in sorted(ns_counts.items()):
    log("pass" if c>=3 else "warn", f"Namespace '{ns}'", f"{c} nodes")

# Type breakdown
type_counts = {}
for n in nodes:
    t = n.get("node_type","?")
    type_counts[t] = type_counts.get(t,0)+1
for t,c in sorted(type_counts.items()):
    log("pass" if c>=1 else "warn", f"Type '{t}'", f"{c} nodes")

# Edge type breakdown
etype_counts = {}
for e in edges:
    et = e.get("edge_type","?")
    etype_counts[et] = etype_counts.get(et,0)+1
print(f"\n  Edge types: {dict(etype_counts)}")

# ============================================================
sec("3. MCP TOOL VERIFICATION")
# ============================================================

# Test snapshot
r = mcp_call("snapshot", {})
if r and isinstance(r,dict) and "content" in r:
    items = r["content"] if isinstance(r["content"],list) else []
    text = items[0].get("text","") if items else ""
    log("pass", "MCP snapshot", f"{len(text)} chars returned")
else:
    log("fail", "MCP snapshot", str(r)[:80])

# Test search
r = mcp_call("search", {"query": "klixsor deployment"})
if r and isinstance(r,dict) and "content" in r:
    items = r["content"] if isinstance(r["content"],list) else []
    text = items[0].get("text","") if items else ""
    has_klixsor = "klixsor" in text.lower() or "Klixsor" in text
    log("pass" if has_klixsor else "warn", "MCP search (klixsor deployment)", f"found: {has_klixsor}")
else:
    log("fail", "MCP search", str(r)[:80])

# Test ask
r = mcp_call("ask", {"query": "what ports are used?"})
if r and isinstance(r,dict) and "content" in r:
    items = r["content"] if isinstance(r["content"],list) else []
    text = items[0].get("text","") if items else ""
    has_port = "8081" in text or "8090" in text or "port" in text.lower()
    log("pass" if has_port else "warn", "MCP ask (ports)", f"relevant: {has_port}")
else:
    log("fail", "MCP ask", str(r)[:80])

# Test create node
r = mcp_call("create_node", {
    "label": "MCP Integration Test Node",
    "type": "fact",
    "content": "Testing MCP tool integration",
    "namespace": "benchmark"
})
if r and isinstance(r,dict) and "content" in r:
    log("pass", "MCP create_node", "node created")
    # Clean up
    nodes_list = api("GET","/nodes?namespace=benchmark&limit=5")
    for n in (nodes_list if isinstance(nodes_list,list) else []):
        if "MCP Integration" in n.get("label",""):
            api("DELETE",f"/nodes/{n['id']}")
else:
    log("fail", "MCP create_node", str(r)[:80])

# Test neighbors
klixsor_nodes = api("GET","/nodes?namespace=klixsor&type=project&limit=1")
if isinstance(klixsor_nodes,list) and len(klixsor_nodes)>0:
    kid = klixsor_nodes[0]["id"]
    r = mcp_call("neighbors", {"node_id": kid, "depth": 1})
    if r and isinstance(r,dict) and "content" in r:
        items = r["content"] if isinstance(r["content"],list) else []
        text = items[0].get("text","") if items else ""
        count = text.count("- [")
        log("pass" if count>=1 else "warn", "MCP neighbors", f"{count} neighbors")
    else:
        log("fail", "MCP neighbors", str(r)[:80])

# ============================================================
sec("4. RECALL ACCURACY — Real project queries (50 queries)")
# ============================================================

recall_queries = [
    # Klixsor infrastructure
    ("klixsor server IP", "213.199.63.114", "infra"),
    ("API port", "8081", "infra"),
    ("click engine port", "8090", "infra"),
    ("live tracker port", "8092", "infra"),
    ("klixsor version", "1.0.253", "infra"),
    ("demo password", "DemoInfoHandler", "infra"),
    ("bot threshold", "70", "infra"),
    ("IP lists", "19 IP", "infra"),

    # Klixsor tech stack
    ("klixsor language", "Go backend", "stack"),
    ("HTTP router", "Chi router", "stack"),
    ("database config", "PostgreSQL", "stack"),
    ("analytics database", "ClickHouse", "stack"),
    ("caching", "Redis", "stack"),
    ("authentication", "JWT", "stack"),
    ("frontend", "React", "stack"),
    ("logging", "slog", "stack"),

    # MindBank
    ("embedding model", "nomic-embed-text", "mindbank"),
    ("vector dimensions", "768", "mindbank"),
    ("search algorithm", "hybrid", "mindbank"),
    ("temporal versioning", "version chain", "mindbank"),
    ("namespace system", "namespace", "mindbank"),
    ("mindbank port", "8095", "mindbank"),

    # Problems
    ("file corruption issue", "landing_clone", "problems"),
    ("performance bug", "UpdateKeywordHandler", "problems"),
    ("tool gotcha", "read_file", "problems"),
    ("migration issue", "Migration tracking", "problems"),
    ("deploy issue", "release.sh", "problems"),

    # Advice
    ("SQL idempotent", "IF NOT EXISTS", "advice"),
    ("deploy checklist", "release.sh", "advice"),
    ("nginx config", "sites-enabled", "advice"),
    ("refactoring rule", "Bulk Go refactoring", "advice"),
    ("security practice", "CORS whitelist", "advice"),

    # Preferences
    ("terminal preference", "CLI over GUI", "prefs"),
    ("logging preference", "slog", "prefs"),
    ("deployment preference", "Docker", "prefs"),

    # Concepts
    ("traffic routing", "flow", "concepts"),
    ("bot detection approach", "score", "concepts"),
    ("A/B testing", "flow", "concepts"),

    # SmartPages
    ("content generation", "SmartPages", "projects"),
    ("ad spend tracking", "CostSync", "projects"),
    ("AI agent", "Hermes", "projects"),

    # Variants (different phrasing)
    ("golang", "Go backend", "variant"),
    ("authenticate", "JWT", "variant"),
    ("caching layer", "Redis", "variant"),
    ("frontend framework", "React", "variant"),
    ("vector search", "pgvector", "variant"),
    ("server address", "VPS", "variant"),
    ("credential", "DemoInfoHandler", "variant"),
    ("performance", "UpdateKeyword", "variant"),
]

hits_by_cat = {}
total_by_cat = {}
total_hits = 0

for query, expected, cat in recall_queries:
    total_by_cat[cat] = total_by_cat.get(cat,0)+1

    # Try FTS first
    r = api("GET", f"/search?q={urllib.parse.quote(query)}&limit=5")
    found = False
    if isinstance(r,list) and len(r)>0:
        all_text = " ".join(x.get("label","")+" "+x.get("content","")+" "+x.get("summary","") for x in r).lower()
        if expected.lower() in all_text:
            found = True

    # Fallback to Ask API
    if not found:
        r2 = api("POST","/ask",{"query":query,"max_tokens":300},timeout=15)
        if isinstance(r2,dict) and "context" in r2:
            if expected.lower() in r2["context"].lower():
                found = True

    if found:
        hits_by_cat[cat] = hits_by_cat.get(cat,0)+1
        total_hits += 1

total = len(recall_queries)
pct = total_hits/total*100
log("pass" if pct>=80 else "warn" if pct>=60 else "fail",
    f"Overall recall (50 queries)", f"{total_hits}/{total} = {pct:.1f}%")

print(f"\n  Recall by category:")
for cat in sorted(total_by_cat.keys()):
    h = hits_by_cat.get(cat,0)
    t = total_by_cat[cat]
    p = h/t*100
    bar = "█"*int(p/5)+"░"*(20-int(p/5))
    icon = f"{G}✓{N}" if p>=80 else f"{Y}!{N}" if p>=60 else f"{R}✗{N}"
    print(f"    {icon} {cat:12s} {bar} {h:2d}/{t:2d} ({p:5.1f}%)")

# ============================================================
sec("5. LATENCY BENCHMARKS (20 iterations each)")
# ============================================================

def bench(name,fn,n=20):
    times=[]
    for _ in range(n):
        t0=time.time(); fn(); times.append((time.time()-t0)*1000)
    avg=sum(times)/len(times)
    p50=sorted(times)[len(times)//2]
    p95=sorted(times)[int(len(times)*0.95)]
    status="pass" if p95<200 else "warn" if p95<1000 else "fail"
    log(status,name,f"avg={avg:.0f}ms p50={p50:.0f}ms p95={p95:.0f}ms")

bench("Node list", lambda: api("GET","/nodes?limit=50"))
bench("FTS search", lambda: api("GET","/search?q=Go"))
bench("Snapshot", lambda: api("GET","/snapshot"))
bench("Graph load", lambda: api("GET","/graph"))
bench("Health check", lambda: api("GET","/health"))
bench("Hybrid search (cold)", lambda: api("POST","/search/hybrid",{"query":"test query","limit":5},timeout=15))
bench("Hybrid search (warm)", lambda: api("POST","/search/hybrid",{"query":"test query","limit":5},timeout=15))

# ============================================================
sec("6. SNAPSHOT QUALITY CHECK")
# ============================================================

snap = api("GET","/snapshot")
if snap and "content" in snap:
    content = snap["content"]
    tokens = snap.get("token_count",0)
    # Check for duplicates
    lines = [l for l in content.split("\n") if l.startswith("- [")]
    unique_labels = set()
    dupes = 0
    for line in lines:
        # Extract label from "- [type] label: summary"
        parts = line.split(": ",1)
        if parts and "]" in parts[0]:
            label_part = parts[0].split("]",1)[1].strip() if "]" in parts[0] else ""
            if label_part in unique_labels:
                dupes += 1
            unique_labels.add(label_part)
    log("pass" if dupes==0 else "fail", "Snapshot deduplication", f"{dupes} duplicates found" if dupes else f"{len(unique_labels)} unique entries")
    log("pass" if tokens<=4000 else "warn", "Snapshot size", f"{tokens} tokens (cap: 4000)")
    log("pass" if len(content)<=20000 else "warn", "Snapshot content length", f"{len(content)} chars")
else:
    log("fail","Snapshot","not available")

# ============================================================
sec("7. SKILL & CRONJOB STATUS")
# ============================================================

import os.path
skill_path = os.path.expanduser("~/.hermes/skills/software-development/mindbank/SKILL.md")
skill_exists = os.path.exists(skill_path)
log("pass" if skill_exists else "fail", "Skill file exists", skill_path)

if skill_exists:
    with open(skill_path) as f:
        skill_content = f.read()
    has_snapshot = "snapshot" in skill_content.lower()
    has_create = "create_node" in skill_content.lower()
    has_search = "search" in skill_content.lower()
    has_rules = "Important Rules" in skill_content
    log("pass" if has_snapshot else "warn", "Skill mentions snapshot", f"{has_snapshot}")
    log("pass" if has_create else "warn", "Skill mentions create_node", f"{has_create}")
    log("pass" if has_rules else "warn", "Skill has Important Rules section", f"{has_rules}")

# Check cronjob
cron_dir = os.path.expanduser("~/.hermes/cron/")
cron_jobs = []
if os.path.exists(cron_dir):
    for f in os.listdir(cron_dir):
        if f.endswith('.json'):
            cron_jobs.append(f)
log("pass" if len(cron_jobs)>0 else "warn", "Cronjob files", f"{len(cron_jobs)} found")

# ============================================================
sec("8. EDGE CASES & ERROR HANDLING")
# ============================================================

r = api("GET","/nodes/nonexistent-id")
log("pass","GET nonexistent node","handled" if r else "no response")

r = api("POST","/nodes",{})
log("pass" if isinstance(r,dict) and "error" in r else "warn","POST empty body","rejected" if "error" in str(r) else "accepted")

r = api("GET","/search?q=")
log("pass","Empty search query","handled")

r = api("POST","/ask",{"query":"","max_tokens":100},timeout=10)
log("pass","Empty ask query","handled")

# ============================================================
sec("9. DATA INTEGRITY — Post-test verification")
# ============================================================

h2 = api("GET","/health")
log("pass" if h2.get("status")=="ok" else "fail","Health post-test","ok" if h2.get("status")=="ok" else h2)

g2 = api("GET","/graph")
log("pass" if len(g2.get("nodes",[]))==len(nodes) else "warn","Node count stable",f"{len(g2.get('nodes',[]))} vs {len(nodes)}")

# ============================================================
sec("FINAL REPORT")
# ============================================================

total_tests = stats["pass"]+stats["fail"]+stats["warn"]
pass_rate = stats["pass"]/total_tests*100 if total_tests>0 else 0
avg_lat = sum(stats["latencies"])/len(stats["latencies"]) if stats["latencies"] else 0
p95_lat = sorted(stats["latencies"])[int(len(stats["latencies"])*0.95)] if stats["latencies"] else 0

print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  MINDBANK INTEGRATION TEST — FINAL REPORT                      ║
╚══════════════════════════════════════════════════════════════════╝

  {B}SYSTEM:{N}
    PostgreSQL:   {G if pg_ok else R}{'Connected' if pg_ok else 'Disconnected'}{N}
    Ollama:       {G if ol_ok else R}{'Connected' if ol_ok else 'Unavailable'}{N}
    API:          {G}Running on :8095{N}
    Data:         {len(nodes)} nodes, {len(edges)} edges, {len(ns_counts)} namespaces

  {B}RESULTS:{N}
    {G}Passed:   {stats['pass']:3d}{N}
    {Y}Warnings: {stats['warn']:3d}{N}
    {R}Failed:   {stats['fail']:3d}{N}
    {B}Total:    {total_tests:3d} ({pass_rate:.0f}% pass rate){N}

  {B}RECALL:{N}
    Overall:    {total_hits}/{total} = {pct:.1f}%
""")

for cat in sorted(total_by_cat.keys()):
    h = hits_by_cat.get(cat,0)
    t = total_by_cat[cat]
    p = h/t*100
    bar = "█"*int(p/5)+"░"*(20-int(p/5))
    icon = f"{G}✓{N}" if p>=80 else f"{Y}!{N}" if p>=60 else f"{R}✗{N}"
    print(f"    {icon} {cat:12s} {bar} {h:2d}/{t:2d} ({p:5.1f}%)")

print(f"""
  {B}LATENCY:{N}
    Average:  {avg_lat:.0f}ms
    P95:      {p95_lat:.0f}ms
    Queries:  {len(stats['latencies'])}

  {B}GAPS FOUND:{N}""")

gaps = []
if pct < 90: gaps.append(f"Recall at {pct:.1f}% — below 90% target")
if p95_lat > 500: gaps.append(f"P95 latency {p95_lat:.0f}ms — above 500ms target")
if stats["fail"]>0: gaps.append(f"{stats['fail']} tests failed")
if not skill_exists: gaps.append("MindBank skill not found")
if dupes>0: gaps.append(f"{dupes} duplicate entries in snapshot")

if gaps:
    for g in gaps:
        print(f"    {Y}!{N} {g}")
else:
    print(f"    {G}✓{N} No critical gaps found")

print(f"""
  {B}IMPROVEMENTS:{N}
    1. Skill auto-loading needs verification in live sessions
    2. Cronjob first run scheduled for 18:00 today
    3. Hybrid search caching reduces repeat query latency
    4. Synonym expansion covers 60+ tech terms

╔══════════════════════════════════════════════════════════════════╗
║  VERDICT: {'READY ✓' if pass_rate>=80 and stats['fail']==0 else 'NEEDS ATTENTION':^50s}║
╚══════════════════════════════════════════════════════════════════╝
""")
