#!/bin/bash
# MindBank Plugin Installer for Hermes Agent
# Installs the MindBank memory provider plugin
#
# Usage:
#   bash install-plugin.sh                          # auto-detect source
#   bash install-plugin.sh /path/to/mindbank-plugin # explicit source
#   HERMES_HOME=/custom/path bash install-plugin.sh # custom hermes home

set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/mindbank"
MINDBANK_SRC="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MINDBANK_PORT="${MINDBANK_PORT:-8095}"

echo "╔══════════════════════════════════════════╗"
echo "║  MindBank Plugin Installer for Hermes    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check hermes is installed
if ! command -v hermes &>/dev/null; then
    echo "ERROR: hermes command not found. Install Hermes Agent first."
    exit 1
fi

# Check MindBank API is running
if ! curl -sf "http://localhost:${MINDBANK_PORT}/api/v1/health" &>/dev/null; then
    echo "WARNING: MindBank API not running on :${MINDBANK_PORT}"
    echo "Start it first: cd /path/to/mindbank && ./mindbank-api"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# Find the plugin source
PLUGIN_SOURCE=""
if [ -n "$MINDBANK_SRC" ] && [ -f "$MINDBANK_SRC/__init__.py" ]; then
    PLUGIN_SOURCE="$MINDBANK_SRC/__init__.py"
    echo "  Source: explicit path"
elif [ -f "$SCRIPT_DIR/__init__.py" ]; then
    PLUGIN_SOURCE="$SCRIPT_DIR/__init__.py"
    echo "  Source: script directory"
elif [ -f "$SCRIPT_DIR/../__init__.py" ]; then
    PLUGIN_SOURCE="$(cd "$SCRIPT_DIR/.." && pwd)/__init__.py"
    echo "  Source: parent directory"
else
    for candidate in \
        "$HERMES_HOME"/hermes-agent/plugins/memory/mindbank/__init__.py \
        "$HOME"/.hermes/*/plugins/memory/mindbank/__init__.py \
        /usr/local/share/hermes/plugins/memory/mindbank/__init__.py \
        /usr/share/hermes/plugins/memory/mindbank/__init__.py; do
        if [ -f "$candidate" ]; then
            PLUGIN_SOURCE="$candidate"
            echo "  Source: bundled ($candidate)"
            break
        fi
    done
fi

if [ -z "$PLUGIN_SOURCE" ]; then
    echo "ERROR: Could not find mindbank plugin source."
    echo ""
    echo "Options:"
    echo "  1. Run from mindbank repo:  cd /path/to/mindbank && bash scripts/install-plugin.sh"
    echo "  2. Pass explicit path:      bash install-plugin.sh /path/to/mindbank-plugin"
    echo "  3. Place __init__.py next to this script"
    exit 1
fi

# Install
echo "  Target: $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"
cp "$PLUGIN_SOURCE" "$PLUGIN_DIR/__init__.py"
echo "  Installed ✓"

# Create config if it doesn't exist
CONFIG_FILE="$HERMES_HOME/mindbank.json"
MINDBANK_URL="${MINDBANK_URL:-http://localhost:${MINDBANK_PORT}/api/v1}"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
{
  "api_url": "${MINDBANK_URL}",
  "namespace": ""
}
EOF
    echo "  Config: $CONFIG_FILE (created)"
else
    echo "  Config: $CONFIG_FILE (exists, not modified)"
fi

echo ""
echo "✓ Plugin installed to: $PLUGIN_DIR/__init__.py"
echo "✓ Config at: $CONFIG_FILE"
echo ""
echo "Namespace behavior:"
echo "  The plugin auto-detects namespace from your working directory."
echo "  Example: working in /home/alice/my-project → namespace 'my-project'"
echo ""
echo "  To customize directory→namespace mappings, create:"
echo "    $HERMES_HOME/mindbank-namespaces.json"
echo '    {"my-project": "custom-ns", "other-dir": "other-ns"}'
echo ""
echo "  Or set a fixed namespace in $CONFIG_FILE:"
echo '    {"api_url": "...", "namespace": "myproject"}'
echo ""
echo "Restart hermes for changes to take effect:"
echo "  hermes chat"
