package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"mindbank/internal/config"
	"mindbank/internal/db"
	"mindbank/internal/embedder"
	mcpsrv "mindbank/internal/mcp"
)

func main() {
	cfg := config.Load()

	// Log to stderr only (stdout is for MCP protocol)
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelWarn})))

	// Connect to database
	pool, err := db.Connect(cfg.DBDSN)
	if err != nil {
		slog.Error("failed to connect to database", "error", err)
		os.Exit(1)
	}
	defer pool.Close()

	// Run migrations
	if err := db.Migrate(context.Background(), pool); err != nil {
		slog.Error("failed to run migrations", "error", err)
		os.Exit(1)
	}

	// Embedder client
	embClient := embedder.NewClient(cfg.OllamaURL, cfg.EmbedModel)

	// Create MCP server
	server := mcpsrv.NewServer(pool, embClient)

	// Graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	// Run MCP server (blocks until stdin closes or context cancelled)
	server.Run(ctx)
}
