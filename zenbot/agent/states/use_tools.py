"""State that executes pending tool calls."""

from __future__ import annotations

import json

from zenbot.agent.states.base import State
from zenbot.agent.types import EventType
from zenbot.agent.utils.json_utils import safe_parse_json
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class UseTools(State):
    """Run queued tool calls and feed tool outputs back into the LLM loop."""

    _DIRECT_TOOL_RESPONSE_FIELDS = {
        "set_reminder": "confirmation",
        "delete_reminder": "confirmation",
        "list_reminders": "summary",
    }

    @property
    def name(self) -> str:
        return "USE_TOOLS"

    def handle(self, agent, event):
        if event is None or event.event_type != EventType.TICK:
            return self

        if not agent.turn.pending_tool_calls:
            logger.debug("No pending tool calls, returning to Generate")
            from zenbot.agent.states.generate import Generate

            return Generate()

        tool_call = agent.turn.pending_tool_calls.pop(0)
        tool_name = str(tool_call.get("tool_name", "")).strip()
        tool_args = safe_parse_json(tool_call.get("args"))

        tool = agent.toolbox.get_tool(tool_name)
        if tool is not None:
            agent.output.emit_status(tool.user_message)
        logger.info(f"Tool started: {tool_name}")

        result = agent.toolbox.run_tool(tool_name, tool_args)
        agent.turn.tool_results.append(
            {"tool_name": tool_name, "args": tool_args or {}, "result": result}
        )

        tool_content = self._llm_tool_payload(tool_name, result)
        agent.turn.llm_messages.append(
            {
                "role": "tool",
                "tool_name": tool_name,
                "content": json.dumps(tool_content),
            }
        )

        logger.info(f"Tool {'failed' if 'error' in result else 'completed'}: {tool_name}")

        if "error" not in result and not agent.turn.pending_tool_calls:
            response_field = self._DIRECT_TOOL_RESPONSE_FIELDS.get(tool_name)
            response_text = str(result.get(response_field, "")).strip() if response_field else ""
            if response_text:
                agent.turn.assistant_text = response_text
                agent.turn.assistant_streamed = False
                agent.output.emit_text(response_text)
                from zenbot.agent.states.cleanup import Cleanup

                return Cleanup()

        if agent.turn.pending_tool_calls:
            return self

        from zenbot.agent.states.generate import Generate

        return Generate()

    @staticmethod
    def _llm_tool_payload(tool_name: str, result: dict) -> dict:
        if tool_name == "list_reminders" and "summary" in result:
            return {
                "success": result.get("success"),
                "count": result.get("count"),
                "summary": result.get("summary"),
            }
        return result
