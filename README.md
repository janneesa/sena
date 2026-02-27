# ZenBot (ongoing)

ZenBot is a synchronous state-machine AI agent project built with Python and Ollama.
This project explores how AI agents and large language models can be integrated into practical software applications through a synchronous, state-machine architecture.

<video loop autoplay muted playsinline>
	<source src="media/zenbot_terminal_demo.mp4" type="video/mp4">
</video>

## Philosophy

- Keep dependencies minimal and explicit.
- Run everything locally (LLM, tools, data).
- Prefer clear, deterministic logic around LLM output.
- Use a simple, synchronous state machine for transparency.

## Features

- State machine orchestration (Idle → Generate → UseTools → Cleanup)
- Tool system for structured LLM calls
- Local Ollama integration
- SQLite persistence for reminders
- Config via TOML + environment variables

## Data Models (where they are used)

- `zenbot/agent/types.py`
  - `EventType` / `Event`: queued inputs to the state machine (`USER_MESSAGE`, `REMINDER_DUE`, `TICK`).
  - `Turn`: temporary per-turn working state for `Generate` and `UseTools`.
- Tool-specific Pydantic models in `zenbot/agent/tools/*`
  - `*Args` models validate tool call inputs.
  - Extraction/confirmation models (for example `ReminderRequest`, `ReminderMatch`) validate structured LLM JSON before any DB writes.
- Config dataclasses in `zenbot/agent/config.py`
  - `Settings`, `LLMSettings`, `AgentSettings` are immutable startup config loaded once.

## Quick Start

Prerequisites:
- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [Ollama](https://ollama.ai/) running locally (default `localhost:11434`)

Install and run:

```bash
uv sync
uv run python -m zenbot
```

## Running with Docker

ZenBot can run as a hardened non-root container while preserving the host workflow above.

### Docker Compose (recommended)

Create your runtime env file (Docker reads this automatically):

```bash
cp .env.example .env
```

Build and run interactively:

```bash
docker compose build
docker compose run --rm -it zenbot
```

Linux note (for bind-mount file ownership compatibility):

```bash
export UID=$(id -u)
export GID=$(id -g)
```

The compose setup:
- runs as a non-root user (`${UID:-10001}:${GID:-10001}`)
- mounts `./workspace` to `/workspace`
- sets `WORKSPACE_ROOT=/workspace`
- sets container timezone via `TZ` (default `Europe/Helsinki`) for local reminder times
- loads runtime environment values from `.env`
- uses read-only root filesystem with writable `/tmp` and `/run` tmpfs mounts
- drops all Linux capabilities and disables privilege escalation

The default command is `python -m zenbot`, and you can override it for debugging, for example:

```bash
docker compose run --rm -it zenbot python -m unittest discover -s tests -v
```

Database persistence in Docker:
- ZenBot stores SQLite at `/workspace/data/zenbot.db` when `WORKSPACE_ROOT=/workspace`.
- Because `/workspace` is a bind mount to host `./workspace`, reminders persist across container restarts/removals.

Database persistence on host:
- ZenBot stores SQLite at `./workspace/data/zenbot.db` by default.
- The `workspace` directory is created automatically on first run.

### Ollama connectivity

- Windows/macOS Docker Desktop: `http://host.docker.internal:11434` works by default.
- Linux Docker Engine: use Docker 20.10+ with host-gateway support and add:
  - `extra_hosts: ["host.docker.internal:host-gateway"]` in compose (already included).

Any existing `ZENBOT_*` environment variables continue to work and can be passed via compose.

For compose, prefer putting them in `.env` (copied from `.env.example`).

You can change Docker reminder local time behavior by setting `TZ` in `.env` (for example `TZ=Europe/Helsinki`).

## Configuration

Config precedence:
1. Environment variables (highest)
2. config/local.toml
3. config/default.toml

System instructions:
- config/default_system.md (shipped default)
- config/system.md (override; used only when it exists and is non-empty)

To customize the bot personality, create config/system.md with your own instructions.
Delete or empty that file to revert to the default.

Common settings:
- `model` (Ollama model name)
- `max_internal_steps` (loop guard)
- `max_history_messages` (history size)
- `reminder_poll_seconds` (worker interval)

### Choosing a model

You are free to use any Ollama model, but it should support tool calling for the agent to work reliably.

Current reference setup:
- GPU: NVIDIA RTX 2070
- RAM: 16 GB
- Model used for development/testing: `ministral-3:14b`

In local testing, some models under 10B were faster but less reliable with tool usage. Tool prompts are being improved so smaller models can use tools more consistently over time.

## Built-in Tools

- DateTime: current time
- Set Reminder: store reminder with date/time
- List Reminders: show active reminders
- Delete Reminder: remove reminder by intent

## Development

Run tests:

```bash
uv run python -m unittest discover -s tests -v
```

## Dependencies (minimal by design)

Third-party:
- `ollama` - LLM chat and tool calls
- `pydantic` - input validation and structured extraction
- `python-dotenv` - environment variable loading

Python standard library (core usage):
- `sqlite3` - persistence
- `datetime` - time handling
- `threading` - background workers
- `queue` - event queue
- `pathlib` - path management
- `dataclasses` - config and event models
- `enum` - event types
- `typing` - type hints
- `uuid` - reminder IDs
- `json` - tool payloads
- `logging` - structured logs
- `time` - main loop pacing
- `os` / `sys` / `tomllib` - configuration loading

## Project Structure

```
zenbot/
├── agent/
│   ├── states/           # State implementations
│   ├── tools/            # Built-in tools
│   ├── utils/            # Helpers and database
│   └── workers/          # Background workers
├── config/               # default/local/system prompt
└── workspace/            # Runtime data (SQLite, future user files)
```

## Notes

This is a personal learning project.
