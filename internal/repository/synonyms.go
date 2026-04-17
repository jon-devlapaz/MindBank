package repository

import (
	"strings"
	"sync"
	"time"
	"unicode"

	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

// normalizeUnicode strips accents and normalizes to ASCII for FTS compatibility.
// "café" → "cafe", "résumé" → "resume"
func normalizeUnicode(s string) string {
	// Remove accents (NFD decomposition, strip combining marks)
	t := transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)
	result, _, _ := transform.String(t, s)
	return result
}

// SynonymMap expands search queries with synonyms before FTS.
var synonymMap = map[string][]string{
	// Languages
	"golang":      {"golang", "Go"},
	"go":          {"Go", "golang"},
	"javascript":  {"javascript", "JS", "node"},
	"python":      {"python", "py"},
	"typescript":  {"typescript", "TS"},

	// Databases
	"postgres":    {"postgres", "PostgreSQL", "pg"},
	"postgresql":  {"postgresql", "postgres", "pg"},
	"database":    {"database", "db", "postgres", "PostgreSQL", "sql", "config"},
	"db":          {"db", "database", "postgres", "sql"},
	"clickhouse":  {"clickhouse", "ClickHouse", "analytics"},
	"redis":       {"redis", "Redis", "cache", "caching"},
	"mysql":       {"mysql", "MariaDB"},
	"sqlite":      {"sqlite", "SQLite"},
	"chromadb":    {"chromadb", "Chroma", "vector store"},
	"timescaledb": {"timescaledb", "Timescale"},

	// Frameworks
	"gin":         {"gin", "Go framework"},
	"chi":         {"chi", "Chi router", "HTTP router"},
	"echo":        {"echo", "Go framework"},
	"react":       {"react", "React", "frontend", "UI"},
	"vite":        {"vite", "Vite", "build", "dev server"},
	"express":     {"express", "expressjs", "Node framework"},

	// Auth
	"auth":        {"auth", "JWT", "token", "authentication", "login"},
	"jwt":         {"JWT", "auth", "token", "authentication"},
	"authenticate": {"authenticate", "auth", "JWT", "token", "login"},
	"authentication": {"authentication", "auth", "JWT", "token"},
	"authorization": {"authorization", "auth", "permission", "access"},
	"token":       {"token", "JWT", "auth", "access token"},
	"login":       {"login", "auth", "credentials", "password"},
	"credentials": {"credentials", "login", "password", "auth"},

	// Caching
	"cache":       {"cache", "caching", "Redis"},
	"caching":     {"caching", "cache", "Redis"},
	"caches":      {"caches", "caching", "cache", "Redis"},
	"cached":      {"cached", "caching", "cache", "Redis"},
	"memcached":   {"memcached", "cache"},

	// Logging
	"log":         {"log", "logging", "slog"},
	"logging":     {"logging", "log", "slog", "structured logging"},
	"slog":        {"slog", "structured logging", "log"},
	"printf":      {"printf", "log.Printf", "log"},
	"log.Printf":  {"log.Printf", "printf", "log", "logging"},

	// Search/Vector
	"vector":      {"vector", "pgvector", "embedding", "search"},
	"embedding":   {"embedding", "nomic-embed-text", "vector"},
	"embeddings":  {"embeddings", "embedding", "nomic-embed-text", "vector"},
	"pgvector":    {"pgvector", "vector", "embedding"},
	"openai":      {"openai", "ada", "embedding"},
	"semantic":    {"semantic", "vector", "embedding", "search"},

	// Deployment
	"deploy":      {"deploy", "deployment", "release", "ship", "release.sh"},
	"deployment":  {"deployment", "deploy", "release", "ship"},
	"release":     {"release", "deploy", "version", "release.sh"},
	"releases":    {"releases", "release", "deploy"},
	"server":      {"server", "VPS", "host", "IP"},
	"vps":         {"VPS", "server", "host", "IP"},
	"ip":          {"ip", "address", "server", "VPS"},
	"port":        {"port", "ports", "service", "endpoint"},
	"ports":       {"ports", "port", "service", "endpoint"},
	"nginx":       {"nginx", "nginx", "sites-enabled", "reverse proxy"},

	// Performance
	"performance": {"performance", "speed", "latency", "fast"},
	"slow":        {"slow", "performance", "O(N)", "bottleneck"},
	"latency":     {"latency", "performance", "speed", "ms"},
	"fast":        {"fast", "performance", "speed"},

	// Security
	"security":    {"security", "CORS", "whitelist", "auth"},
	"cors":        {"CORS", "security", "whitelist", "origin"},

	// Alternatives
	"alternative": {"alternative", "replacement", "option", "vs"},
	"replacement": {"replacement", "alternative", "successor"},
	"vs":          {"vs", "versus", "compared", "alternative"},
	"compared":    {"compared", "vs", "versus", "alternative"},

	// Problems
	"bug":         {"bug", "bugs", "issue", "problem", "broken"},
	"bugs":        {"bugs", "bug", "issues", "problems", "broken"},
	"broken":      {"broken", "bug", "issue", "corruption"},
	"corruption":  {"corruption", "broken", "bug", "issue"},
	"issue":       {"issue", "bug", "problem"},
	"issues":      {"issues", "bugs", "problems"},
	"error":       {"error", "bug", "issue", "problem"},
	"problem":     {"problem", "bug", "issue", "broken"},
	"problems":    {"problems", "bugs", "issues"},

	// Migration
	"migration":   {"migration", "SQL", "schema", "migrate"},
	"migrations":  {"migrations", "migration", "SQL"},
	"idempotent":  {"idempotent", "IF NOT EXISTS", "safe"},

	// Frontend
	"frontend":    {"frontend", "React", "UI", "interface"},
	"ui":          {"UI", "frontend", "interface"},
	"proxy":       {"proxy", "vite proxy", "reverse proxy"},

	// Infrastructure
	"docker":      {"docker", "Docker", "container", "compose"},
	"systemd":     {"systemd", "service", "daemon"},
	"cron":        {"cron", "cronjob", "scheduled", "scheduler"},
	"sessions":    {"sessions", "Redis", "session binding", "tmux", "session management"},
	"session":     {"session", "sessions", "tmux", "terminal"},
	"tmux":        {"tmux", "session", "terminal", "multiplexer"},
	"terminal":    {"terminal", "tmux", "CLI", "command line"},
	// Bot detection
	"bot":         {"bot", "bot detection", "crawler", "scraper"},
	"score":       {"score", "threshold", "bot score"},
	"threshold":   {"threshold", "score", "bot detection"},
	"ip list":     {"ip list", "IP lists", "bot IPs"},

	// Misc
	"compression": {"compression", "ClickHouse", "columnar"},
	"routing":     {"routing", "flow", "traffic routing"},
	"middleware":  {"middleware", "chi middleware", "interceptor"},
	"timeout":     {"timeout", "context timeout", "deadline"},
	"architecture": {"architecture", "design", "structure", "pgvector", "hybrid"},
	"algorithm":   {"algorithm", "search", "hybrid", "RRF", "ranking"},
	"search":      {"search", "FTS", "hybrid", "semantic", "vector"},
}

