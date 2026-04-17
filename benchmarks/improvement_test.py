#!/usr/bin/env python3
"""
MindBank Recall Improvement Test
Tests the SAME queries through 3 search strategies to measure improvement:
1. FTS only (baseline)
2. Hybrid (FTS + vector RRF)
3. FTS + Ask API fallback
"""
import json, urllib.request, urllib.parse, time

API = "http://localhost:8095/api/v1"

def api(method, path, body=None, timeout=5):
    url = API + path; data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except: return {"error": "timeout"}

# All 99 recall queries from the 100-pass benchmark
ALL_QUERIES = [
    # exact (10)
    ("Klixsor TDS", "Klixsor TDS"), ("SmartPages", "SmartPages"), ("CostSync", "CostSync"),
    ("Go backend over Python", "Go backend"), ("Chi router", "Chi router"),
    ("pgx for Postgres", "pgx"), ("ClickHouse for analytics", "ClickHouse"),
    ("Redis for rate limiting", "Redis"), ("JWT with refresh tokens", "JWT"),
    ("React TypeScript Vite", "React"),
    # partial (6)
    ("landing_clone", "landing_clone"), ("UpdateKeyword", "UpdateKeyword"),
    ("read_file prefix", "read_file"), ("release.sh binary", "release.sh"),
    ("IF NOT EXISTS", "IF NOT EXISTS"), ("sites-enabled", "sites-enabled"),
    # numeric (10)
    ("port 8081", "8081"), ("port 8090", "8090"), ("port 8092", "8092"),
    ("port 8095", "8095"), ("port 5434", "5434"), ("version 1.0.253", "1.0.253"),
    ("768 dimensions", "768"), ("threshold 70", "70"), ("19 IP lists", "19 IP"),
    ("213.199.63", "213.199"),
    # concept (14)
    ("authentication tokens", "JWT"), ("analytics database", "ClickHouse"),
    ("caching layer", "Redis"), ("HTTP routing", "Chi"), ("frontend framework", "React"),
    ("server address", "VPS"), ("bot detection system", "Bot detection"),
    ("traffic routing", "flow"), ("structured logging", "slog"),
    ("vector search", "pgvector"), ("embedding model", "nomic-embed"),
    ("version history", "Temporal"), ("namespace isolation", "namespace"),
    ("MCP integration", "MCP"),
    # variant (20)
    ("Go programming", "Go backend"), ("golang", "Go backend"),
    ("caching", "Redis"), ("tokens", "JWT"), ("frontend", "React"),
    ("router", "Chi"), ("analytics", "ClickHouse"), ("logging", "slog"),
    ("vectors", "pgvector"), ("embeddings", "nomic-embed"),
    ("compression", "ClickHouse"), ("sessions", "Redis"),
    ("deployment", "release.sh"), ("corruption", "landing_clone"),
    ("performance", "UpdateKeyword"), ("idempotent", "IF NOT EXISTS"),
    ("nginx", "sites-enabled"), ("credentials", "DemoInfoHandler"),
    ("score", "Bot detection"), ("IP lists", "19 IP"),
    # depth (15)
    ("pgx connection pooling", "pgx"), ("chi middleware", "Chi"),
    ("vite proxy", "React"), ("batched writes", "ClickHouse"),
    ("TTL expiration", "Redis"), ("refresh token rotation", "JWT"),
    ("A/B testing", "flow"), ("columnar compression", "ClickHouse"),
    ("HNSW index", "HNSW"), ("Reciprocal Rank Fusion", "hybrid"),
    ("sharded rate limiter", "rate limit"), ("CORS whitelist", "CORS"),
    ("context timeout", "timeout"), ("audit logging", "audit"),
    ("bot score calculation", "score"),
    # paraphrase (8)
    ("how do we authenticate API", "JWT"), ("what database stores config", "PostgreSQL"),
    ("what analytics database", "ClickHouse"), ("how do we handle caching", "Redis"),
    ("what frontend framework", "React"), ("what is our server IP", "213.199"),
    ("which ports does klixsor use", "8081"), ("how should we write migrations", "IF NOT EXISTS"),
    # edge (10)
    ("Python vs Go", "Go backend"), ("TimescaleDB alternative", "ClickHouse"),
    ("gin alternative", "Chi"), ("session vs JWT", "JWT"),
    ("log.Printf replacement", "slog"), ("ChromaDB alternative", "pgvector"),
    ("OpenAI ada alternative", "nomic-embed"), ("admin password", "DemoInfoHandler"),
    ("login credentials", "DemoInfoHandler"), ("the Go language", "Go backend"),
    # graph (3)
    ("klixsor known problems", "landing_clone"), ("klixsor architecture", "Go backend"),
    ("mindbank design decisions", "pgvector"),
    # namespace (3)
    ("klixsor bot detection", "Bot detection"), ("mindbank vector search", "pgvector"),
    ("klixsor deploy issues", "release.sh"),
]

def check_hit(results, expected):
    if isinstance(results, list) and len(results) > 0:
        all_text = " ".join(x.get("label","")+" "+x.get("content","")+" "+x.get("summary","") for x in results).lower()
        return expected.lower() in all_text
    return False

