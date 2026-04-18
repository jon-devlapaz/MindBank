#!/bin/bash
# MindBank Complete Setup — One-command install for new users
# Usage: bash setup.sh
#
# This script sets up everything:
# 1. Checks prerequisites (Docker, Go, curl)
# 2. Creates directory structure
# 3. Generates secure credentials
# 4. Creates Docker Compose config
# 5. Starts PostgreSQL
# 6. Runs migrations
# 7. Builds MindBank
# 8. Starts MindBank API
# 9. Verifies everything works

set -e

MINDBANK_DIR="$(pwd)"
MINDBANK_PORT="${MB_PORT:-8095}"
MINDBANK_PG_PORT="${MB_PG_PORT:-5434}"

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  MindBank — Graph Memory for AI Agents           ║"
echo "║  Complete Setup                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Step 1: Check prerequisites
echo "[1/9] Checking prerequisites..."
MISSING=""
command -v docker &>/dev/null || MISSING="$MISSING docker"
command -v go &>/dev/null || MISSING="$MISSING go"
command -v curl &>/dev/null || MISSING="$MISSING curl"
command -v psql &>/dev/null || echo "  WARNING: psql not found - will use Docker for migrations"

if [ -n "$MISSING" ]; then
    echo "  ERROR: Missing:$MISSING"
    echo ""
    echo "  Install instructions:"
    echo "    Docker: https://docs.docker.com/engine/install/"
    echo "    Go: https://go.dev/doc/install"
    echo "    curl: usually pre-installed"
    exit 1
fi
echo "  ✓ All prerequisites found"

# Step 2: Generate secure password
echo "[2/9] Generating credentials..."
if [ ! -f .env ]; then
    DB_PASS=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | head -c 32)
    API_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | head -c 64)
    echo "  ✓ Generated DB password and API key"
else
    echo "  ✓ Using existing .env"
    source .env
    DB_PASS="${MB_POSTGRES_PASSWORD:-mindbank_secret}"
    API_KEY="${MB_API_KEY:-}"
fi

# Step 3: Create .env file
echo "[3/9] Creating configuration..."
cat > .env << EOF
# MindBank Configuration
MB_PORT=${MINDBANK_PORT}
MB_POSTGRES_PASSWORD=${DB_PASS}
MB_PG_PORT=${MINDBANK_PG_PORT}
MB_DB_DSN=postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable
MB_OLLAMA_URL=http://localhost:11434
MB_EMBED_MODEL=nomic-embed-text
MB_LOG_LEVEL=info
MB_API_KEY=${API_KEY}
EOF
echo "  ✓ Created .env"

# Step 4: Check Ollama
echo "[4/9] Checking Ollama..."
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "  ✓ Ollama is running"
    # Check if model is installed
    if curl -s http://localhost:11434/api/tags | grep -q "nomic-embed-text"; then
        echo "  ✓ nomic-embed-text model found"
    else
        echo "  ⚠ Pulling nomic-embed-text model (this may take a few minutes)..."
        curl -s http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'
        echo "  ✓ Model installed"
    fi
else
    echo "  ⚠ Ollama not running on port 11434"
    echo "    Install: https://ollama.ai"
    echo "    Then run: ollama pull nomic-embed-text"
    echo ""
    echo "    Continuing without Ollama - embeddings will be disabled"
fi

# Step 5: Start PostgreSQL
echo "[5/9] Starting PostgreSQL..."
docker compose up -d postgres
echo "  Waiting for Postgres to be healthy..."
for i in $(seq 1 30); do
    if docker exec mindbank-postgres pg_isready -U mindbank &>/dev/null; then
        echo "  ✓ Postgres ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ERROR: Postgres failed to start"
        exit 1
    fi
    sleep 1
done

