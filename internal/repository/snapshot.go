package repository

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type SnapshotRepo struct {
	pool *pgxpool.Pool
	// In-memory cache for namespace-filtered snapshots (TTL: 5 min)
	cacheMu sync.RWMutex
	cache   map[string]snapshotCacheEntry
}

type snapshotCacheEntry struct {
	content string
	tokens  int
	time    time.Time
}

func NewSnapshotRepo(pool *pgxpool.Pool) *SnapshotRepo {
	return &SnapshotRepo{pool: pool, cache: make(map[string]snapshotCacheEntry)}
}

const snapshotCacheTTL = 5 * time.Minute

// Pool returns the underlying connection pool.
func (r *SnapshotRepo) Pool() *pgxpool.Pool {
	return r.pool
}

// Generate builds a snapshot — a pre-computed context blob of the most important nodes.
func (r *SnapshotRepo) Generate(ctx context.Context, workspace, name string, maxTokens int) (string, int, int, error) {
	return r.GenerateFiltered(ctx, workspace, "", name, maxTokens)
}

// GenerateFiltered generates a snapshot optionally filtered by namespace.
func (r *SnapshotRepo) GenerateFiltered(ctx context.Context, workspace, nsFilter, name string, maxTokens int) (string, int, int, error) {
	if maxTokens <= 0 {
		maxTokens = 2000
	}
	// Cap at 4000 tokens to prevent browser/API issues
	if maxTokens > 4000 {
		maxTokens = 4000
	}
	if name == "" {
		name = "default"
	}

	// Get top nodes by importance score
	rows, err := r.pool.Query(ctx, `
		SELECT n.id, n.label, n.node_type::text, n.content, n.summary, n.namespace,
			(
				0.30 * COALESCE(1.0 - EXTRACT(EPOCH FROM (now() - n.last_accessed)) / 2592000.0, 0.5)::real
				+ 0.25 * LEAST(n.access_count::real / 100.0, 1.0)::real
				+ 0.20 * LEAST((SELECT COUNT(*)::real / 20.0 FROM edges WHERE source_id = n.id OR target_id = n.id), 1.0)::real
				+ 0.15 * n.importance
				+ 0.10 * CASE n.node_type
					WHEN 'decision' THEN 1.0
					WHEN 'preference' THEN 0.9
					WHEN 'problem' THEN 0.9
					WHEN 'advice' THEN 0.8
					WHEN 'fact' THEN 0.7
					WHEN 'person' THEN 0.7
					WHEN 'project' THEN 0.7
					WHEN 'event' THEN 0.5
					WHEN 'topic' THEN 0.4
					WHEN 'concept' THEN 0.3
					ELSE 0.5
				END::real
			) AS score
		FROM nodes n
		WHERE n.valid_to IS NULL
		  AND ($1 = '' OR n.workspace_name = $1)
		  AND ($2 = '' OR n.namespace = $2)
		ORDER BY score DESC
		LIMIT 100
	`, workspace, nsFilter)
	if err != nil {
		return "", 0, 0, fmt.Errorf("get top nodes: %w", err)
	}
	defer rows.Close()

	var lines []string
	tokens := 0
	nodeCount := 0
	seen := make(map[string]bool) // deduplicate by label+type

	for rows.Next() {
		var id, label, nodeType, content, summary, namespace string
		var score float32
		if err := rows.Scan(&id, &label, &nodeType, &content, &summary, &namespace, &score); err != nil {
			continue
		}

		// Skip duplicates (same label+type can appear from version chains)
		seenKey := label + "|" + nodeType
		if seen[seenKey] {
			continue
		}
		seen[seenKey] = true

		line := summary
		if line == "" {
			line = truncate(content, 120)
		}
		if line == "" {
			continue
		}

		entry := fmt.Sprintf("- [%s] %s: %s", nodeType, label, line)
		entryTokens := len(entry) / 4

		if tokens+entryTokens > maxTokens {
			break
		}

		lines = append(lines, entry)
		tokens += entryTokens
		nodeCount++
	}

	if len(lines) == 0 {
		return "No memories stored yet.", 0, 0, nil
	}

	content := "## Key Facts & Decisions\n\n" + strings.Join(lines, "\n")

	// Upsert snapshot
	_, err = r.pool.Exec(ctx, `
		INSERT INTO snapshots (workspace_name, name, content, token_count, node_count)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (workspace_name, name) DO UPDATE
		SET content = $3, token_count = $4, node_count = $5, updated_at = now()
	`, workspace, name, content, tokens, nodeCount)
	if err != nil {
		slog.Warn("failed to save snapshot", "error", err)
	}

	return content, tokens, nodeCount, nil
}

// Get retrieves a pre-computed snapshot.
func (r *SnapshotRepo) Get(ctx context.Context, workspace, name string) (string, int, error) {
	return r.GetFiltered(ctx, workspace, "", name)
}

// SetCache stores a namespace-filtered snapshot in the cache.
func (r *SnapshotRepo) SetCache(workspace, nsFilter, name, content string, tokens int) {
	cacheKey := workspace + ":" + name + ":" + nsFilter
	r.cacheMu.Lock()
	r.cache[cacheKey] = snapshotCacheEntry{content: content, tokens: tokens, time: time.Now()}
	r.cacheMu.Unlock()
}

// GetFiltered retrieves a snapshot, filtering by namespace if specified.
// When namespace is provided, always generates fresh (cached snapshots don't account for namespace).
func (r *SnapshotRepo) GetFiltered(ctx context.Context, workspace, nsFilter, name string) (string, int, error) {
	if nsFilter == "" {
		// No namespace filter — use pre-computed snapshot
		if name == "" {
			name = "default"
		}
		var content string
		var tokenCount int
		err := r.pool.QueryRow(ctx, `
			SELECT content, token_count FROM snapshots
			WHERE workspace_name = $1 AND name = $2
		`, workspace, name).Scan(&content, &tokenCount)
		if err != nil {
			return "", 0, err
		}
		return content, tokenCount, nil
	}

	// Namespace-filtered: check cache first
	cacheKey := workspace + ":" + name + ":" + nsFilter
	r.cacheMu.RLock()
	if entry, ok := r.cache[cacheKey]; ok {
		if time.Since(entry.time) < snapshotCacheTTL {
			r.cacheMu.RUnlock()
			return entry.content, entry.tokens, nil
		}
	}
	r.cacheMu.RUnlock()

	// Cache miss or expired — signal caller to regenerate
	return "", 0, fmt.Errorf("namespace filter requires regeneration")
}
