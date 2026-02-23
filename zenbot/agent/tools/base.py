from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel


class Tool(ABC):
    """Abstract base class for all tools."""

    name: str
    user_message: str
    ArgsModel: Type[BaseModel]

    @abstractmethod
    def run(self, args: BaseModel) -> dict[str, Any]:
        """Run the tool with validated arguments."""
        raise NotImplementedError