# Step 6: Run migrations
echo "[6/9] Running database migrations..."
if command -v psql &> /dev/null; then
    # Use local psql
    export PGPASSWORD="${DB_PASS}"
    for migration in internal/db/migrations/*.sql; do
        if [ -f "$migration" ]; then
            filename=$(basename "$migration")
            echo "  Running: $filename"
            psql -h localhost -p "$MINDBANK_PG_PORT" -U mindbank -d mindbank -f "$migration" -q
        fi
    done
else
    # Use Docker to run migrations
    echo "  Using Docker for migrations..."
    for migration in internal/db/migrations/*.sql; do
        if [ -f "$migration" ]; then
            filename=$(basename "$migration")
            echo "  Running: $filename"
            docker exec -i mindbank-postgres psql -U mindbank -d mindbank < "$migration"
        fi
    done
fi
echo "  ✓ All migrations completed"

# Step 7: Build MindBank
echo "[7/9] Building MindBank..."
go build -o mindbank ./cmd/mindbank
go build -o mindbank-mcp ./cmd/mindbank-mcp
echo "  ✓ Built mindbank and mindbank-mcp"

# Step 8: Start MindBank
echo "[8/9] Starting MindBank API..."
pkill -f "./mindbank" 2>/dev/null || true
sleep 1
MB_DB_DSN="postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable" \
  MB_OLLAMA_URL="http://localhost:11434" \
  MB_PORT="$MINDBANK_PORT" \
  nohup ./mindbank >> /tmp/mindbank.log 2>&1 &
echo "  Waiting for API to start..."
for i in $(seq 1 15); do
    if curl -s http://localhost:$MINDBANK_PORT/api/v1/health &>/dev/null; then
        echo "  ✓ MindBank API is running"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "  ERROR: MindBank API failed to start"
        echo "  Check logs: tail -f /tmp/mindbank.log"
        exit 1
    fi
    sleep 1
done

# Step 9: Verify
echo "[9/9] Verifying installation..."
HEALTH=$(curl -s http://localhost:$MINDBANK_PORT/api/v1/health)
echo "  $HEALTH"

# Step 10: Configure AI Agent
echo ""
echo "[10/10] Configure AI Agent"
echo "Which AI agent would you like to configure?"
echo "  1) Hermes Agent"
echo "  2) Claude Code"
echo "  3) Skip (configure manually later)"
echo ""
read -p "Enter choice [1-3]: " AGENT_CHOICE

case $AGENT_CHOICE in
    1)
        echo "  Configuring Hermes Agent..."
        mkdir -p ~/.hermes
        if [ ! -f ~/.hermes/config.yaml ]; then
            cat > ~/.hermes/config.yaml << EOF
mcpServers:
  mindbank:
    command: $(pwd)/mindbank-mcp
    env:
      MB_DB_DSN: "postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable"
      MB_OLLAMA_URL: "http://localhost:11434"
EOF
            echo "  ✓ Created ~/.hermes/config.yaml"
        else
            echo "  ⚠ ~/.hermes/config.yaml already exists"
            echo "    Add this to your config:"
            echo ""
            echo "  mcpServers:"
            echo "    mindbank:"
            echo "      command: $(pwd)/mindbank-mcp"
            echo "      env:"
            echo "        MB_DB_DSN: \"postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable\""
            echo "        MB_OLLAMA_URL: \"http://localhost:11434\""
        fi
        
        # Install plugin if hermes is available
        if command -v hermes &>/dev/null && [ -f scripts/install-plugin.sh ]; then
            echo ""
            read -p "Install MindBank plugin for Hermes? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                bash scripts/install-plugin.sh
            fi
        fi
        ;;
    2)
        echo "  Configuring Claude Code..."
        mkdir -p ~/.claude
        if [ ! -f ~/.claude/claude_desktop_config.json ]; then
            cat > ~/.claude/claude_desktop_config.json << EOF
{
  "mcpServers": {
    "mindbank": {
      "command": "$(pwd)/mindbank-mcp",
      "env": {
        "MB_DB_DSN": "postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable",
        "MB_OLLAMA_URL": "http://localhost:11434"
      }
    }
  }
}
EOF
            echo "  ✓ Created ~/.claude/claude_desktop_config.json"
        else
            echo "  ⚠ ~/.claude/claude_desktop_config.json already exists"
            echo "    Add this to your config:"
            echo ""
            echo '  "mcpServers": {'
            echo '    "mindbank": {'
            echo "      \"command\": \"$(pwd)/mindbank-mcp\","
            echo '      "env": {'
            echo "        \"MB_DB_DSN\": \"postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable\","
            echo '        "MB_OLLAMA_URL": "http://localhost:11434"'
            echo '      }'
            echo '    }'
            echo '  }'
        fi
        ;;
    3)
        echo "  Skipping agent configuration"
        ;;
    *)
        echo "  Invalid choice, skipping agent configuration"
        ;;
esac

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  ✅  MindBank Setup Complete!                     ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "  Dashboard: http://localhost:$MINDBANK_PORT"
echo "  API: http://localhost:$MINDBANK_PORT/api/v1"
echo "  Graph: http://localhost:$MINDBANK_PORT/graph-view"
echo ""
echo "  Useful commands:"
echo "    make run        - Start MindBank"
echo "    make stop       - Stop MindBank"
echo "    make logs       - View logs"
echo "    make health     - Check health"
echo ""
echo "  MCP Server: ./mindbank-mcp"
echo ""
if [ "$AGENT_CHOICE" = "1" ]; then
    echo "  Restart Hermes for changes to take effect:"
    echo "    hermes chat"
elif [ "$AGENT_CHOICE" = "2" ]; then
    echo "  Restart Claude Code for changes to take effect"
fi
echo ""
