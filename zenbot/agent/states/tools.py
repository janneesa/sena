"""UseTools state for executing tool calls."""

from __future__ import annotations

import json

from zenbot.agent.types import EventType
from zenbot.agent.states.base import State
from zenbot.agent.utils.logging import get_logger
from zenbot.agent.utils.json_utils import safe_parse_json

logger = get_logger("zenbot")


class UseTools(State):
	"""State that executes pending tool calls and feeds results back to the LLM."""

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
		raw_args = tool_call.get("args")

		tool = agent.toolbox.get_tool(tool_name)
		if tool is not None:
			agent.output.emit_status(tool.user_message)
		logger.info(f"Tool started: {tool_name}")

		raw_args = safe_parse_json(raw_args)
		result = agent.toolbox.run_tool(tool_name, raw_args)
		agent.turn.tool_results.append(
			{"tool_name": tool_name, "args": raw_args or {}, "result": result}
		)
		
		# For list_reminders, use the LLM-generated summary to avoid hallucination
		tool_content = result
		if tool_name == "list_reminders" and "summary" in result:
			# Pass only the summary and count to the LLM to prevent it from
			# reconstructing reminders from conversation history
			tool_content = {
				"success": result.get("success"),
				"count": result.get("count"),
				"summary": result.get("summary")
			}
		
		agent.turn.llm_messages.append(
			{
				"role": "tool",
				"tool_name": tool_name,
				"content": json.dumps(tool_content),
			}
		)

		if "error" in result:
			logger.warning(f"Tool failed: {tool_name}")
		else:
			logger.info(f"Tool completed: {tool_name}")

		if "error" not in result and not agent.turn.pending_tool_calls:
			response_field = self._DIRECT_TOOL_RESPONSE_FIELDS.get(tool_name)
			if response_field:
				response_text = str(result.get(response_field, "")).strip()
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
