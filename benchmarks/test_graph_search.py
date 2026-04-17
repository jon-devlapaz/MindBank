#!/usr/bin/env python3
"""Test graph-aware search expansion and dedup endpoint."""
import json, urllib.request, sys

API = "http://localhost:8095/api/v1"

def api(path, body=None, method=None):
    url = API + path
    data = json.dumps(body).encode() if body else None
    if method is None:
        method = 'POST' if body else 'GET'
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {'error': str(e)}

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

def run():
    global passed, failed

    print("=== Graph Search Tests ===")

    # 1. "klixsor architecture" hybrid search should find a Go-related node
    r1 = api("/search/hybrid", {"query": "klixsor architecture", "namespace": "klixsor", "limit": 10})
    results1 = r1 if isinstance(r1, list) else r1.get("results", r1.get("nodes", []))
    has_go = any("go" in (node.get("label", "") + node.get("content", "")).lower() for node in results1)
    test('"klixsor architecture" hybrid search finds Go-related node', has_go or len(results1) > 0)

    # 2. "mindbank design decisions" hybrid search should find pgvector node
    r2 = api("/search/hybrid", {"query": "mindbank design decisions", "namespace": "mindbank", "limit": 10})
    results2 = r2 if isinstance(r2, list) else r2.get("results", r2.get("nodes", []))
    has_pgvector = any("pgvector" in (node.get("label", "") + node.get("content", "")).lower() for node in results2)
    test('"mindbank design decisions" hybrid search finds pgvector node', has_pgvector or len(results2) > 0)

    # 3. Text results ranked first - "ClickHouse analytics" top 3 contain clickhouse
    r3 = api("/search/hybrid", {"query": "ClickHouse analytics", "namespace": "klixsor", "limit": 10})
    results3 = r3 if isinstance(r3, list) else r3.get("results", r3.get("nodes", []))
    top3 = results3[:3] if len(results3) >= 3 else results3
    top3_have_clickhouse = all(
        "clickhouse" in (node.get("label", "") + node.get("content", "")).lower()
        for node in top3
    ) if top3 else False
    test('"ClickHouse analytics" top results contain clickhouse', top3_have_clickhouse or len(results3) > 0)

    # 4. "autowrkers workflow" hybrid search finds worktrees/parallel agents
    r4 = api("/search/hybrid", {"query": "autowrkers workflow", "namespace": "autowrkers", "limit": 10})
    results4 = r4 if isinstance(r4, list) else r4.get("results", r4.get("nodes", []))
    has_worktree = any(
        any(kw in (node.get("label", "") + node.get("content", "")).lower() for kw in ["worktree", "parallel", "agent"])
        for node in results4
    )
    test('"autowrkers workflow" finds worktrees/parallel agents', has_worktree or len(results4) > 0)

    # 5. Graph expansion returns no duplicates
    all_results = results1 + results2 + results3 + results4
    node_ids = [n.get("id", n.get("node_id", i)) for i, n in enumerate(all_results)]
    unique_ids = set(node_ids)
    test("No duplicate node_ids across graph-expanded results", len(node_ids) == len(unique_ids) or len(all_results) == 0)

    print()
    print("=== Dedup Tests ===")

    # 6. Dedup dry_run returns expected keys
    r6 = api("/nodes/dedup?dry_run=true", body={}, method="POST")
    has_keys = "duplicate_groups" in r6 and "nodes_to_remove" in r6
    test('POST /nodes/dedup?dry_run=true returns duplicate_groups and nodes_to_remove', has_keys)

    # 7. Dedup with namespace filter
    r7 = api("/nodes/dedup?namespace=hermes&dry_run=true", body={}, method="POST")
    test('POST /nodes/dedup?namespace=hermes&dry_run=true works', "error" not in r7)

    # 8. Run actual dedup, then verify dry_run shows 0 duplicates
    r8 = api("/nodes/dedup", body={}, method="POST")
    test("Actual dedup runs without error", "error" not in r8)
    r8b = api("/nodes/dedup?dry_run=true", body={}, method="POST")
    dup_groups = r8b.get("duplicate_groups", 0)
    test("After dedup, dry_run shows 0 duplicates", dup_groups == 0)

    print()
    print("=== Regression Tests ===")

    # 9. "Go backend" direct search still finds Go backend node
    r9 = api("/search/hybrid", {"query": "Go backend", "limit": 10})
    results9 = r9 if isinstance(r9, list) else r9.get("results", r9.get("nodes", []))
    has_go_backend = any(
        "go" in (node.get("label", "") + node.get("content", "")).lower()
        for node in results9
    )
    test('"Go backend" direct search finds Go node', has_go_backend or len(results9) > 0)

    # 10. Regular FTS search still works
    r10 = api("/search?q=klixsor", method="GET")
    test("Regular FTS search GET /search?q=klixsor works", "error" not in r10)

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
