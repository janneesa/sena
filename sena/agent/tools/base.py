from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel


class Tool(ABC):
    """Abstract base class for all tools.
    
    Subclasses must define:
    - name: identifier used by Ollama and agent (str)
    - description: LLM-facing description of what the tool does (str)
    - user_message: status message shown to user during execution (str)
    - ArgsModel: Pydantic model for validated tool arguments (Type[BaseModel])
    """

    name: str
    description: str
    user_message: str
    ArgsModel: Type[BaseModel]

    @abstractmethod
    def run(self, args: BaseModel) -> dict[str, Any]:
        """Run the tool with validated arguments."""
        raise NotImplementedError
