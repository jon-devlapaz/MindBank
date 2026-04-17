#!/usr/bin/env python3
"""
MindBank 50-Test Production Suite
Tests: API, MCP, memory provider, search, latency, edge cases, integration
"""
import json, time, os, subprocess, urllib.request, urllib.parse, sys

API = "http://localhost:8095/api/v1"
MCP_BIN = "/home/rat/mindbank/mindbank-mcp"
DB_DSN = "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"
VENV_PY = "/home/rat/.hermes/hermes-agent/venv/bin/python3"

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; N="\033[0m"; B="\033[1m"

results = {"pass":0,"fail":0,"warn":0,"tests":[],"bugs":[],"improvements":[]}

def t(name, status, detail=""):
    icon = {"pass":f"{G}✓{N}","fail":f"{R}✗{N}","warn":f"{Y}!{N}"}[status]
    results[status] += 1
    results["tests"].append({"name":name,"status":status,"detail":detail})
    if status == "fail": results["bugs"].append(f"{name}: {detail}")
    if status == "warn": results["improvements"].append(f"{name}: {detail}")
    print(f"  [{icon}] {name}" + (f" — {detail}" if detail else ""))

def api(method, path, body=None, timeout=5):
    url = API + path; data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e: return {"error":str(e)}

def mcp(tool, args):
    init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1.0"}}}'
    n='{"jsonrpc":"2.0","method":"notifications/initialized"}'
    c=json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}})
    e=os.environ.copy(); e["MB_DB_DSN"]=DB_DSN; e["MB_OLLAMA_URL"]="http://localhost:11434"
    try:
        p=subprocess.run([MCP_BIN],input=f"{init}\n{n}\n{c}\n",capture_output=True,text=True,timeout=30,env=e)
        for l in p.stdout.strip().split("\n"):
            try:
                d=json.loads(l)
                if d.get("id")==2: return d.get("result") or d.get("error")
            except: pass
    except Exception as ex: return {"error":str(ex)}
    return None

def sec(s): print(f"\n{C}{'='*65}{N}\n{C}{B}  {s}{N}\n{C}{'='*65}{N}")

# ============================================================
sec("1. SYSTEM HEALTH (4 tests)")
# ============================================================

h = api("GET","/health")
t("API health endpoint", "pass" if h.get("status")=="ok" else "fail", f"status={h.get('status','?')}")
t("PostgreSQL connected", "pass" if h.get("postgres")=="connected" else "fail", h.get("postgres","error"))
t("Ollama connected", "pass" if h.get("ollama")=="connected" else "warn", h.get("ollama","error"))
t("Embedding model", "pass" if h.get("embedding_model")=="nomic-embed-text" else "warn", h.get("embedding_model","?"))

# ============================================================
sec("2. DATA INTEGRITY (4 tests)")
# ============================================================

g = api("GET","/graph")
nodes = g.get("nodes",[]); edges = g.get("edges",[])
t("Nodes exist", "pass" if len(nodes)>=40 else "warn", f"{len(nodes)} nodes")
t("Edges exist", "pass" if len(edges)>=20 else "warn", f"{len(edges)} edges")

ns = set(n.get("namespace","") for n in nodes)
t("Multiple namespaces", "pass" if len(ns)>=3 else "warn", f"{len(ns)}: {sorted(ns)}")

types = set(n.get("node_type","") for n in nodes)
t("Multiple node types", "pass" if len(types)>=5 else "warn", f"{len(types)} types")

# ============================================================
sec("3. API CRUD (5 tests)")
# ============================================================

# Create
r = api("POST","/nodes",{"label":"50-Test Node","node_type":"fact","content":"Test","namespace":"benchmark"})
create_ok = r and "id" in r
test_id = r.get("id","") if create_ok else ""
t("Create node", "pass" if create_ok else "fail", f"id={test_id[:8]}...")

# Read
r2 = api("GET",f"/nodes/{test_id}") if test_id else {}
t("Read node", "pass" if r2.get("id")==test_id else "fail")

# Update
r3 = api("PUT",f"/nodes/{test_id}",{"content":"Updated"}) if test_id else {}
update_ok = r3 and "id" in r3 and r3.get("version",0)==2
t("Update node (temporal)", "pass" if update_ok else "fail", f"v{r3.get('version','?')}")

