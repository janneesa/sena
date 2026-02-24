from __future__ import annotations

import inspect
from typing import Any, Callable

from pydantic import ValidationError

from zenbot.agent.tools.base import Tool
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class Toolbox:
    """Registry and execution wrapper for tools."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: Tool) -> None:
        """Register a tool instance by name."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool



    def get_ollama_tool_functions(self) -> list[Callable[..., dict[str, Any]]]:
        """Return tool functions compatible with the Ollama Python SDK.
        
        The description property of each Tool is assigned as __doc__ for Ollama's tool converter.
        """
        tool_functions: list[Callable[..., dict[str, Any]]] = []
        for tool in self._tools.values():
            def _wrapper(*, _t: Tool = tool, **kwargs: Any) -> dict[str, Any]:
                return _t.run(_t.ArgsModel.model_validate(kwargs))

            # Build explicit signature from Pydantic model for Ollama's tool converter
            params = [
                inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=field.annotation or Any)
                for name, field in tool.ArgsModel.model_fields.items()
            ]

            _wrapper.__name__ = tool.name
            _wrapper.__doc__ = tool.description
            _wrapper.__signature__ = inspect.Signature(params)
            tool_functions.append(_wrapper)

        return tool_functions

    def get_tool(self, name: str) -> Tool | None:
        """Fetch a tool by name."""
        return self._tools.get(name)

    def run_tool(self, name: str, raw_args: dict[str, Any] | None) -> dict[str, Any]:
        """Run a tool by name with raw arguments."""
        tool = self.get_tool(name)
        if not tool:
            logger.warning(f"tool={name} event=not_found")
            return {"error": f"Tool not found: {name}"}

        try:
            validated = tool.ArgsModel.model_validate(raw_args or {})
            return tool.run(validated)
        except ValidationError as exc:
            logger.warning(f"tool={name} event=validation_failed")
            return {"error": "Invalid arguments", "details": exc.errors()}
        except Exception as exc:
            logger.error(f"tool={name} event=execution_failed error={exc}")
            return {"error": str(exc)}