// ExpandQuery expands a search query with synonyms.
// Returns an expanded query string for FTS, and a list of terms for LIKE fallback.
func ExpandQuery(query string) (expanded string, terms []string) {
	// Normalize unicode first (café → cafe)
	query = normalizeUnicode(query)
	lower := strings.ToLower(query)
	words := strings.Fields(lower)
	seen := make(map[string]bool)
	
	// Start with original query
	expanded = query
	terms = append(terms, query)
	
	for _, word := range words {
		// Strip punctuation for matching
		clean := strings.Trim(word, ".,!?;:()[]{}\"'")
		if syns, ok := synonymMap[clean]; ok {
			for _, syn := range syns {
				if !seen[strings.ToLower(syn)] {
					seen[strings.ToLower(syn)] = true
					terms = append(terms, syn)
				}
			}
		}
	}
	
	// Build expanded query for FTS (OR all synonyms)
	if len(terms) > 1 {
		expanded = strings.Join(terms, " OR ")
	}
	
	return expanded, terms
}

// EmbeddingCache caches query embeddings to avoid repeated Ollama calls.
type EmbeddingCache struct {
	mu      sync.RWMutex
	entries map[string]cacheEntry
	maxAge  time.Duration
	maxSize int
}

type cacheEntry struct {
	embedding []float32
	createdAt time.Time
}

// NewEmbeddingCache creates a new embedding cache.
func NewEmbeddingCache() *EmbeddingCache {
	return &EmbeddingCache{
		entries: make(map[string]cacheEntry),
		maxAge:  30 * time.Minute,
		maxSize: 5000,
	}
}

// Get retrieves a cached embedding.
func (c *EmbeddingCache) Get(key string) ([]float32, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	
	entry, ok := c.entries[key]
	if !ok {
		return nil, false
	}
	if time.Since(entry.createdAt) > c.maxAge {
		return nil, false
	}
	return entry.embedding, true
}

// Set stores an embedding in the cache.
func (c *EmbeddingCache) Set(key string, embedding []float32) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	// Evict oldest if at capacity
	if len(c.entries) >= c.maxSize {
		var oldest string
		var oldestTime time.Time
		for k, v := range c.entries {
			if oldestTime.IsZero() || v.createdAt.Before(oldestTime) {
				oldest = k
				oldestTime = v.createdAt
			}
		}
		delete(c.entries, oldest)
	}
	
	c.entries[key] = cacheEntry{
		embedding: embedding,
		createdAt: time.Now(),
	}
}

// Stats returns cache statistics.
func (c *EmbeddingCache) Stats() (size int, maxAge time.Duration) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.entries), c.maxAge
}
