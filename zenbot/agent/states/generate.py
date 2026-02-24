"""State that asks the LLM for the next assistant step."""

from __future__ import annotations

import ollama

from zenbot.agent.types import EventType
from zenbot.agent.states.base import State
from zenbot.agent.utils.json_utils import safe_parse_json
from zenbot.agent.states.cleanup import Cleanup
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class Generate(State):
    """Generate assistant output and queue tool calls when requested."""
    @property
    def name(self):
        return "GENERATE"

    def handle(self, agent, event):
        """Generate a response when activated by a TICK event."""
        if event is None or event.event_type != EventType.TICK:
            logger.debug("Generate ignoring non-TICK event")
            return self

        if not agent.turn.llm_messages:
            agent.turn.llm_messages = list(agent.messages)
            agent.turn.llm_messages.append({"role": "user", "content": agent.turn.user_text})
            logger.debug("Generate initialized turn llm_messages from history")

        tools = agent.toolbox.get_ollama_tool_functions()
        logger.debug(f"Generate calling LLM with {len(tools)} available tools")

        try:
            response = ollama.chat(
                model=agent.settings.llm.model,
                messages=agent.turn.llm_messages,
                tools=tools,
                stream=agent.settings.llm.stream,
                think=agent.settings.llm.think,
            )
        except Exception:
            logger.exception("Generate failed during ollama.chat call")
            error_message = "Sorry, I hit an internal error while generating a response."
            agent.turn.assistant_text = error_message
            agent.output.emit_text(error_message)
            return Cleanup()

        if agent.settings.llm.stream:
            response = self._process_streamed_response(agent, response)
        
        self._handle_response(agent, response)

        response_message = response.get("message", {})
        tool_calls = response_message.get("tool_calls") or []

        if tool_calls:
            logger.info(f"Generate received {len(tool_calls)} tool call(s)")
            agent.turn.assistant_streamed = False
            agent.turn.llm_messages.append(response_message)
            self._enqueue_tool_calls(agent, tool_calls)
            from zenbot.agent.states.use_tools import UseTools
            return UseTools()

        return Cleanup()

    def _process_streamed_response(self, agent, response) -> dict:
        """Process streamed response from LLM and aggregate chunks.
        
        Args:
            agent: The Agent instance.
            response: Stream iterator from ollama.chat.
        
        Returns:
            dict: Aggregated response with assembled message content.
        """
        parts = []
        tool_calls = []
        stream_open = False
        
        for chunk in response:
            msg = chunk.get("message", {})
            delta = msg.get("content", "")
            if delta:
                if not stream_open:
                    agent.output.begin_stream()
                    stream_open = True
                agent.output.emit_stream_chunk(delta)
                parts.append(delta)
            chunk_tool_calls = msg.get("tool_calls") or []
            if chunk_tool_calls:
                tool_calls.extend(chunk_tool_calls)

        if stream_open:
            agent.output.end_stream()

        return {
            "message": {
                "role": "assistant",
                "content": "".join(parts),
                "tool_calls": tool_calls or None,
            }
        }

    def _handle_response(self, agent, response: dict) -> None:
        """Persist assistant text and emit output for non-tool responses."""
        response_message = response.get("message", {})
        tool_calls = response_message.get("tool_calls") or []

        if tool_calls:
            return  # Will be handled by caller

        logger.debug("Generate received assistant response with no tool calls")
        agent.turn.assistant_text = response_message.get("content", "")
        agent.turn.assistant_streamed = bool(agent.settings.llm.stream and agent.turn.assistant_text)
        
        if agent.turn.assistant_text and not agent.turn.assistant_streamed:
            agent.output.emit_text(agent.turn.assistant_text)

    def _enqueue_tool_calls(self, agent, tool_calls: list) -> None:
        """Parse and enqueue tool calls from LLM response.
        
        Args:
            agent: The Agent instance.
            tool_calls: List of tool call dicts from LLM response.
        """
        for tool_call in tool_calls:
            function_payload = tool_call.get("function", {})
            tool_name = str(function_payload.get("name", "")).strip()
            raw_args = function_payload.get("arguments", {})
            raw_args = safe_parse_json(raw_args)

            if tool_name:
                agent.turn.pending_tool_calls.append(
                    {"tool_name": tool_name, "args": raw_args}
                )
            else:
                logger.warning("Generate encountered tool call without function name")



