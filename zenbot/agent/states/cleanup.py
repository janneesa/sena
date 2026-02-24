"""Cleanup state for turn finalization.

This state is the final step in a turn: commit history and reset transient state,
then transition back to Idle (rest state).

All user-facing output is handled by the communication manager during earlier states.
This state performs only internal housekeeping.
"""

from __future__ import annotations

from zenbot.agent.states.base import State
from zenbot.agent.types import EventType
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class Cleanup(State):
    """State that finalizes a turn by committing history and returns to Idle."""

    @property
    def name(self) -> str:
        return "CLEANUP"

    def handle(self, agent, event):
        if event is None or event.event_type != EventType.TICK:
            logger.debug("Cleanup ignoring non-TICK event")
            return self

        from zenbot.agent.states.idle import Idle

        logger.debug("Cleanup committing turn and returning to IDLE")
        agent.commit_turn()
        return Idle()
