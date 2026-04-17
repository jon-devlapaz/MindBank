#!/usr/bin/env python3
"""Rebuild MindBank with comprehensive test data and run recall gap analysis."""
import urllib.request, json, urllib.parse

API = "http://localhost:8095/api/v1"

def api(method, path, body=None, timeout=5):
    url = API + path; data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e: return {"error":str(e)}

# Comprehensive data: 60 items across 4 namespaces
items = [
    # Klixsor infra
    ("Klixsor VPS address","fact","klixsor","Production VPS at 213.199.63.114 Ubuntu 24.04"),
    ("API port 8081","fact","klixsor","Admin REST API port 8081 Chi router JWT auth"),
    ("ClickEngine 8090","fact","klixsor","Click processing engine port 8090 10K clicks/sec"),
    ("LiveTracker 8092","fact","klixsor","Real-time tracker port 8092 WebSocket updates"),
    ("Postgres DSN","fact","klixsor","host=localhost port=5432 user=klixsor dbname=klixsor"),
    ("ClickHouse 9000","fact","klixsor","clickhouse://localhost:9000/klixsor batched inserts"),
    ("Redis 6379","fact","klixsor","Redis localhost:6379 rate limiting session binding"),
    ("Version 1.0.253","fact","klixsor","Klixsor v1.0.253 deployed root /home/rat/kataro"),
    ("Demo credentials","fact","klixsor","DemoInfoHandler login=admin password=admin123"),
    ("Bot threshold 70","fact","klixsor","score_threshold=70 definite bot challenge=40"),
    # Klixsor decisions
    ("Go over Python","decision","klixsor","Go chosen for concurrency and latency over Python"),
    ("Chi router","decision","klixsor","Chi lightweight HTTP router with middleware"),
    ("pgx v5 driver","decision","klixsor","pgx for connection pooling COPY protocol"),
    ("PostgreSQL config","decision","klixsor","Postgres for campaigns flows bot rules"),
    ("ClickHouse analytics","decision","klixsor","ClickHouse columnar compression over TimescaleDB"),
    ("Redis caching","decision","klixsor","Redis for rate limiting with TTL expiration"),
    ("JWT authentication","decision","klixsor","JWT 15min access 7d refresh stateless auth"),
    ("React TypeScript","decision","klixsor","React 18 TypeScript Vite frontend"),
    ("slog logging","decision","klixsor","slog structured JSON logging migrated from printf"),
    ("Score-based bots","decision","klixsor","0-255 score IP lists UA patterns DNS verification"),
    # Klixsor problems
    ("landing_clone corruption","problem","klixsor","stripScripts reconstructed after write_file corruption"),
    ("UpdateKeywordHandler O(N)","problem","klixsor","Loads all keywords to find one O(N) needs index"),
    ("read_file prefixes","problem","klixsor","Line numbers in output never pipe to write_file"),
    ("Migration tracking","problem","klixsor","No tracking table all SQL must be idempotent"),
    ("release.sh path","problem","klixsor","Binaries in releases/latest but systemd runs /opt/klixsor"),
    # MindBank
    ("nomic-embed-text","decision","mindbank","768 dims 270MB Ollama localhost:11434 local embeddings"),
    ("Temporal versioning","decision","mindbank","valid_from/valid_to plus version chains never delete"),
    ("Hybrid search RRF","decision","mindbank","FTS plus pgvector with Reciprocal Rank Fusion k=60"),
    ("Namespaces","decision","mindbank","Per-project namespace cross-namespace edges allowed"),
    ("Importance scoring","fact","mindbank","recency 30% frequency 25% connectivity 20% explicit 15%"),
    ("MCP 6 tools","decision","mindbank","create_node search ask snapshot neighbors create_edge"),
    ("Canvas graph","fact","mindbank","2D force-directed glow effects particles no WebGL"),
    ("Docker Compose","fact","mindbank","pgvector/pg16 Docker 5434 API native 8095 Ollama 11434"),
    ("MemoryProvider plugin","decision","mindbank","Auto-inject snapshot prefetch sync turns extract"),
    ("Session mining cron","fact","mindbank","Every 6 hours mines transcripts extracts facts stores"),
    # Autowrkers
    ("Autowrkers manager","project","autowrkers","Multi-session Claude Code Hermes manager FastAPI"),
    ("Hermes chat provider","decision","autowrkers","hermes_chat provider alongside claude_code tmux"),
    ("Resume Ctrl+C","decision","autowrkers","Ctrl+C exit then hermes sessions list to capture ID"),
    ("Git worktree workers","decision","autowrkers","Lead spawns workers in git worktrees isolated branches"),
    ("Provider badges","fact","autowrkers","Purple Claude blue Hermes on session kanban cards"),
    ("Port 8420","fact","autowrkers","Web dashboard port 8420 FastAPI backend"),
    ("Tmux sessions","fact","autowrkers","Each agent in tmux session auto-created windows"),
    # Hermes
    ("Hermes CLI agent","agent","hermes","Nous Research AI agent persistent memory skills MCP"),
    ("MEMORY.md 2200","fact","hermes","Built-in MEMORY.md 2200 chars plus USER.md 1375 chars"),
    ("Skills directory","fact","hermes","~/.hermes/skills/ SKILL.md files context-relevant loading"),
    ("MCP servers config","fact","hermes","config.yaml mcp_servers prefixed mcp_{server}_{tool}"),
    ("Cronjob system","fact","hermes","~/.hermes/cron/ jobs run in separate sessions"),
    ("Config locations","fact","hermes","config.yaml settings .env API keys"),
    ("Default model","fact","hermes","xiaomi/mimo-v2-pro via Nous inference API"),
    ("Session storage","fact","hermes","~/.hermes/sessions/*.json full conversation history"),
    ("Plugin system","fact","hermes","plugins/memory/ MemoryProvider ABC for providers"),
    ("Gateway mode","fact","hermes","Telegram Discord Slack WhatsApp Signal adapters"),
    # Cross-project
    ("Go backend standard","concept","klixsor","Both Klixsor and MindBank use Go for backend"),
    ("Port allocation","concept","klixsor","8081 8090 8092 8095 sequential port assignment"),
    ("Systemd services","concept","klixsor","All Go services in systemd Restart=on-failure"),
    ("Docker for DB","concept","mindbank","Postgres in Docker for both Klixsor and MindBank"),
    ("Release pattern","concept","klixsor","Similar release.sh pattern for both projects"),
]

