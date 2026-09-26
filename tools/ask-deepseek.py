"""
Delegates heavy read/analysis work to DeepSeek (cheap model).
Returns a short, line-numbered answer so Claude only reads the narrow relevant section.

Decision chain this script is part of:
  graphify (free, structural)  →  DeepSeek (cheap, semantic)  →  Claude (edit)

USAGE:
  python tools/ask-deepseek.py "QUESTION" file1 [file2 ...]
  python tools/ask-deepseek.py "Where is the cache logic?" hooks/useTranslation.ts
  python tools/ask-deepseek.py "Any errors in this diff?" --stdin < changes.diff
  python tools/ask-deepseek.py "Hard analysis" file.ts --reasoner

OPTIONS:
  --model X     Model name (default: LLM_MODEL / DEEPSEEK_MODEL or "deepseek-chat")
  --base-url U  OpenAI-compatible API base URL (default: LLM_BASE_URL or DeepSeek)
  --stdin       Use stdin content as context (for diffs/logs)
  --max-kb N    Context size limit in KB (default 600)
  --reasoner    Use deepseek-reasoner (harder problems, slightly more expensive)
  --raw         Send question as-is without system prompt
  --timeout N   Request timeout in seconds (default 120)

OTHER PROVIDERS (any OpenAI-compatible /chat/completions API), in env or .env:
  LLM_BASE_URL=https://openrouter.ai/api/v1
  LLM_API_KEY=sk-or-...
  LLM_MODEL=deepseek/deepseek-chat
  Without these, DEEPSEEK_API_KEY / DEEPSEEK_MODEL and api.deepseek.com are used.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from pathlib import Path

import requests

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "You are a code analysis assistant. You receive source files (with line numbers) and a question. "
    "Your job: help the asking AI agent navigate to the right place without reading the entire file.\n\n"
    "RULES:\n"
    "1. Be SHORT. Do not summarize the file — only address what the question asks.\n"
    "2. Give EXACT location for every finding: `file:start-end` line range.\n"
    "3. Quote at most 15-20 relevant lines, no more.\n"
    "4. If related locations exist (called function, import), give their locations too.\n"
    "5. If unsure, say so. Do not invent.\n"
    "6. Answer in the same language as the question.\n"
)


def load_setting(*names: str) -> str | None:
    """First non-empty value among names (in order); each is looked up in env, then .env."""
    values = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    for name in names:
        value = (os.environ.get(name) or "").strip() or values.get(name)
        if value:
            return value
    return None


def read_file_numbered(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Read error {path}: {e}]"
    lines = text.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}\t{ln}" for i, ln in enumerate(lines, 1))


def build_context(files: list[str], stdin_text: str | None, max_bytes: int) -> tuple[str, list[str]]:
    parts = []
    used = []
    total = 0
    for f in files:
        p = (PROJECT_ROOT / f) if not Path(f).is_absolute() else Path(f)
        if not p.is_file():
            parts.append(f"## {f}\n[NOT FOUND]\n")
            continue
        body = read_file_numbered(p)
        block = f"## FILE: {f}\n```\n{body}\n```\n"
        if total + len(block.encode("utf-8")) > max_bytes:
            remaining = max_bytes - total
            if remaining > 500:
                block = block.encode("utf-8")[:remaining].decode("utf-8", errors="replace")
                block += "\n[... TRUNCATED: file exceeded budget, use --max-kb to increase ...]\n"
                parts.append(block)
                used.append(f + " (truncated)")
            else:
                parts.append(f"## FILE: {f}\n[SKIPPED: context budget full]\n")
            break
        parts.append(block)
        used.append(f)
        total += len(block.encode("utf-8"))
    if stdin_text:
        parts.append(f"## STDIN\n```\n{stdin_text}\n```\n")
        used.append("<stdin>")
    return "\n".join(parts), used


def main():
    ap = argparse.ArgumentParser(description="Delegate heavy analysis to DeepSeek")
    ap.add_argument("question", help="Question to ask")
    ap.add_argument("files", nargs="*", help="Files to include as context")
    ap.add_argument("--model", help="Model name")
    ap.add_argument("--base-url", help="OpenAI-compatible API base URL")
    ap.add_argument("--reasoner", action="store_true", help="Use deepseek-reasoner")
    ap.add_argument("--stdin", action="store_true", help="Include stdin as context")
    ap.add_argument("--max-kb", type=int, default=600, help="Context size limit in KB")
    ap.add_argument("--raw", action="store_true", help="No system prompt")
    ap.add_argument("--timeout", type=int, default=120, help="Request timeout (seconds)")
    args = ap.parse_args()

    key = load_setting("LLM_API_KEY", "DEEPSEEK_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not found.\n"
              "Add to .env:  DEEPSEEK_API_KEY=sk-...\n"
              "Get a key at: platform.deepseek.com\n"
              "(or use another provider: LLM_BASE_URL + LLM_API_KEY + LLM_MODEL)", file=sys.stderr)
        sys.exit(2)

    base_url = (args.base_url or load_setting("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    api_url = base_url + "/chat/completions"
    if args.model:
        model = args.model
    elif args.reasoner:
        model = load_setting("LLM_REASONER_MODEL") or "deepseek-reasoner"
    else:
        model = load_setting("LLM_MODEL", "DEEPSEEK_MODEL") or DEFAULT_MODEL

    stdin_text = None
    if args.stdin and not sys.stdin.isatty():
        stdin_text = sys.stdin.read()

    context, used = build_context(args.files, stdin_text, args.max_kb * 1024)

    if args.raw:
        messages = [{"role": "user", "content": args.question + ("\n\n" + context if context else "")}]
    else:
        user_content = args.question
        if context:
            user_content += "\n\n--- CONTEXT (source files, line-numbered) ---\n" + context
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    try:
        resp = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False, "temperature": 0.2},
            timeout=args.timeout,
        )
    except requests.RequestException as e:
        print(f"ERROR: Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: API {resp.status_code} ({api_url}): {resp.text[:500]}", file=sys.stderr)
        if resp.status_code == 402:
            print("HINT: the account has no credit left. Top up, or point LLM_BASE_URL / "
                  "LLM_API_KEY / LLM_MODEL at another OpenAI-compatible provider.", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"ERROR: Unexpected response: {json.dumps(data)[:500]}", file=sys.stderr)
        sys.exit(1)

    print(answer)

    usage = data.get("usage", {})
    if usage:
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        host = base_url.split("//")[-1].split("/")[0]
        print(f"\n[{host}] model={model} | in={pt} out={ct} tokens | "
              f"context: {', '.join(used) if used else 'none'}", file=sys.stderr)


if __name__ == "__main__":
    main()
