# ZenBot (ongoing)

ZenBot is a synchronous state-machine AI agent project built with Python and Ollama.
This project explores how AI agents and large language models can be integrated into practical software applications through a synchronous, state-machine architecture.

<video controls loop autoplay muted playsinline>
	<source src="media/zenbot_terminal_demo.mp4" type="video/mp4">
</video>

Video: [media/zenbot_terminal_demo.mp4](media/zenbot_terminal_demo.mp4)

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
└── data/                 # SQLite database
```

## Notes

This is a personal learning project.
