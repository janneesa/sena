from __future__ import annotations

from abc import ABC, abstractmethod


class OutputManager(ABC):
    """Abstract output surface for user-visible messages and streaming."""

    @abstractmethod
    def emit_text(self, text: str) -> None:
        """Emit a complete line of text to the user."""
        raise NotImplementedError

    @abstractmethod
    def emit_status(self, text: str) -> None:
        """Emit a non-final status/progress message to the user."""
        raise NotImplementedError

    @abstractmethod
    def begin_stream(self) -> None:
        """Start a streaming assistant output section."""
        raise NotImplementedError

    @abstractmethod
    def emit_stream_chunk(self, chunk: str) -> None:
        """Emit a single chunk of streaming output."""
        raise NotImplementedError

    @abstractmethod
    def end_stream(self) -> None:
        """Close a streaming assistant output section."""
        raise NotImplementedError


class ConsoleOutputManager(OutputManager):
    """Console output implementation used by the CLI runtime."""

    def __init__(self) -> None:
        self._stream_open = False

    def emit_text(self, text: str) -> None:
        if not text:
            return
        print(text)

    def emit_status(self, text: str) -> None:
        if not text:
            return
        print(text)

    def begin_stream(self) -> None:
        self._stream_open = True

    def emit_stream_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        print(chunk, end="", flush=True)

    def end_stream(self) -> None:
        if self._stream_open:
            print()
            self._stream_open = False


output_manager = ConsoleOutputManager()
