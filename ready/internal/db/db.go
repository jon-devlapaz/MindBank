package db

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Connect creates a pgx connection pool.
func Connect(dsn string) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse dsn: %w", err)
	}

	cfg.MaxConns = 50
	cfg.MinConns = 2

	pool, err := pgxpool.NewWithConfig(context.Background(), cfg)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}

	// Verify connection
	if err := pool.Ping(context.Background()); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping: %w", err)
	}

	return pool, nil
}

// Health checks database connectivity.
func Health(ctx context.Context, pool *pgxpool.Pool) error {
	return pool.Ping(ctx)
}

// LogPoolStats logs current pool statistics.
func LogPoolStats(pool *pgxpool.Pool) {
	stat := pool.Stat()
	slog.Debug("db pool stats",
		"total_conns", stat.TotalConns(),
		"idle_conns", stat.IdleConns(),
		"acquired_conns", stat.AcquiredConns(),
		"max_conns", stat.MaxConns(),
	)
}
