"""Typed configuration loader with env > local.toml > default.toml precedence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sena.agent.utils.logging import get_logger

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


logger = get_logger("sena")


@dataclass(frozen=True)
class LLMSettings:
    """Settings for the Language Model backend.
    
    Attributes:
        model: Name of the LLM model to use (e.g., 'qwen2.5:14b'). Must be available in the configured Ollama instance.
        stream: Whether to stream token responses (True) or wait for full response (False).
        think: Whether to enable extended thinking mode for models that support it (True/False).
    """
    model: str
    stream: bool
    think: bool


@dataclass(frozen=True)
class AgentSettings:
    """Settings for the Agent state machine and conversation management.
    
    Attributes:
        max_internal_steps: Maximum number of internal state transitions per drain() call.
        max_history_messages: Maximum number of non-system messages to keep in history.
        debug: Enable DEBUG-level logging for state transitions and configuration details.
        reminder_poll_seconds: Reminder worker polling interval in seconds.
    """
    max_internal_steps: int
    max_history_messages: int
    debug: bool
    reminder_poll_seconds: int


@dataclass(frozen=True)
class Settings:
    """Top-level immutable settings."""
    llm: LLMSettings
    agent: AgentSettings


def _parse_bool(value: str) -> bool:
    """Parse common boolean strings."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise ValueError(f"Cannot parse '{value}' as boolean")


def _load_toml(path: Path) -> dict:
    """Load TOML file, returning empty dict when missing."""
    if not path.exists():
        return {}
    
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        raise RuntimeError(f"Failed to load TOML file {path}: {exc}") from exc


def _get_config_dir() -> Path:
    """Return absolute path to project `config/` directory."""
    agent_dir = Path(__file__).parent
    project_root = agent_dir.parent.parent
    config_dir = project_root / "config"
    
    if not config_dir.exists():
        raise RuntimeError(
            f"Config directory not found. Expected: {config_dir}\n"
            "Please run Sena from the project root or ensure config/default.toml exists."
        )
    
    return config_dir


def _merged_sections(default_data: dict, local_data: dict) -> dict:
    merged: dict[str, dict] = {}
    for section in ("llm", "agent"):
        merged[section] = {
            **default_data.get(section, {}),
            **local_data.get(section, {}),
        }
    return merged


def _env_or(config: dict, env_key: str, config_key: str, default=None):
    return os.getenv(env_key, config.get(config_key, default))


def _int_value(raw_value, field_name: str) -> int:
    try:
        return int(raw_value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be an integer. Got: {raw_value}") from exc


def _bool_value(raw_value, env_key: str) -> bool:
    try:
        return _parse_bool(raw_value) if isinstance(raw_value, str) else bool(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid {env_key} value: {raw_value}") from exc


def load_settings() -> Settings:
    """Load and validate settings from TOML + env overrides."""
    config_dir = _get_config_dir()

    default_path = config_dir / "default.toml"
    if not default_path.exists():
        raise RuntimeError(f"default.toml not found at {default_path}")

    default_data = _load_toml(default_path)
    local_path = config_dir / "local.toml"
    local_data = _load_toml(local_path)

    merged = _merged_sections(default_data, local_data)

    llm_config = merged["llm"]
    llm_model = _env_or(llm_config, "SENA_MODEL", "model")
    llm_stream_raw = _env_or(llm_config, "SENA_STREAM", "stream")
    llm_think_raw = _env_or(llm_config, "SENA_THINK", "think", False)

    if not llm_model:
        raise ValueError("LLM model not configured. Set SENA_MODEL or config llm.model")

    llm_settings = LLMSettings(
        model=llm_model,
        stream=_bool_value(llm_stream_raw, "SENA_STREAM"),
        think=_bool_value(llm_think_raw, "SENA_THINK"),
    )

    agent_config = merged["agent"]
    agent_max_internal_steps_raw = _env_or(agent_config, "SENA_MAX_INTERNAL_STEPS", "max_internal_steps")
    agent_max_history_raw = _env_or(agent_config, "SENA_MAX_HISTORY_MESSAGES", "max_history_messages")
    agent_debug_raw = _env_or(agent_config, "SENA_DEBUG", "debug", False)
    agent_reminder_poll_raw = _env_or(
        agent_config,
        "SENA_REMINDER_POLL_SECONDS",
        "reminder_poll_seconds",
        30,
    )

    if agent_max_internal_steps_raw is None:
        raise ValueError("max_internal_steps not configured. Set SENA_MAX_INTERNAL_STEPS or config agent.max_internal_steps")
    if agent_max_history_raw is None:
        raise ValueError("max_history_messages not configured. Set SENA_MAX_HISTORY_MESSAGES or config agent.max_history_messages")

    agent_max_internal_steps = _int_value(agent_max_internal_steps_raw, "max_internal_steps")
    agent_max_history = _int_value(agent_max_history_raw, "max_history_messages")
    agent_reminder_poll = _int_value(agent_reminder_poll_raw, "reminder_poll_seconds")

    if agent_max_internal_steps <= 0:
        raise ValueError(f"max_internal_steps must be greater than zero, got {agent_max_internal_steps}. Set SENA_MAX_INTERNAL_STEPS or config agent.max_internal_steps.")
    if agent_max_history < 2:
        raise ValueError(f"max_history_messages must be at least 2, got {agent_max_history}. Set SENA_MAX_HISTORY_MESSAGES or config agent.max_history_messages.")
    if agent_reminder_poll <= 0:
        raise ValueError(f"reminder_poll_seconds must be greater than zero, got {agent_reminder_poll}. Set SENA_REMINDER_POLL_SECONDS or config agent.reminder_poll_seconds.")

    agent_debug = _bool_value(agent_debug_raw, "SENA_DEBUG")
    agent_settings = AgentSettings(
        max_internal_steps=agent_max_internal_steps,
        max_history_messages=agent_max_history,
        debug=agent_debug,
        reminder_poll_seconds=agent_reminder_poll,
    )
    
    settings = Settings(llm=llm_settings, agent=agent_settings)
    stream_mode = "streaming" if llm_settings.stream else "non-streaming"
    logger.info(
        f"Configuration loaded: model={llm_settings.model}, mode={stream_mode}, "
        f"debug={agent_debug}"
    )

    return settings
