#!/bin/bash
# MindBank Plugin Installer
# Installs MindBank for Claude Desktop, Claude Code CLI, Hermes Agent, or all
#
# Usage:
#   bash install-plugin.sh                          # interactive menu
#   bash install-plugin.sh --all                    # install for all detected
#   bash install-plugin.sh --claude-desktop         # Claude Desktop only
#   bash install-plugin.sh --claude-code            # Claude Code CLI only
#   bash install-plugin.sh --hermes                 # Hermes Agent only
#
# Environment Variables:
#   HERMES_HOME        - Hermes home directory (default: ~/.hermes)
#   MINDBANK_PORT      - API port (default: 8095)
#   MINDBANK_URL       - Full API URL override
#   MINDBANK_NS        - Default namespace override
#   MINDBANK_MCP_BIN   - Path to mindbank-mcp binary (default: auto-detect)

set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
MINDBANK_SRC="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MINDBANK_PORT="${MINDBANK_PORT:-8095}"
MINDBANK_URL="${MINDBANK_URL:-http://localhost:${MINDBANK_PORT}/api/v1}"

echo "╔══════════════════════════════════════════════════╗"
echo "║  MindBank Installer                              ║"
echo "║  v0.1.0                                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ---- Detect MCP binary ----
MCP_BIN="${MINDBANK_MCP_BIN:-}"
if [ -z "$MCP_BIN" ]; then
    for candidate in \
        "$SCRIPT_DIR/../mindbank-mcp" \
        "$SCRIPT_DIR/mindbank-mcp" \
        "/usr/local/bin/mindbank-mcp" \
        "$HOME/.local/bin/mindbank-mcp"; do
        if [ -x "$candidate" ]; then
            MCP_BIN="$candidate"
            break
        fi
    done
fi

# ---- Detect available targets ----
HAS_CLAUDE_DESKTOP=false
HAS_CLAUDE_CODE=false
HAS_HERMES=false

CLAUDE_DESKTOP_CONFIG=""
if [ "$(uname)" = "Darwin" ]; then
    CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    CLAUDE_DESKTOP_CONFIG="$HOME/.config/claude/claude_desktop_config.json"
fi
if command -v claude &>/dev/null || [ -f "$CLAUDE_DESKTOP_CONFIG" ]; then
    HAS_CLAUDE_DESKTOP=true
fi

if command -v claude &>/dev/null; then
    HAS_CLAUDE_CODE=true
fi

if command -v hermes &>/dev/null; then
    HAS_HERMES=true
fi

# ---- Check MindBank API ----
if ! curl -sf "http://localhost:${MINDBANK_PORT}/api/v1/health" &>/dev/null; then
    echo "WARNING: MindBank API not running on :${MINDBANK_PORT}"
    echo "Start it first: cd /path/to/mindbank && make run"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# ---- Parse args or show menu ----
INSTALL_CLAUDE_DESKTOP=false
INSTALL_CLAUDE_CODE=false
INSTALL_HERMES=false

case "${1:-}" in
    --all)
        INSTALL_CLAUDE_DESKTOP=true
        INSTALL_CLAUDE_CODE=true
        INSTALL_HERMES=true
        ;;
    --claude-desktop)
        INSTALL_CLAUDE_DESKTOP=true
        ;;
    --claude-code)
        INSTALL_CLAUDE_CODE=true
        ;;
    --hermes)
        INSTALL_HERMES=true
        ;;
    *)
        echo "Detected:"
        echo ""
        echo "  [1] Claude Desktop   $([ "$HAS_CLAUDE_DESKTOP" = true ] && echo "✓ found" || echo "  not found")"
        echo "  [2] Claude Code CLI  $([ "$HAS_CLAUDE_CODE" = true ] && echo "✓ found" || echo "  not found")"
        echo "  [3] Hermes Agent     $([ "$HAS_HERMES" = true ] && echo "✓ found" || echo "  not found")"
        echo ""
        echo "Enter choices (e.g. 1 3 or 'all'), or press Enter to skip:"
        read -p "> " CHOICES

        if [ -z "$CHOICES" ]; then
            echo "Nothing selected. Exiting."
            exit 0
        fi

        if [[ "$CHOICES" == *"all"* ]]; then
            INSTALL_CLAUDE_DESKTOP=true
            INSTALL_CLAUDE_CODE=true
            INSTALL_HERMES=true
        else
            for c in $CHOICES; do
                case $c in
                    1) INSTALL_CLAUDE_DESKTOP=true ;;
                    2) INSTALL_CLAUDE_CODE=true ;;
                    3) INSTALL_HERMES=true ;;
                    *) echo "Unknown option: $c" ;;
                esac
            done
        fi
        ;;
esac

# ---- Find plugin source (for Hermes) ----
PLUGIN_SOURCE=""
if [ -n "$MINDBANK_SRC" ] && [ -f "$MINDBANK_SRC/__init__.py" ]; then
    PLUGIN_SOURCE="$MINDBANK_SRC/__init__.py"
elif [ -f "$SCRIPT_DIR/../plugins/memory/mindbank/__init__.py" ]; then
    PLUGIN_SOURCE="$SCRIPT_DIR/../plugins/memory/mindbank/__init__.py"
elif [ -f "$SCRIPT_DIR/__init__.py" ]; then
    PLUGIN_SOURCE="$SCRIPT_DIR/__init__.py"
fi

# ---- Build MCP config JSON ----
build_mcp_config() {
    local db_dsn="${MB_DB_DSN:-postgres://mindbank:mindbank_secret@localhost:5432/mindbank?sslmode=disable}"
    cat << EOJSON
{
  "command": "${MCP_BIN}",
  "args": [],
  "env": {
    "MB_DB_DSN": "${db_dsn}",
    "MB_OLLAMA_URL": "${MB_OLLAMA_URL:-http://localhost:11434}",
    "MB_PORT": "${MINDBANK_PORT}"
  }
}
EOJSON
}

