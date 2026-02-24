"""Utilities for JSON and argument handling."""

from __future__ import annotations

import json
from typing import Any, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def safe_parse_json(raw: Any) -> dict[str, Any]:
    """Parse raw arguments to a dictionary, handling string JSON and nested dicts.
    
    Args:
        raw: Raw argument data (dict, string, or other).
    
    Returns:
        dict: Parsed arguments, or empty dict if parsing fails.
    """
    if isinstance(raw, dict):
        return raw
    
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    
    return {}


def call_llm_with_format(
    model: str,
    messages: list[dict[str, Any]],
    schema_class: type[T],
    think: bool = False,
) -> T | None:
    """
    Call LLM with structured output format and validate using Pydantic.
    
    Args:
        model: Model name to use with Ollama.
        messages: Message history in standard chat format.
        schema_class: Pydantic model class for deserializing response.
        think: Whether to enable thinking mode.
    
    Returns:
        Validated schema instance, or None if extraction/validation fails.
    """
    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            format=schema_class.model_json_schema(),
            stream=False,
            think=think,
        )
        raw = response.get("message", {}).get("content", "")
        return schema_class.model_validate_json(raw)
    except (ValidationError, ValueError, json.JSONDecodeError):
        return None

