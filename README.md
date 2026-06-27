# claude-code-deepseek-delegate

**Cut Claude Code token costs by ~80% on large codebases.**

A three-layer analysis system: route structural questions through a free knowledge graph, delegate large-file analysis to DeepSeek (cheap), and only pull source into Claude's context when you're about to edit.

```
graphify (free)  →  DeepSeek (cheap)  →  Claude (edit only)
```

---

## The problem

Claude Code reads entire files into context. On a large file:

| Action | Tokens consumed |
|---|---|
| Read a 1300-line file directly | ~23,000 tokens |
| Trace a flow across 3 large files | ~60,000 tokens |
| Answer "where is X defined?" with grep | ~5,000 tokens |

At scale, this adds up fast.

## The solution

This repo gives you two things:

1. **`tools/ask-deepseek.py`** — a CLI that sends large files to DeepSeek and returns a short, line-numbered answer. Claude reads the answer (~300 tokens), then reads only the 20 lines it needs to edit.

2. **Claude Code enforcement hooks** (`.claude/settings.json`) — intercept grep and file-read tool calls, reminding Claude to check the knowledge graph first before loading raw files.

Combined with [graphify](https://github.com/graphify-dev/graphify) for free structural lookups, the result:

| Action | Before | After |
|---|---|---|
| "Where is X defined?" | ~5,000 tokens | 0 (graphify) |
| Analyze 1300-line file | ~23,000 tokens | ~400 tokens |
| Trace flow across 3 files | ~60,000 tokens | ~1,500 tokens |

---

## Quickstart

```bash
git clone https://github.com/YOUR_USERNAME/claude-code-deepseek-delegate
cd your-project
bash /path/to/claude-code-deepseek-delegate/setup.sh
```

`setup.sh` will:
- Install `requests` and `graphify`
- Run `graphify init .` to build the knowledge graph
- Ask you for your DeepSeek API key and save it to `.env`
- Copy `CLAUDE.md.template` to `CLAUDE.md`

Get a free DeepSeek API key at [platform.deepseek.com](https://platform.deepseek.com).

---

## Usage

```bash
# Structural question — use graphify (free)
graphify query "auth token refresh flow"
graphify explain "TranslationBubble"
graphify path "reading screen" "database"

# Large file analysis — delegate to DeepSeek (cheap)
python tools/ask-deepseek.py "Where is the highlight logic rendered?" "app/reading/screen.tsx"
python tools/ask-deepseek.py "How does this state sync work?" store/myStore.ts

# Review a diff
python tools/ask-deepseek.py "Any logic errors?" --stdin < changes.diff

# Hard analysis — use the reasoning model
python tools/ask-deepseek.py "Explain this state flow" store/myStore.ts --reasoner

# After DeepSeek answers → read only those specific lines → edit
```

---

## Decision chain

Always follow this order:

```
1. graphify query/explain/path
       ↓ (if not enough)
2. python tools/ask-deepseek.py "question" file.ts
       ↓ (DeepSeek returns line range)
3. Read only those lines → edit
```

**Never** grep or read a full file before trying graphify first.  
**Never** apply an edit based solely on DeepSeek output — verify the line range yourself.

---

## Files

```
tools/ask-deepseek.py     — delegation script (the core of this repo)
.claude/settings.json     — Claude Code enforcement hooks
CLAUDE.md.template        — rules to add to your project's CLAUDE.md
setup.sh                  — automated setup
```

---

## Compatibility

Works with any Claude model (Opus, Sonnet, Haiku) — the hooks intercept tool calls regardless of model.

The decision chain rules in `CLAUDE.md.template` can also be added to the system prompt of other AI coding tools (Cursor, Windsurf, OpenCode, etc.).

---

## Requirements

- Python 3.8+
- `pip install requests graphify`
- DeepSeek API key (free tier available)
- Claude Code (for the enforcement hooks)
