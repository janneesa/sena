# ZenBot: Guide for Coding Agents

Synchronous state-machine AI agent framework.
Python 3.13+. Default Ollama endpoint: `localhost:11434`.

Philosophy:
- Minimal dependencies and explicit data flow
- Local-first (LLM, tools, and data run locally)
- Deterministic logic around LLM outputs

Third-party dependencies:
- `ollama` (LLM chat and tool calls)
- `pydantic` (schema validation and structured extraction)
- `python-dotenv` (environment variable loading)

Standard library usage (core):
- `sqlite3`, `datetime`, `threading`, `queue`, `pathlib`, `dataclasses`, `enum`,
  `typing`, `uuid`, `json`, `logging`, `time`, `os`, `sys`, `tomllib`

## Package Management & Running

Use `uv` for dependency management.

- `uv sync` install dependencies
- `uv run python -m zenbot` run project

Do not edit dependencies directly; use `uv` to update `pyproject.toml`.

## Core Architecture

ZenBot is driven by a synchronous state machine.

The Agent owns state transitions, event dispatch, the TICK loop, history trimming,
configuration injection, and logging. States implement behavior but do not control
orchestration.

## State Machine Contract

- `State.handle(agent, event)` must return a `State` instance (never `None`)
- `handle()` may return `self` to remain in the same state
- States must not mutate configuration
- States must not introduce global state
- State transitions are controlled by `Agent`, not by states directly

## Configuration

Precedence: environment variables > `config/local.toml` > `config/default.toml`.

Loaded once at startup via `load_settings()`.
Validation rules:
- `max_internal_steps` > 0
- `max_history_messages` >= 2

Settings are immutable. Do not mutate at runtime.
Do not hardcode model names, limits, or ports.

## Logging

- Uses Python `logging`
- Configured once at startup
- DEBUG: state transitions, dispatch events
- INFO: configuration summary
- WARNING: loop guard triggers

Do not log LLM token streams or sensitive data.

## Testing Expectations

- Use Python `unittest`
- Run all tests with `uv run python -m unittest discover -s tests -v`
- Update tests with behavior changes
- Add tests for new features or paths

## Utilities

### datetime_utils

Reusable datetime parsing and calculations:

```python
from zenbot.agent.utils.datetime_utils import (
    parse_time_string,           # "9:15", "3:45 PM" -> (9, 15)
    resolve_date_expression,     # "tomorrow", "monday" -> date object
    combine_date_and_time,       # Merge into ISO-8601 with timezone
    parse_iso_datetime,          # Safe ISO parsing
    is_datetime_past,            # Check if datetime is in past
)
```

Why separate from tools: centralizes datetime logic for reuse and testability.

### json_utils

LLM integration helpers - see `json_utils.py` docstrings.

### database

SQLite operations for persistence - `DatabaseHelper` class handles all reminder CRUD.

---

## Tool Usage Patterns

LLM-assisted extraction using `call_llm_with_format()`:
- Define a Pydantic model for structured output
- Provide clear system prompt (no side effects instructions)
- Handle `None` result gracefully
- Never trust the LLM for calculations (use programmatic logic)

Reminder tool workflow:
1. Extract: LLM extracts user intent to schema
2. Parse: programmatic parsing/validation
3. Calculate: deterministic computations
4. Save: database operations
5. Confirm: generate user-facing response

Do not have the LLM perform calculations or manipulate data structures.

