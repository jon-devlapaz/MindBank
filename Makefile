.PHONY: build run stop db-up db-down db-status logs tidy vet clean

# === MindBank Commands ===

# Build the binary
build:
	go build -o mindbank ./cmd/mindbank

# Start everything (Postgres + API)
run: build db-up
	@echo "Starting MindBank API..."
	@pkill -f "./mindbank" 2>/dev/null || true
	@sleep 1
	@MB_DB_DSN="postgres://mindbank:mindbank_secret@localhost:5434/mindbank?sslmode=disable" \
		MB_OLLAMA_URL="http://localhost:11434" \
		MB_PORT=8095 \
		nohup ./mindbank >> /tmp/mindbank.log 2>&1 &
	@sleep 2
	@curl -s http://localhost:8095/api/v1/health
	@echo ""
	@echo "Dashboard: http://localhost:8095"

# Stop everything
stop:
	@pkill -f "./mindbank" 2>/dev/null && echo "API stopped" || echo "API not running"
	@$(MAKE) db-down

# === Database (Docker) ===

db-up:
	docker compose up -d
	@echo "Waiting for Postgres..."
	@sleep 3
	docker compose ps

db-down:
	docker compose down

db-status:
	docker compose ps

db-logs:
	docker compose logs --tail=50 -f

# === Development ===

tidy:
	go mod tidy

vet:
	go vet ./...

test:
	go test ./... -v

logs:
	tail -f /tmp/mindbank.log

clean:
	rm -f mindbank
	docker compose down -v

# === Quick health check ===

health:
	@curl -s http://localhost:8095/api/v1/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8095/api/v1/health