def test_fts(query, expected):
    r = api("GET", f"/search?q={urllib.parse.quote(query)}&limit=5")
    return check_hit(r, expected)

def test_hybrid(query, expected):
    r = api("POST", "/search/hybrid", {"query": query, "limit": 5}, timeout=10)
    return check_hit(r, expected)

def test_fts_ask(query, expected):
    # FTS first
    r = api("GET", f"/search?q={urllib.parse.quote(query)}&limit=5")
    if check_hit(r, expected):
        return True
    # Fallback to Ask API
    r2 = api("POST", "/ask", {"query": query, "max_tokens": 300}, timeout=10)
    if isinstance(r2, dict) and "context" in r2:
        return expected.lower() in r2["context"].lower()
    return False

# Run all 99 queries through 3 strategies
print("Testing 99 queries × 3 strategies = 297 tests...")
print()

strategies = {
    "FTS only": test_fts,
    "Hybrid (FTS+Vector)": test_hybrid,
    "FTS + Ask fallback": test_fts_ask,
}

results = {name: {"hits": 0, "total": 0, "by_cat": {}} for name in strategies}

for qi, (query, expected) in enumerate(ALL_QUERIES):
    # Determine category from query index
    cat_boundaries = [(0,10,"exact"),(10,16,"partial"),(16,26,"numeric"),(26,40,"concept"),
                      (40,60,"variant"),(60,75,"depth"),(75,83,"paraphrase"),(83,93,"edge"),
                      (93,96,"graph"),(96,99,"namespace")]
    cat = "unknown"
    for start, end, name in cat_boundaries:
        if start <= qi < end:
            cat = name
            break

    for strat_name, strat_fn in strategies.items():
        hit = strat_fn(query, expected)
        results[strat_name]["total"] += 1
        if hit:
            results[strat_name]["hits"] += 1
        if cat not in results[strat_name]["by_cat"]:
            results[strat_name]["by_cat"][cat] = {"hits": 0, "total": 0}
        results[strat_name]["by_cat"][cat]["total"] += 1
        if hit:
            results[strat_name]["by_cat"][cat]["hits"] += 1

# Print results
print(f"\n{'='*70}")
print(f"  RECALL IMPROVEMENT COMPARISON — 99 queries × 3 strategies")
print(f"{'='*70}\n")

for strat_name in strategies:
    r = results[strat_name]
    pct = r["hits"]/r["total"]*100
    print(f"  {strat_name:<25} {r['hits']:3d}/{r['total']:3d} = {pct:5.1f}%")

print(f"\n{'Category':<15}", end="")
for strat_name in strategies:
    print(f"  {strat_name[:20]:>20}", end="")
print()
print("-" * 75)

categories = ["exact","partial","numeric","concept","variant","depth","paraphrase","edge","graph","namespace"]
for cat in categories:
    print(f"  {cat:<13}", end="")
    for strat_name in strategies:
        bc = results[strat_name]["by_cat"].get(cat, {"hits":0,"total":1})
        pct = bc["hits"]/bc["total"]*100 if bc["total"]>0 else 0
        bar = "█"*int(pct/10) + "░"*(10-int(pct/10))
        print(f"  {bc['hits']:2d}/{bc['total']:2d} {pct:4.0f}%", end="")
    print()

print(f"\n{'='*70}")
print(f"  IMPROVEMENT ANALYSIS")
print(f"{'='*70}\n")

# Compare strategies
fts_pct = results["FTS only"]["hits"]/results["FTS only"]["total"]*100
hybrid_pct = results["Hybrid (FTS+Vector)"]["hits"]/results["Hybrid (FTS+Vector)"]["total"]*100
combined_pct = results["FTS + Ask fallback"]["hits"]/results["FTS + Ask fallback"]["total"]*100

print(f"  FTS baseline:           {fts_pct:.1f}%")
print(f"  Hybrid improvement:     +{hybrid_pct-fts_pct:.1f}% (→ {hybrid_pct:.1f}%)")
print(f"  FTS+Ask improvement:    +{combined_pct-fts_pct:.1f}% (→ {combined_pct:.1f}%)")
print()

# Category improvements
print(f"  Biggest improvements by category:")
for cat in categories:
    fts_bc = results["FTS only"]["by_cat"].get(cat, {"hits":0,"total":1})
    hybrid_bc = results["Hybrid (FTS+Vector)"]["by_cat"].get(cat, {"hits":0,"total":1})
    ask_bc = results["FTS + Ask fallback"]["by_cat"].get(cat, {"hits":0,"total":1})
    fts_p = fts_bc["hits"]/fts_bc["total"]*100 if fts_bc["total"]>0 else 0
    hybrid_p = hybrid_bc["hits"]/hybrid_bc["total"]*100 if hybrid_bc["total"]>0 else 0
    ask_p = ask_bc["hits"]/ask_bc["total"]*100 if ask_bc["total"]>0 else 0
    best_p = max(hybrid_p, ask_p)
    improvement = best_p - fts_p
    if improvement > 5:
        best_name = "Hybrid" if hybrid_p >= ask_p else "Ask"
        print(f"    {cat:12s}: {fts_p:5.1f}% → {best_p:5.1f}% (+{improvement:.0f}% via {best_name})")