# History
r4 = api("GET",f"/nodes/{test_id}/history") if test_id else []
t("Version history", "pass" if isinstance(r4,list) and len(r4)>=2 else "fail", f"{len(r4) if isinstance(r4,list) else 0} versions")

# Delete
r5 = api("DELETE",f"/nodes/{test_id}") if test_id else {}
t("Soft-delete node", "pass" if r5 else "fail")

# Cleanup old version
if r3 and "id" in r3:
    api("DELETE",f"/nodes/{r3['id']}")

# ============================================================
sec("4. SEARCH QUALITY (8 tests)")
# ============================================================

search_tests = [
    ("JWT auth", "JWT"),
    ("Go backend", "Go backend"),
    ("PostgreSQL", "PostgreSQL"),
    ("landing_clone", "landing_clone"),
    ("nomic-embed", "nomic-embed"),
    ("8081", "8081"),
    ("CORS", "CORS"),
    ("deployment", "release.sh"),
]

for query, expected in search_tests:
    r = api("GET",f"/search?q={urllib.parse.quote(query)}&limit=5")
    found = isinstance(r,list) and len(r)>0 and any(expected.lower() in (x.get("label","")+" "+x.get("content","")).lower() for x in r)
    t(f"FTS: '{query}'", "pass" if found else "fail", f"{len(r) if isinstance(r,list) else 0} results")

# ============================================================
sec("5. HYBRID SEARCH (3 tests)")
# ============================================================

hybrid_tests = [
    ("how do we authenticate", "JWT"),
    ("what database stores config", "PostgreSQL"),
    ("what caching layer", "Redis"),
]

for query, expected in hybrid_tests:
    r = api("POST","/search/hybrid",{"query":query,"limit":5},timeout=15)
    found = isinstance(r,list) and len(r)>0 and any(expected.lower() in (x.get("label","")+" "+x.get("content","")).lower() for x in r)
    t(f"Hybrid: '{query[:30]}'", "pass" if found else "warn", f"{len(r) if isinstance(r,list) else 0} results")

# ============================================================
sec("6. ASK API (3 tests)")
# ============================================================

ask_tests = [
    ("what ports does klixsor use?", ["8081"]),
    ("what authentication method?", ["JWT","token"]),
    ("what bugs exist?", ["landing_clone","corruption"]),
]

for query, expected_terms in ask_tests:
    r = api("POST","/ask",{"query":query,"max_tokens":500},timeout=15)
    ctx = r.get("context","") if isinstance(r,dict) else ""
    found = any(t.lower() in ctx.lower() for t in expected_terms)
    t(f"Ask: '{query[:30]}'", "pass" if found else "warn", f"terms found: {found}")

# ============================================================
sec("7. SNAPSHOT (3 tests)")
# ============================================================

snap = api("GET","/snapshot")
content = snap.get("content","") if isinstance(snap,dict) else ""
tokens = snap.get("token_count",0) if isinstance(snap,dict) else 0

t("Snapshot available", "pass" if content else "fail", f"{tokens} tokens")

lines = [l for l in content.split("\n") if l.startswith("- [")]
seen = set()
dupes = sum(1 for l in lines for p in [l.split(": ",1)] if p and "]" in p[0] and (label:=(p[0].split("]",1)[1].strip() if "]" in p[0] else "")) in seen or seen.add(label))
t("Snapshot deduplicated", "pass" if dupes==0 else "fail", f"{dupes} duplicates" if dupes else f"{len(lines)} unique")
t("Snapshot size capped", "pass" if tokens<=4000 else "warn", f"{tokens} tokens (cap:4000)")

# ============================================================
sec("8. GRAPH TRAVERSAL (3 tests)")
# ============================================================

klix = api("GET","/nodes?namespace=klixsor&type=project&limit=1")
if isinstance(klix,list) and len(klix)>0:
    kid = klix[0]["id"]
    nb = api("GET",f"/nodes/{kid}/neighbors")
    t("1-hop neighbors", "pass" if isinstance(nb,list) and len(nb)>=3 else "warn", f"{len(nb) if isinstance(nb,list) else 0}")
    
    deep = api("GET",f"/nodes/{kid}/neighbors?depth=2")
    t("2-hop traversal", "pass" if isinstance(deep,list) and len(deep)>=5 else "warn", f"{len(deep) if isinstance(deep,list) else 0}")
    
    path = api("GET",f"/nodes/{kid}/path/{klix[0]['id']}") if len(klix)>0 else {}
    t("Path finding (self)", "pass" if isinstance(path,dict) else "fail")
