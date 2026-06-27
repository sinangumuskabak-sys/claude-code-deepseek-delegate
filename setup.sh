#!/bin/bash
set -e

echo "=== claude-code-deepseek-delegate setup ==="
echo ""

# 1. Dependencies
echo "[1/4] Installing Python dependencies..."
pip install requests graphifyy --quiet
echo "      Done."

# 2. graphify init
echo "[2/4] Initializing graphify knowledge graph..."
if [ ! -f "graphify-out/graph.json" ]; then
    graphify init .
    echo "      Done."
else
    echo "      Already initialized, skipping."
fi

# 3. API key
echo "[3/4] Setting up DeepSeek API key..."
if [ -f ".env" ] && grep -q "DEEPSEEK_API_KEY" .env; then
    echo "      Already set in .env, skipping."
else
    echo ""
    echo "  Get your free API key at: https://platform.deepseek.com"
    read -p "  Enter your DEEPSEEK_API_KEY: " api_key
    echo "DEEPSEEK_API_KEY=$api_key" >> .env
    echo "      Saved to .env"
fi

# 4. Copy CLAUDE.md template
echo "[4/4] Setting up CLAUDE.md..."
if [ ! -f "CLAUDE.md" ]; then
    cp CLAUDE.md.template CLAUDE.md
    echo "      Created CLAUDE.md from template."
else
    echo "      CLAUDE.md already exists."
    echo "      Tip: manually add the contents of CLAUDE.md.template to your existing CLAUDE.md"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Verify with:"
echo "  graphify query 'main components'"
echo "  python tools/ask-deepseek.py 'what does this do?' tools/ask-deepseek.py"
