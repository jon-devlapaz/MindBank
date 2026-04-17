package config

import (
	"os"
	"strconv"
)

type Config struct {
	Port       int    // MB_PORT (default 8095)
	DBDSN      string // MB_DB_DSN
	OllamaURL  string // MB_OLLAMA_URL (default http://localhost:11434)
	EmbedModel string // MB_EMBED_MODEL (default nomic-embed-text)
	LogLevel   string // MB_LOG_LEVEL (default info)
}

func Load() Config {
	return Config{
		Port:       envInt("MB_PORT", 8095),
		DBDSN:      envStr("MB_DB_DSN", "postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable"),
		OllamaURL:  envStr("MB_OLLAMA_URL", "http://localhost:11434"),
		EmbedModel: envStr("MB_EMBED_MODEL", "nomic-embed-text"),
		LogLevel:   envStr("MB_LOG_LEVEL", "info"),
	}
}

func envStr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return fallback
}
