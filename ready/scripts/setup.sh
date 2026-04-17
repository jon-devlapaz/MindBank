#!/bin/bash
# MindBank Quick Setup
# Usage: bash scripts/setup.sh
#
# Prerequisites: Go 1.23+, Docker, Ollama

set -e

echo ""
echo "  MindBank Setup"
echo "  =============="
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."
MISSING=""
command -v go &>/dev/null || MISSING="$MISSING go"
command -v docker &>/dev/null || MISSING="$MISSING docker"
command -v curl &>/dev/null || MISSING="$MISSING curl"

if [ -n "$MISSING" ]; then
    echo "  ERROR: Missing:$MISSING"
    exit 1
fi
echo "  OK"

# Check Ollama
echo "[2/5] Checking Ollama..."
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "  Ollama is running"
    # Check if model is installed
    if curl -s http://localhost:11434/api/tags | grep -q "nomic-embed-text"; then
        echo "  nomic-embed-text model found"
    else
        echo "  Pulling nomic-embed-text model..."
        curl -s http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'
    fi
else
    echo "  WARNING: Ollama not running on port 11434"
    echo "  Install: https://ollama.ai"
    echo "  Then run: ollama pull nomic-embed-text"
fi

# Copy config
echo "[3/5] Setting up config..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate random password
    PASS=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | head -c 32)
    sed -i "s/mindbank_secret/$PASS/" .env
    echo "  Created .env with random password"
else
    echo "  .env already exists, skipping"
fi

# Start database
echo "[4/5] Starting PostgreSQL..."
make db-up

# Build
echo "[5/5] Building..."
make build

echo ""
echo "  Setup complete!"
echo ""
echo "  Start MindBank:"
echo "    make run"
echo ""
echo "  Then open:"
echo "    http://localhost:8095"
echo ""
