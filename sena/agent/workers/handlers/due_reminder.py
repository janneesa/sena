"""Handler for due reminder events."""

from __future__ import annotations

from datetime import datetime

import ollama

from sena.agent.utils.logging import get_logger


logger = get_logger("sena")


def handle_due_reminder(agent, payload: dict) -> str:
    """Generate and emit a friendly due-reminder message.
    
    The reminder is already marked completed by the worker.
    Gets current local time context and uses LLM to compose a friendly notification.
    
    Args:
        agent: The Agent instance with settings and output manager
        payload: Dict with 'task', 'when', and optional 'notes' keys
        
    Returns:
        str: The reminder notification message
    """
    task = str(payload.get("task", "your reminder")).strip() or "your reminder"
    when_text = str(payload.get("when", "")).strip()
    notes = str(payload.get("notes", "")).strip()

    # Get current local time to help LLM generate contextually correct messages
    now_local = datetime.now().astimezone()
    current_time_context = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    system_prompt = (
        "Write one short, friendly reminder notification for the user. "
        "The reminder is due now, so tell them it is time to do the task now. "
        "Focus only on this task and optional notes. "
        "Do not mention other reminders, future timing, or scheduling actions. "
        "Return plain text only."
        "The reminder will be deleted after this notification, so do not include instructions about snoozing or rescheduling."
    )
    user_prompt = (
        f"Current local date/time: {current_time_context}\n"
        f"Task: {task}\n"
        f"Due at: {when_text or 'now'}"
    )
    if notes:
        user_prompt += f"\nNotes: {notes}"

    try:
        response = ollama.chat(
            model=agent.settings.llm.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            think=agent.settings.llm.think,
        )
        message = response.get("message", {}).get("content", "").strip()
    except Exception:
        logger.exception("Failed to compose reminder_due message")
        message = "Hey, just a reminder: it's time now."

    if not message:
        message = "Hey, just a reminder: it's time now."

    agent.turn.assistant_text = message
    agent.turn.assistant_streamed = False
    agent.output.emit_text(message)
    logger.debug(f"Reminder notified: {task}")
    
    return message