# =============================================
# CLAUDE DESKTOP
# =============================================
if [ "$INSTALL_CLAUDE_DESKTOP" = true ]; then
    echo ""
    echo "── Claude Desktop ──────────────────────────"

    if [ -z "$MCP_BIN" ]; then
        echo "  ERROR: mindbank-mcp binary not found."
        echo "  Build it first: make build-mcp"
        echo "  Then set MINDBANK_MCP_BIN=/path/to/mindbank-mcp"
        echo "  Skipped."
    else
        mkdir -p "$(dirname "$CLAUDE_DESKTOP_CONFIG")"

        if [ -f "$CLAUDE_DESKTOP_CONFIG" ]; then
            # Merge into existing config
            if python3 -c "
import json, sys
with open('$CLAUDE_DESKTOP_CONFIG') as f:
    cfg = json.load(f)
cfg.setdefault('mcpServers', {})['mindbank'] = $(build_mcp_config | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)))')
with open('$CLAUDE_DESKTOP_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null; then
                echo "  Config: $CLAUDE_DESKTOP_CONFIG (updated)"
            else
                echo "  ERROR: Failed to update config. Check JSON syntax."
            fi
        else
            cat > "$CLAUDE_DESKTOP_CONFIG" << EOF
{
  "mcpServers": {
    "mindbank": $(build_mcp_config)
  }
}
EOF
            echo "  Config: $CLAUDE_DESKTOP_CONFIG (created)"
        fi
        echo "  Installed ✓"
    fi
fi

# =============================================
# CLAUDE CODE CLI
# =============================================
if [ "$INSTALL_CLAUDE_CODE" = true ]; then
    echo ""
    echo "── Claude Code CLI ─────────────────────────"

    if [ -z "$MCP_BIN" ]; then
        echo "  ERROR: mindbank-mcp binary not found."
        echo "  Build it first: make build-mcp"
        echo "  Skipped."
    else
        CLAUDE_CODE_CONFIG="$HOME/.claude/mcp.json"
        mkdir -p "$(dirname "$CLAUDE_CODE_CONFIG")"

        if [ -f "$CLAUDE_CODE_CONFIG" ]; then
            if python3 -c "
import json
with open('$CLAUDE_CODE_CONFIG') as f:
    cfg = json.load(f)
cfg.setdefault('mcpServers', {})['mindbank'] = $(build_mcp_config | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)))')
with open('$CLAUDE_CODE_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null; then
                echo "  Config: $CLAUDE_CODE_CONFIG (updated)"
            else
                echo "  ERROR: Failed to update config."
            fi
        else
            cat > "$CLAUDE_CODE_CONFIG" << EOF
{
  "mcpServers": {
    "mindbank": $(build_mcp_config)
  }
}
EOF
            echo "  Config: $CLAUDE_CODE_CONFIG (created)"
        fi
        echo "  Installed ✓"
    fi
fi

# =============================================
# HERMES
# =============================================
if [ "$INSTALL_HERMES" = true ]; then
    echo ""
    echo "── Hermes Agent ────────────────────────────"

    if [ -z "$PLUGIN_SOURCE" ]; then
        echo "  ERROR: Could not find mindbank plugin source (__init__.py)."
        echo "  Run from mindbank repo or pass explicit path."
    else
        PLUGIN_DIR="$HERMES_HOME/hermes-agent/plugins/memory/mindbank"
        echo "  Source: $PLUGIN_SOURCE"
        echo "  Target: $PLUGIN_DIR"
        mkdir -p "$PLUGIN_DIR"
        cp "$PLUGIN_SOURCE" "$PLUGIN_DIR/__init__.py"
        echo "  Installed ✓"

        # Config
        CONFIG_FILE="$HERMES_HOME/mindbank.json"
        if [ ! -f "$CONFIG_FILE" ]; then
            cat > "$CONFIG_FILE" << EOF
{
  "api_url": "${MINDBANK_URL}",
  "namespace": "${MINDBANK_NS:-}"
}
EOF
            echo "  Config: $CONFIG_FILE (created)"
        else
            echo "  Config: $CONFIG_FILE (exists, not modified)"
        fi

        # Namespace map
        NS_MAP="$HERMES_HOME/mindbank-namespaces.json"
        if [ ! -f "$NS_MAP" ]; then
            cat > "$NS_MAP" << 'EOF'
{}
EOF
            echo "  Namespace map: $NS_MAP (empty, add your mappings)"
        else
            echo "  Namespace map: $NS_MAP (exists, not modified)"
        fi
    fi
fi

# =============================================
# SUMMARY
# =============================================
echo ""
echo "══════════════════════════════════════════════"
echo ""

if [ "$INSTALL_CLAUDE_DESKTOP" = true ] || [ "$INSTALL_CLAUDE_CODE" = true ]; then
    echo "MCP Server (Claude):"
    echo "  Binary: ${MCP_BIN:-NOT FOUND — build with: make build-mcp}"
    echo ""
fi

if [ "$INSTALL_HERMES" = true ]; then
    echo "Hermes Plugin:"
    echo "  Start hermes: hermes chat"
    echo ""
fi

echo "Available Tools (same across all clients):"
echo "  mindbank_store      - Save facts, decisions, questions, preferences"
echo "  mindbank_search     - Hybrid FTS + vector search"
echo "  mindbank_ask        - Ask natural language questions about memory"
echo "  mindbank_snapshot   - Get wake-up context summary"
echo "  mindbank_neighbors  - Explore connected memories in graph"
echo ""
echo "Restart your AI client for changes to take effect."
