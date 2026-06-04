"""Meeting transcription app.

Lives next to `core` so it can FK Room without creating a dependency cycle.
Owns:

- The `MeetingUtterance` model that stores speaker text emitted by the
  agent worker during a meeting.
- A server-to-server write endpoint authenticated by a shared
  `AGENT_API_KEY`.
- Query helpers consumed by MCP tools in `core.api.mcp`.
"""

default_app_config = "transcription.apps.TranscriptionConfig"
