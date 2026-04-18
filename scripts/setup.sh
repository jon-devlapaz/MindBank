#!/bin/bash
# MindBank Complete Setup — One-command install for new users
# Usage: curl -sSL https://raw.githubusercontent.com/.../setup.sh | bash
# Or:    bash setup.sh

set -e

MINDBANK_DIR="${MINDBANK_DIR:-$HOME/mindbank}"
MINDBANK_PORT="${MINDBANK_PORT:-8095}"
MINDBANK_PG_PORT="${MINDBANK_PG_PORT:-5434}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  MindBank — Graph Memory for Hermes Agent         ║"
echo "║  Complete Setup                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Step 1: Check prerequisites
echo "[1/7] Checking prerequisites..."
MISSING=""
command -v docker &>/dev/null || MISSING="$MISSING docker"
command -v curl &>/dev/null || MISSING="$MISSING curl"
command -v hermes &>/dev/null || echo "  WARNING: hermes not found — plugin install will be skipped"

if [ -n "$MISSING" ]; then
    echo "  ERROR: Missing: $MISSING"
    echo "  Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "  OK"

# Step 2: Create directory structure
echo "[2/7] Creating directory structure..."
mkdir -p "$MINDBANK_DIR"/{migrations,scripts,internal,cmd,plugins/memory/mindbank}
echo "  OK"

# Step 3: Generate secure password
echo "[3/7] Generating credentials..."
DB_PASS=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | head -c 32)
API_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | head -c 64)
echo "  Generated DB password and API key"

# Step 4: Create docker-compose.yml
echo "[4/7] Creating Docker Compose config..."
cat > "$MINDBANK_DIR/docker-compose.yml" << EOF
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: mindbank-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: mindbank
      POSTGRES_USER: mindbank
      POSTGRES_PASSWORD: ${DB_PASS}
    ports:
      - "${MINDBANK_PG_PORT}:5432"
    volumes:
      - mindbank-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mindbank"]
      interval: 5s
      timeout: 5s
      retries: 5
volumes:
  mindbank-pgdata:
EOF
echo "  OK"

# Step 5: Start Postgres
echo "[5/7] Starting Postgres..."
cd "$MINDBANK_DIR"
docker compose up -d postgres
echo "  Waiting for Postgres to be healthy..."
for i in $(seq 1 30); do
    if docker exec mindbank-postgres pg_isready -U mindbank &>/dev/null; then
        echo "  Postgres ready"
        break
    fi
    sleep 1
done

# Step 6: Create config
echo "[6/7] Creating configuration..."
cat > "$MINDBANK_DIR/.env" << EOF
# MindBank Configuration
MB_PORT=${MINDBANK_PORT}
MB_DB_DSN=postgres://mindbank:${DB_PASS}@localhost:${MINDBANK_PG_PORT}/mindbank?sslmode=disable
MB_OLLAMA_URL=http://localhost:11434
MB_EMBED_MODEL=nomic-embed-text
MB_LOG_LEVEL=info
MB_API_KEY=${API_KEY}
EOF
echo "  OK"

# Step 7: Install Hermes plugin
echo "[7/7] Installing Hermes plugin..."
if command -v hermes &>/dev/null; then
    mkdir -p "$HERMES_HOME/plugins/mindbank"

    # Find plugin source
    PLUGIN_SRC=""
    if [ -f "$MINDBANK_DIR/plugins/memory/mindbank/__init__.py" ]; then
        PLUGIN_SRC="$MINDBANK_DIR/plugins/memory/mindbank/__init__.py"
    elif [ -f "$MINDBANK_DIR/scripts/install-plugin.sh" ]; then
        bash "$MINDBANK_DIR/scripts/install-plugin.sh" "$MINDBANK_DIR/plugins/memory/mindbank"
        PLUGIN_SRC="installed_via_script"
    fi

    if [ -n "$PLUGIN_SRC" ] && [ "$PLUGIN_SRC" != "installed_via_script" ]; then
        cp "$PLUGIN_SRC" "$HERMES_HOME/plugins/mindbank/__init__.py"
    fi

    # Create plugin config
    cat > "$HERMES_HOME/mindbank.json" << EOF
{
  "api_url": "http://localhost:${MINDBANK_PORT}/api/v1",
  "namespace": ""
}
EOF

    echo "  Plugin installed to $HERMES_HOME/plugins/mindbank/"
    echo "  Config created at $HERMES_HOME/mindbank.json"
else
    echo "  Skipped (hermes not found)"
fi

# Done!
echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  Setup Complete!                                  ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Start MindBank API:"
echo "     cd $MINDBANK_DIR && source .env && ./mindbank-api"
echo ""
echo "  2. Verify it's running:"
echo "     curl http://localhost:${MINDBANK_PORT}/api/v1/health"
echo ""
echo "  3. Open the dashboard:"
echo "     http://localhost:${MINDBANK_PORT}"
echo ""
echo "  4. For auto-start on boot:"
echo "     cp $MINDBANK_DIR/scripts/mindbank.service ~/.config/systemd/user/"
echo "     systemctl --user enable --now mindbank"
echo ""
echo "  API Key: ${API_KEY}"
echo "  (Set MB_API_KEY env var to require auth)"
echo ""
echo "  Namespace auto-detection:"
echo "    cd /your/project && hermes chat"
echo "    → memories stored under 'your-project' namespace"
echo ""
