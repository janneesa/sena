# Execution Flow

This document explains the end-to-end execution flow with high-level steps
and visual flow charts. It is kept aligned with the current codebase.

## Startup and Runtime Overview

```mermaid
flowchart TD
    A[Start app] --> B[Load settings]
    B --> C[Create Agent]
    C --> D[Start workers]
    D --> E[Process queued events loop]
    E --> F[Stop event]
    F --> G[Stop workers and exit]
```

### Startup steps

1. `load_settings()` loads config with precedence: env > local.toml > default.toml
2. `Agent` initializes the state machine and tool registry
3. System instructions are loaded via `ContextBuilder`
4. Workers start:
   - `InputWorker` reads user input and enqueues events
   - `ReminderWorker` polls the DB and enqueues due reminders
5. The main loop drains the event queue

## Event Processing Loop

```mermaid
flowchart TD
    A[Main loop tick] --> B{Queue has events}
    B -- Yes --> C[Dispatch and drain]
    B -- No --> D[Sleep briefly]
    C --> A
    D --> A
```

## State Machine Flow

```mermaid
flowchart LR
    Idle -- USER_MESSAGE --> Generate
    Idle -- REMINDER_DUE --> Task
    Generate -- tool_calls --> UseTools
    Generate -- no tool_calls --> Cleanup
    UseTools -- more calls --> UseTools
    UseTools -- done --> Generate
    Task --> Cleanup
    Cleanup --> Idle
```

## Generate and Tool Execution

```mermaid
flowchart TD
    A[Generate tick] --> B[Call LLM with tools]
    B --> C{Tool calls present}
    C -- Yes --> D[Go to UseTools]
    C -- No --> E[Emit response]
    E --> F[Cleanup]
```

```mermaid
flowchart TD
    A[UseTools tick] --> B{Pending tool calls}
    B -- No --> C[Return to Generate]
    B -- Yes --> D[Run next tool and append result]
    D --> E{More calls left}
    E -- Yes --> A
    E -- No --> C
```

## Reminder Flow

```mermaid
flowchart TD
    A["ReminderWorker poll once"] --> B[Load active reminders]
    B --> C[Parse ISO timestamps]
    C --> D{Due now?}
    D -- Yes --> E[Mark completed]
    E --> F[Enqueue REMINDER_DUE event]
    D -- No --> G[Skip]
```

```mermaid
flowchart TD
    A["Task handle tick"] --> B{Has reminder payload?}
    B -- No --> C[Cleanup]
    B -- Yes --> D[Compose reminder message]
    D --> E[Emit output]
    E --> C
```

## Shutdown

```mermaid
flowchart TD
    A["User types exit or quit"] --> B["InputWorker sets stop event"]
    B --> C["Main loop sees stop event"]
    C --> D[Stop InputWorker]
    D --> E[Stop ReminderWorker]
```

## Notes and Invariants

- The state machine only advances on `TICK` events during `drain()`.
- Tool calls are executed in order; the model may request multiple calls at once.
- System instructions are loaded from config/system.md if non-empty, otherwise
  config/default_system.md.
- Reminder deletions and scheduling are grounded in the SQLite database.