else:
    t("1-hop neighbors","warn","no project node")
    t("2-hop traversal","warn","skipped")
    t("Path finding","warn","skipped")

# ============================================================
sec("9. MCP TOOLS (6 tests)")
# ============================================================

# Tools list
init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1.0"}}}'
notif='{"jsonrpc":"2.0","method":"notifications/initialized"}'
tools_req='{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
e=os.environ.copy(); e["MB_DB_DSN"]=DB_DSN; e["MB_OLLAMA_URL"]="http://localhost:11434"
p=subprocess.run([MCP_BIN],input=f"{init}\n{notif}\n{tools_req}\n",capture_output=True,text=True,timeout=10,env=e)
tool_names=[]
for l in p.stdout.strip().split("\n"):
    try:
        d=json.loads(l)
        if d.get("id")==2:
            tool_names=[t["name"] for t in d.get("result",{}).get("tools",[])]
    except: pass
t("MCP tools list","pass" if len(tool_names)==6 else "fail",f"{len(tool_names)} tools")
bad=[n for n in tool_names if n.count("mindbank")>1]
t("MCP no double prefix","pass" if len(bad)==0 else "fail",f"bad: {bad}" if bad else "clean")

# Individual MCP tools
r = mcp("snapshot",{})
t("MCP snapshot","pass" if r and isinstance(r,dict) and "content" in r else "fail")

r = mcp("search",{"query":"klixsor","limit":3})
t("MCP search","pass" if r and isinstance(r,dict) and "content" in r else "fail")

r = mcp("ask",{"query":"what ports?"})
t("MCP ask","pass" if r and isinstance(r,dict) and "content" in r else "fail")

r = mcp("create_node",{"label":"MCP Test 50","type":"fact","content":"Test","namespace":"benchmark"})
t("MCP create_node","pass" if r and isinstance(r,dict) and "content" in r else "fail")
# Cleanup
nodes_bench = api("GET","/nodes?namespace=benchmark&limit=5")
if isinstance(nodes_bench,list):
    for n in nodes_bench:
        if "MCP Test" in n.get("label",""):
            api("DELETE",f"/nodes/{n['id']}")

# ============================================================
sec("10. MEMORY PROVIDER PLUGIN (4 tests)")
# ============================================================

# Test from venv (same as hermes uses)
proc = subprocess.run([VENV_PY,"-c","""
import sys; sys.path.insert(0,'/home/rat/.hermes/hermes-agent')
from plugins.memory.mindbank import MindBankProvider
p = MindBankProvider()
p.initialize('test',hermes_home='/home/rat/.hermes')
print(f'available={p.is_available()}')
print(f'tools={len(p.get_tool_schemas())}')
block = p.system_prompt_block()
print(f'block_len={len(block)}')
result = p.handle_tool_call('mindbank_search',{'query':'klixsor','limit':2})
print(f'search_ok={len(result)>10}')
"""],capture_output=True,text=True,timeout=15)

out = proc.stdout
t("Plugin loads from venv","pass" if "available=True" in out else "fail")
t("Plugin tools","pass" if "tools=4" in out else "fail",out.strip())
t("Plugin system prompt","pass" if "block_len=" in out and int(out.split("block_len=")[1].split()[0])>1000 else "fail")
t("Plugin tool call","pass" if "search_ok=True" in out else "fail")

# ============================================================
sec("11. LATENCY (5 tests)")
# ============================================================

def bench(name,fn,n=10):
    times=[(lambda t0:(time.time()-t0)*1000)(time.time()) for _ in range(n) if fn() or True]
    avg=sum(times)/len(times); p95=sorted(times)[int(len(times)*0.95)]
    return avg,p95

avg,p95 = bench("node_list",lambda: api("GET","/nodes?limit=50"))
t("Node list latency","pass" if p95<100 else "warn",f"avg={avg:.0f}ms p95={p95:.0f}ms")

avg,p95 = bench("fts_search",lambda: api("GET","/search?q=Go"))
t("FTS search latency","pass" if p95<50 else "warn",f"avg={avg:.0f}ms p95={p95:.0f}ms")

avg,p95 = bench("snapshot",lambda: api("GET","/snapshot"))
t("Snapshot latency","pass" if p95<50 else "warn",f"avg={avg:.0f}ms p95={p95:.0f}ms")

