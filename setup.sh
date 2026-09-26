#!/bin/bash
set -e

# Directory of this repo (setup.sh is run from inside the target project)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== claude-code-deepseek-delegate setup ==="
echo ""

# 1. Dependencies
echo "[1/5] Installing Python dependencies..."
pip install requests graphifyy --quiet
echo "      Done."

# 2. graphify init
echo "[2/5] Initializing graphify knowledge graph..."
if [ ! -f "graphify-out/graph.json" ]; then
    graphify update .
    echo "      Done."
else
    echo "      Already initialized, skipping."
fi

# 3. Copy the delegate script and Claude Code hooks into the project
echo "[3/5] Copying tools/ask-deepseek.py and .claude/settings.json..."
mkdir -p tools .claude
cp "$REPO_DIR/tools/ask-deepseek.py" tools/ask-deepseek.py
if [ ! -f ".claude/settings.json" ]; then
    cp "$REPO_DIR/.claude/settings.json" .claude/settings.json
    echo "      Done."
else
    echo "      .claude/settings.json already exists, not overwritten."
    echo "      Tip: merge the hooks from $REPO_DIR/.claude/settings.json manually"
fi

# 4. API key
echo "[4/5] Setting up DeepSeek API key..."
if [ -f ".env" ] && grep -q "DEEPSEEK_API_KEY" .env; then
    echo "      Already set in .env, skipping."
else
    echo ""
    echo "  Get your API key at: https://platform.deepseek.com"
    read -p "  Enter your DEEPSEEK_API_KEY: " api_key
    echo "DEEPSEEK_API_KEY=$api_key" >> .env
    echo "      Saved to .env"
fi
if [ ! -f ".gitignore" ] || ! grep -qx ".env" .gitignore; then
    echo ".env" >> .gitignore
    echo "      Added .env to .gitignore"
fi

# 5. Copy CLAUDE.md template
echo "[5/5] Setting up CLAUDE.md..."
if [ ! -f "CLAUDE.md" ]; then
    cp "$REPO_DIR/CLAUDE.md.template" CLAUDE.md
    echo "      Created CLAUDE.md from template."
else
    echo "      CLAUDE.md already exists."
    echo "      Tip: manually add the contents of $REPO_DIR/CLAUDE.md.template to your existing CLAUDE.md"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Verify with:"
echo "  graphify query 'main components'"
echo "  python tools/ask-deepseek.py 'what does this do?' tools/ask-deepseek.py"
