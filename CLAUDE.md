# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

Requires Python 3.13+ and `uv`. Always use `uv` to run the server and manage packages — never use `pip` directly. Must run from the `backend/` directory:

```bash
# Quick start (from project root, Git Bash on Windows)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8000
```

App runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

**Environment setup:**
```bash
uv sync                          # Install dependencies
cp .env.example .env             # Then add your ANTHROPIC_API_KEY
```

Always use `uv` for all package management — never `pip`:
```bash
uv add <package>      # Add a dependency
uv remove <package>   # Remove a dependency
uv sync               # Sync environment to lockfile
```

## Architecture

This is a full-stack RAG chatbot. The backend is a FastAPI app (`backend/`) that serves both the API and the static frontend (`frontend/`). There is no build step for the frontend.

### RAG Query Pipeline

The core flow for a user query:

1. `app.py` receives `POST /api/query` and delegates to `RAGSystem.query()`
2. `rag_system.py` wraps the query, fetches session history, and calls `AIGenerator.generate_response()` with the `search_course_content` tool available
3. `ai_generator.py` makes a **first Claude API call**. If Claude decides to search (`stop_reason == "tool_use"`), it calls `_handle_tool_execution()`
4. `search_tools.py` → `VectorStore.search()` performs semantic search against ChromaDB
5. Tool results are appended to the message history and a **second Claude API call** generates the final answer
6. Sources and answer are returned up the chain; session history is updated

If Claude answers from its own knowledge (`stop_reason == "end_turn"`), steps 4–5 are skipped entirely.

### Vector Store (ChromaDB)

Two collections in `chroma_db/` (auto-created, persisted on disk):
- `course_catalog` — one entry per course; used for fuzzy course-name resolution via vector search
- `course_content` — chunked lesson text; used for semantic content retrieval

Both use `all-MiniLM-L6-v2` embeddings via `sentence-transformers`.

### Document Format

Course files in `docs/` must follow this structure for correct parsing:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <title>
...
```

Only `.txt` files are functionally supported (`.pdf`/`.docx` are detected but not parsed). On startup, already-indexed courses are skipped automatically by comparing titles.

### Key Configuration (`backend/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model used for generation |
| `CHUNK_SIZE` | `800` | Max characters per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `MAX_RESULTS` | `5` | ChromaDB search results returned |
| `MAX_HISTORY` | `2` | Conversation exchanges retained per session |

### Adding a New Tool

1. Create a class extending `Tool` (ABC) in `search_tools.py` implementing `get_tool_definition()` and `execute()`
2. Register it in `RAGSystem.__init__()` via `tool_manager.register_tool()`

The tool definition must follow Anthropic's tool-use schema. Claude will call it automatically when appropriate.
