# DeepSheets

AI-powered reading companion using DeepSeek + VS Code Copilot.  
**Understand books deeply, not just re-read them.**

[![Watch the setup - 1 minute](https://img.youtube.com/vi/TWOJE_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=TWOJE_VIDEO_ID)

---

## What is this?

You paste a PDF or EPUB, DeepSheets splits it into chapters, extracts key themes via DeepSeek, and turns VS Code Copilot into a personal reading tutor that:

- Asks **targeted questions** about what you read
- Identifies **specific gaps** in your understanding
- Builds a **growing quiz pool** with citations from the text
- Tracks progress across sessions so you **never repeat what you already know**

Zero UI. Everything happens in VS Code Copilot chat (Agent mode).

---

## Quick Start (5 minutes)

### 1. Prerequisites

- **DeepSeek account** with a few dollars of credit — [sign up here](https://platform.deepseek.com)
- **GitHub Copilot** subscription (free tier works — just sign in with GitHub)
- [VS Code](https://code.visualstudio.com/) **1.116+**
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### 2. Set up DeepSeek in Copilot

DeepSeek is NOT the default Copilot model — you need to add it as an extension.
You also need a DeepSeek account with some credits (prices are low, ~$0.14/1M tokens).

1. Create an account at **[platform.deepseek.com](https://platform.deepseek.com)** and top up a few dollars
2. Install **[DeepSeek V4 for Copilot](https://github.com/Vizards/deepseek-v4-for-copilot)** VS Code extension
3. Get an API key at **[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)**
4. In VS Code: `Ctrl+Shift+P` → **DeepSeek: Set API Key** → paste your key
5. Open Copilot Chat (`Ctrl+Shift+I`) → click the model picker (top-right) → select **DeepSeek V4 Pro**
6. Optional: click the gear icon next to the model → set thinking effort to **High** or **Max**

Full guide: **[api-docs.deepseek.com/quick_start/agent_integrations/github_copilot](https://api-docs.deepseek.com/quick_start/agent_integrations/github_copilot)**

That's it. Copilot + DeepSeek handles all the AI work. No other keys needed.

### 3. Install DeepSheets

```powershell
# Clone and enter the repo
cd deepsheets

# Install dependencies (creates .venv automatically)
uv sync

# Ready. No .env file needed — Copilot handles everything.
```

### 4. Open the folder in VS Code

```powershell
code .
```

**This is critical.** VS Code Copilot auto-detects `AGENTS.md` from the workspace root. If you open just a file (not the folder), it won't work.

Now open Copilot Chat and switch to **Agent mode** (Ctrl+Shift+I → pick "Agent" from the dropdown).

### 5. Start reading — Copilot does the rest

Paste your book file path:

> "Mam książkę: C:/Users/zenon/books/moja-ksiazka.epub. Przeparsuj ją i zacznijmy rozdział 1."

Copilot will:
1. **Run** `uv run scripts/parse_book.py` — splits into `chapters/`
2. **Run** `uv run scripts/pre_analyze.py` — extracts key themes via DeepSeek
3. **Start** the reading session — asks questions, gives Feedback Sandwich
4. **Auto-update** `state/session_state.json` — progress saved across sessions
5. **Build** a quiz pool with source citations from the text

**You never touch the terminal** after initial setup. Just chat.

---

## How It Works

```
your-book.epub
    │
    ▼
scripts/parse_book.py       →  chapters/*.md
    │
    ▼
scripts/pre_analyze.py      →  state/session_state.json  (key themes)
    │
    ▼
AGENTS.md + VS Code Copilot →  interactive reading session
    │                           • Feedback Sandwich
    │                           • auto-updates state
    │                           • builds quiz pool
    ▼
scripts/quiz_pool.py         →  deterministic MCQ with source citations
```

---

## Commands Reference

| What | Command |
|---|---|
| Parse book | `uv run scripts/parse_book.py book.epub` |
| Parse single chapter | `uv run scripts/parse_book.py book.pdf --chapter 3` |
| Pre-analyze chapter | `uv run scripts/pre_analyze.py chapters/.../rozdzial_01.md` |
| Re-analyze (force) | `uv run scripts/pre_analyze.py ... --force` |
| Decide next action | `uv run scripts/decide.py` |
| Add quiz question | `uv run scripts/quiz_pool.py add --chapter 1 --question "..." --correct "X" --wrong "A" "B" "C" --source-quote "..."` |
| Generate quiz | `uv run scripts/quiz_pool.py generate --chapter 1 --count 5` |
| Score answer | `uv run scripts/quiz_pool.py score --question-id 7 --user-answer "X"` |
| List quiz pool | `uv run scripts/quiz_pool.py list --chapter 1` |

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM | DeepSeek (`deepseek-chat`, 1M context, Polish-friendly) |
| Chat interface | VS Code Copilot (Agent mode, no UI to build) |
| PDF parsing | Marker (local ML) → PyMuPDF (fallback) |
| EPUB parsing | EbookLib |
| Package mgr | uv |
| State | JSON files (zero setup) |
| Config | pydantic-settings from `.env` |
| License | MIT |

---

## Why "DeepSheets"?

DeepSeek helps you turn the pages ("sheets") of a book into deep understanding.  
Simple, cheap, no SaaS lock-in.

---

## License

MIT — use it, fork it, share it.
