from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sena.agent.agent import Agent
    from sena.agent.types import Event


class State(ABC):
    """Abstract base class for all agent states.
    
    A state receives events, optionally mutates the agent's context, and returns
    the next state in the state machine. States must always return a State instance
    (never None); if no transition is desired, return self.
    
    The state machine is driven by the Agent.dispatch() and Agent.drain() methods,
    which feed events to states and manage transitions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this state for logging and debugging.
        
        Returns:
            str: The state name (e.g., 'IDLE', 'GENERATE').
        """
        raise NotImplementedError

    @abstractmethod
    def handle(self, agent: "Agent", event: "Event") -> "State":
        """Process an event and return the next state.
        
        This method must:
        - Not block forever (or not for long periods).
        - Return a State instance (can return self to stay in the current state).
        - Optionally mutate the agent's state (messages, turn, etc.).
        
        Args:
            agent: The Agent instance.
            event: The Event to process.
        
        Returns:
            State: The next state to transition to (or self to remain).
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<State {self.name}>"