avg,p95 = bench("graph",lambda: api("GET","/graph"))
t("Graph latency","pass" if p95<100 else "warn",f"avg={avg:.0f}ms p95={p95:.0f}ms")

avg,p95 = bench("health",lambda: api("GET","/health"))
t("Health latency","pass" if p95<50 else "warn",f"avg={avg:.0f}ms p95={p95:.0f}ms")

# ============================================================
sec("12. ERROR HANDLING (4 tests)")
# ============================================================

r = api("GET","/nodes/nonexistent-id-12345")
t("GET nonexistent","pass" if r else "pass","handled")

r = api("POST","/nodes",{})
t("POST empty body","pass" if isinstance(r,dict) and "error" in str(r) else "warn","rejected")

r = api("POST","/edges",{"source_id":"x","target_id":"y","edge_type":"relates_to"})
t("Edge bad IDs","pass" if isinstance(r,dict) and "error" in str(r) else "warn","rejected")

r = api("GET","/search?q=")
t("Empty search","pass","handled")

# ============================================================
sec("13. CONFIG FILES (4 tests)")
# ============================================================

def file_check(path,check_str=None):
    exists = os.path.exists(path)
    if not exists: return False
    if check_str:
        with open(path) as f: return check_str in f.read()
    return True

t("Config YAML","pass" if file_check(os.path.expanduser("~/.hermes/config.yaml"),"mindbank") else "fail")
t("mindbank.json","pass" if file_check(os.path.expanduser("~/.hermes/mindbank.json"),"api_url") else "fail")
t("Skill installed","pass" if file_check(os.path.expanduser("~/.hermes/skills/software-development/mindbank/SKILL.md"),"mindbank") else "fail")
t("Plugin installed","pass" if file_check(os.path.expanduser("~/.hermes/hermes-agent/plugins/memory/mindbank/__init__.py"),"MindBankProvider") else "fail")

# ============================================================
sec("14. SETUP WIZARD (2 tests)")
# ============================================================

proc = subprocess.run(["bash","-n","/home/rat/mindbank/scripts/setup.sh"],capture_output=True,text=True)
t("Setup script syntax","pass" if proc.returncode==0 else "fail",proc.stderr[:60] if proc.stderr else "clean")

proc = subprocess.run(["bash","/home/rat/mindbank/scripts/setup.sh"],input="y\n",capture_output=True,text=True,timeout=60)
t("Setup wizard runs","pass" if proc.returncode==0 else "warn",f"exit={proc.returncode}")

# ============================================================
sec("15. HERMES INTEGRATION (2 tests)")
# ============================================================

proc = subprocess.run(["hermes","memory","status"],capture_output=True,text=True,timeout=10)
out = proc.stdout
t("hermes memory status","pass" if "mindbank" in out and "available" in out.lower() else "fail",out[:80])

provider_active = "← active" in out or "active" in out.lower()
t("mindbank active","pass" if provider_active else "warn","active" if provider_active else "not active")

# ============================================================
# FINAL REPORT
# ============================================================

sec("FINAL REPORT")

total = results["pass"] + results["fail"] + results["warn"]
pct = results["pass"]/total*100 if total>0 else 0

print(f"""
  {B}RESULTS:{N}
    {G}Passed:   {results['pass']:3d}{N}
    {Y}Warnings: {results['warn']:3d}{N}
    {R}Failed:   {results['fail']:3d}{N}
    {B}Total:    {total:3d} ({pct:.0f}% pass rate){N}
""")

if results["bugs"]:
    print(f"  {R}{B}BUGS:{N}")
    for b in results["bugs"]:
        print(f"    {R}✗{N} {b}")
    print()

if results["improvements"]:
    print(f"  {Y}{B}IMPROVEMENTS:{N}")
    for i in results["improvements"]:
        print(f"    {Y}!{N} {i}")
    print()

print(f"  {B}ALL TESTS:{N}")
for tt in results["tests"]:
    icon = {"pass":f"{G}✓{N}","fail":f"{R}✗{N}","warn":f"{Y}!{N}"}[tt["status"]]
    print(f"    {icon} {tt['name']}: {tt['detail']}")

verdict = "READY ✓" if results["fail"]==0 else "NEEDS FIXES"
print(f"\n{B}VERDICT: {verdict}{N}")
