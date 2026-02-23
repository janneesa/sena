"""Configuration system for ZenBot.

This module provides a typed configuration loader that reads settings from TOML files
and environment variables, following a clear precedence order:

1. Environment variables (highest priority)
2. config/local.toml (if it exists)
3. config/default.toml (lowest priority)

Configuration is structured using dataclasses for type safety and clarity. All settings
are immutable (frozen) after loading to prevent accidental runtime mutation.

Configuration Validation:
    All configuration values are validated immediately after loading. Invalid values
    cause a ValueError to be raised with a clear, actionable error message. This "fail fast"
    approach prevents invalid configurations from propagating to runtime.
    
    Validation rules:
    - max_internal_steps: Must be an integer > 0
    - max_history_messages: Must be an integer >= 2
    - stream: Must be a boolean
    - debug: Must be a boolean

Configuration Logging:
    Upon successful loading, an INFO-level message is logged indicating the model name,
    streaming mode, and debug flag. No sensitive values are logged.

Example usage:
    settings = load_settings()  # Loads and validates configuration
    agent = Agent(settings=settings)

Environment Variables:
    ZENBOT_MODEL: LLM model name (default: ministral-3:14b)
    ZENBOT_STREAM: Whether to stream responses (default: true)
    ZENBOT_THINK: Enable extended thinking mode (default: false)
    ZENBOT_MAX_INTERNAL_STEPS: Max state machine steps (default: 8, must be > 0)
    ZENBOT_MAX_HISTORY_MESSAGES: Max conversation history (default: 20, must be >= 2)
    ZENBOT_REMINDER_POLL_SECONDS: Reminder worker poll interval (default: 30, must be > 0)
    ZENBOT_DEBUG: Enable DEBUG-level logging (default: false)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from zenbot.agent.utils.logging import get_logger

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


logger = get_logger("zenbot")


@dataclass(frozen=True)
class LLMSettings:
    """Settings for the Language Model backend.
    
    Attributes:
        model: Name of the LLM model to use (e.g., 'qwen2.5:14b').
               Must be available in the configured Ollama instance.
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
                           Prevents infinite loops in the state machine.
                           Must be greater than zero.
        max_history_messages: Maximum number of non-system messages to keep in history.
                             Older messages are trimmed when this limit is exceeded.
                             Must be at least two.
        debug: Enable DEBUG-level logging for state transitions and configuration details.
               When False, only INFO and above are logged.
        reminder_poll_seconds: Reminder worker polling interval in seconds.
                              Must be greater than zero.
    """
    max_internal_steps: int
    max_history_messages: int
    debug: bool
    reminder_poll_seconds: int


@dataclass(frozen=True)
class Settings:
    """Top-level configuration object for ZenBot.
    
    Groups all settings into logical subgroups (LLM, Agent) and provides a single,
    immutable configuration object for the entire application.
    
    Immutability is enforced using frozen=True on the dataclass. This design ensures:
    - Configuration cannot be accidentally mutated at runtime
    - Deterministic behavior across the agent lifecycle
    - Clear separation between configuration (creation time) and runtime state
    - Thread-safety when passed to multiple components
    
    All validation of configuration values happens during load_settings(); invalid
    configurations are rejected immediately with clear error messages rather than
    allowing bad values to propagate to runtime.
    
    Attributes:
        llm: Language model settings (model, stream).
        agent: Agent state machine and conversation settings (max_internal_steps,
               max_history_messages, debug).
    """
    llm: LLMSettings
    agent: AgentSettings


def _parse_bool(value: str) -> bool:
    """Parse a string value as a boolean.
    
    Args:
        value: A string that should represent a boolean.
               Accepts "true", "false" (case-insensitive), "1", "0".
    
    Returns:
        bool: True if value is "true", "1" (case-insensitive); False otherwise.
    
    Raises:
        ValueError: If value is not a recognized boolean representation.
    """
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise ValueError(f"Cannot parse '{value}' as boolean")


def _load_toml(path: Path) -> dict:
    """Load a TOML file if it exists.
    
    Args:
        path: Path to the TOML file.
    
    Returns:
        dict: Parsed TOML data, or empty dict if file does not exist.
    """
    if not path.exists():
        return {}
    
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load TOML file {path}: {e}") from e


def _get_config_dir() -> Path:
    """Get the config directory path (relative to project root).
    
    Returns:
        Path: The absolute path to the config/ directory.
    
    Raises:
        RuntimeError: If config directory cannot be located.
    """
    # Start from this file's directory (zenbot/agent/)
    # Go up two levels to project root, then look for config/
    agent_dir = Path(__file__).parent
    project_root = agent_dir.parent.parent
    config_dir = project_root / "config"
    
    if not config_dir.exists():
        raise RuntimeError(
            f"Config directory not found. Expected: {config_dir}\n"
            "Please run ZenBot from the project root or ensure config/default.toml exists."
        )
    
    return config_dir


def load_settings() -> Settings:
    """Load ZenBot configuration from files and environment variables.
    
    Configuration precedence (highest to lowest):
    1. Environment variables (ZENBOT_* prefix)
    2. config/local.toml (if it exists)
    3. config/default.toml (required; must exist)
    
    Configuration values are validated immediately after loading:
    - max_internal_steps must be greater than zero
    - max_history_messages must be at least two
    
    After successful loading, logs an INFO-level message indicating the configured
    model and streaming mode. No sensitive values are logged.
    
    Returns:
        Settings: The loaded, merged, and validated configuration object.
    
    Raises:
        RuntimeError: If config/default.toml is missing or malformed.
        ValueError: If required fields are missing, invalid, or fail validation.
    """
    # Get logger for configuration messages
    config_logger = logger
    
    config_dir = _get_config_dir()
    
    # Load default configuration (required)
    default_path = config_dir / "default.toml"
    if not default_path.exists():
        raise RuntimeError(f"default.toml not found at {default_path}")
    
    default_data = _load_toml(default_path)
    
    # Load local configuration (optional)
    local_path = config_dir / "local.toml"
    local_data = _load_toml(local_path)
    
    # Merge configurations: local overrides default
    merged = {}
    
    # Deep merge for nested sections
    for section in ("llm", "agent"):
        merged[section] = {}
        if section in default_data:
            merged[section].update(default_data[section])
        if section in local_data:
            merged[section].update(local_data[section])
    
    # Extract LLM settings
    llm_config = merged.get("llm", {})
    llm_model = os.getenv("ZENBOT_MODEL", llm_config.get("model"))
    llm_stream_raw = os.getenv("ZENBOT_STREAM", llm_config.get("stream"))
    llm_think_raw = os.getenv("ZENBOT_THINK", llm_config.get("think", False))
    
    if not llm_model:
        raise ValueError("LLM model not configured. Set ZENBOT_MODEL or config llm.model")
    
    try:
        llm_stream = _parse_bool(llm_stream_raw) if isinstance(llm_stream_raw, str) else bool(llm_stream_raw)
    except ValueError as e:
        raise ValueError(f"Invalid ZENBOT_STREAM value: {llm_stream_raw}") from e
    
    try:
        llm_think = _parse_bool(llm_think_raw) if isinstance(llm_think_raw, str) else bool(llm_think_raw)
    except ValueError as e:
        raise ValueError(f"Invalid ZENBOT_THINK value: {llm_think_raw}") from e
    
    llm_settings = LLMSettings(model=llm_model, stream=llm_stream, think=llm_think)
    
    # Extract Agent settings
    agent_config = merged.get("agent", {})
    agent_max_internal_steps_raw = os.getenv(
        "ZENBOT_MAX_INTERNAL_STEPS",
        agent_config.get("max_internal_steps")
    )
    agent_max_history_raw = os.getenv(
        "ZENBOT_MAX_HISTORY_MESSAGES",
        agent_config.get("max_history_messages")
    )
    agent_debug_raw = os.getenv(
        "ZENBOT_DEBUG",
        agent_config.get("debug", False)
    )
    agent_reminder_poll_raw = os.getenv(
        "ZENBOT_REMINDER_POLL_SECONDS",
        agent_config.get("reminder_poll_seconds", 30),
    )
    
    if agent_max_internal_steps_raw is None:
        raise ValueError(
            "max_internal_steps not configured. Set ZENBOT_MAX_INTERNAL_STEPS or config agent.max_internal_steps"
        )
    if agent_max_history_raw is None:
        raise ValueError(
            "max_history_messages not configured. Set ZENBOT_MAX_HISTORY_MESSAGES or config agent.max_history_messages"
        )
    
    try:
        agent_max_internal_steps = int(agent_max_internal_steps_raw)
        agent_max_history = int(agent_max_history_raw)
        agent_reminder_poll = int(agent_reminder_poll_raw)
    except (ValueError, TypeError) as e:
        raise ValueError(
            "max_internal_steps, max_history_messages, and reminder_poll_seconds must be integers. "
            f"Got: {agent_max_internal_steps_raw}, {agent_max_history_raw}, {agent_reminder_poll_raw}"
        ) from e
    
    # Validate agent settings
    if agent_max_internal_steps <= 0:
        raise ValueError(
            f"max_internal_steps must be greater than zero, got {agent_max_internal_steps}. "
            "Set ZENBOT_MAX_INTERNAL_STEPS or config agent.max_internal_steps."
        )
    
    if agent_max_history < 2:
        raise ValueError(
            f"max_history_messages must be at least 2, got {agent_max_history}. "
            "Set ZENBOT_MAX_HISTORY_MESSAGES or config agent.max_history_messages."
        )

    if agent_reminder_poll <= 0:
        raise ValueError(
            f"reminder_poll_seconds must be greater than zero, got {agent_reminder_poll}. "
            "Set ZENBOT_REMINDER_POLL_SECONDS or config agent.reminder_poll_seconds."
        )
    
    try:
        agent_debug = _parse_bool(agent_debug_raw) if isinstance(agent_debug_raw, str) else bool(agent_debug_raw)
    except ValueError as e:
        raise ValueError(f"Invalid ZENBOT_DEBUG value: {agent_debug_raw}") from e
    
    agent_settings = AgentSettings(
        max_internal_steps=agent_max_internal_steps,
        max_history_messages=agent_max_history,
        debug=agent_debug,
        reminder_poll_seconds=agent_reminder_poll,
    )
    
    settings = Settings(llm=llm_settings, agent=agent_settings)
    
    # Log successful configuration load with key settings
    stream_mode = "streaming" if llm_settings.stream else "non-streaming"
    config_logger.info(
        f"Configuration loaded: model={llm_settings.model}, mode={stream_mode}, "
        f"debug={agent_debug}"
    )
    
    return settings
