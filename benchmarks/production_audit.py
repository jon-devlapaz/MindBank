#!/usr/bin/env python3
"""PRAXIS Production Readiness Audit"""
import urllib.request, json, os, time

API = "http://localhost:8095/api/v1"
def api(path, body=None, method="GET", timeout=5):
    url = API + path; data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e: return {"error": str(e)}

gaps = []

# 1. SECURITY
r = api("/nodes?limit=1")
if isinstance(r, list):
    gaps.append("SEC-1: No auth on API — anyone with network access can read/write")

r = api("/nodes", {"label": "x"*10000, "node_type": "fact", "content": "y"*100000, "namespace": "test"}, "POST")
if isinstance(r, dict) and "id" in r:
    gaps.append("SEC-2: No input size validation — DoS via large payloads")
    api(f'/nodes/{r["id"]}', method="DELETE")

r = api("/nodes", {"label": "<script>alert(1)</script>", "node_type": "fact", "content": "<img onerror=alert(1)>", "namespace": "test"}, "POST")
if isinstance(r, dict) and "id" in r:
    gaps.append("SEC-3: API stores raw HTML — dashboard must escape on render")
    api(f'/nodes/{r["id"]}', method="DELETE")

# 2. ERROR HANDLING
r = api("/nodes/nonexistent-id")
if not (isinstance(r, dict) and "error" in r):
    gaps.append("ERR-1: 404 handling may not return proper error format")

# 3. DATA INTEGRITY
g = api("/graph")
nodes = g.get("nodes", []) if isinstance(g, dict) else []
edges = g.get("edges", []) if isinstance(g, dict) else []
node_ids = set(n.get("id", "") for n in nodes)
dangling = [e for e in edges if e.get("source", "") not in node_ids or e.get("target", "") not in node_ids]
if dangling:
    gaps.append(f"DATA-1: {len(dangling)} edges reference non-existent nodes")

# 4. DEPLOYMENT
if not os.path.exists("/etc/systemd/system/mindbank.service"):
    if not os.path.exists(os.path.expanduser("~/.config/systemd/user/mindbank.service")):
        gaps.append("DEPLOY-1: No systemd service — API won't survive reboot")

# 5. MONITORING
gaps.append("MON-1: No Prometheus/metrics endpoint for monitoring")

# 6. PERFORMANCE
t0 = time.time()
api("/snapshot?namespace=klixsor")
first = (time.time() - t0) * 1000
t0 = time.time()
api("/snapshot?namespace=klixsor")
cached = (time.time() - t0) * 1000
if first / max(cached, 0.1) < 2:
    gaps.append("PERF-1: Snapshot cache may not be working effectively")

# Summary
print(json.dumps({"gaps": gaps, "total": len(gaps)}))
