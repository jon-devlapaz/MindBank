#!/bin/bash
# MindBank Quick Install
# Usage: curl -sSL https://raw.githubusercontent.com/spfcraze/MindBank/main/install.sh | bash

set -e

echo "Installing MindBank..."

# Clone the repository
git clone https://github.com/spfcraze/MindBank.git ~/MindBank
cd ~/MindBank

# Run setup
make setup

echo ""
echo "✅ MindBank installed successfully!"
echo ""
echo "Dashboard: http://localhost:8095"
echo ""
echo "To start MindBank later:"
echo "  cd ~/MindBank"
echo "  make run"
echo ""