print(f"Seeding {len(items)} items...")

# Get existing
existing = api("GET", "/nodes?limit=500")
existing_labels = set(n["label"] for n in existing) if isinstance(existing, list) else set()

created = 0
for label, ntype, ns, content in items:
    if label in existing_labels: continue
    r = api("POST", "/nodes", {"label":label,"node_type":ntype,"content":content,"namespace":ns,"summary":content[:80]})
    if r and "id" in r: created += 1

print(f"Created {created} new nodes")

# Create edges
edge_count = 0
for ns in ["klixsor","mindbank","autowrkers","hermes"]:
    proj = api("GET", f"/nodes?namespace={ns}&type=project&limit=1")
    if not isinstance(proj,list) or len(proj)==0:
        proj = api("GET", f"/nodes?namespace={ns}&limit=1")
    if isinstance(proj,list) and len(proj)>0:
        pid = proj[0]["id"]
        ns_nodes = api("GET", f"/nodes?namespace={ns}&limit=200")
        if isinstance(ns_nodes,list):
            for n in ns_nodes:
                if n["id"]!=pid:
                    r = api("POST","/edges",{"source_id":pid,"target_id":n["id"],"edge_type":"contains"})
                    if r and "id" in r: edge_count += 1

print(f"Created {edge_count} edges")

# Verify
g = api("GET","/graph")
print(f"\nFinal: {len(g.get('nodes',[]))} nodes, {len(g.get('edges',[]))} edges")
