#!/bin/bash
# MindBank stop script
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log() { echo -e "${GREEN}[mindbank]${NC} $1"; }
err() { echo -e "${RED}[mindbank]${NC} $1"; }

MB_PIDFILE="$DIR/.mindbank.pid"

# Stop MindBank API using PID file (not pkill)
if [ -f "$MB_PIDFILE" ]; then
    PID=$(cat "$MB_PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Stopping MindBank API (PID $PID)..."
        kill "$PID" 2>/dev/null
        # Wait for graceful shutdown
        for i in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                log "MindBank API stopped."
                break
            fi
            sleep 0.5
        done
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            log "Force killing MindBank..."
            kill -9 "$PID" 2>/dev/null || true
            sleep 1
            log "MindBank API force stopped."
        fi
    else
        log "MindBank PID $PID is not running (stale PID file)."
    fi
    rm -f "$MB_PIDFILE"
else
    log "No PID file found. MindBank may not be running."
fi

# BUGFIX: Use "stop" not "down" — down removes containers and loses data
# "stop" keeps containers, "down" removes them (and with default volumes, data loss)
if docker compose ps --status=running 2>/dev/null | grep -q mindbank-postgres; then
    log "Stopping Postgres container..."
    docker compose stop 2>/dev/null
    log "Postgres stopped (container preserved, data safe)."
else
    log "Postgres container not running."
fi

log "All services stopped."
log "To start: ./start.sh"
log "To destroy containers + data: docker compose down -v"
