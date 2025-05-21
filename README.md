# Insight Digger MCP

**This project contains both the MCP server (`mcp_server.py`) and the MCP client (`mcp_client/`). Each is started separately.**

## MCP Client

The MCP client is a lightweight HTTP server that manages a single chat session for a user. It starts the MCP server as a subprocess, exposes HTTP endpoints for tool listing and invocation, and manages JWT/session parameters securely in memory. Each client runs on a dynamic port and is started on demand by the chat system.

### Endpoints
- `POST /init` — Initialize session, receive JWT and params, return port and status.
- `GET /tools` — List available tools.
- `POST /call-tool` — Call a tool by name, passing params (MCP client injects JWT as needed).
- `POST /shutdown` — Cleanly shut down client and server.
- `GET /health` — Health check (optional).

### Usage
1. Start the MCP client process (no arguments needed).
2. POST session parameters (JWT, etc.) to `/init`.
3. Use `/tools` and `/call-tool` as needed.
4. Call `/shutdown` when done with the session. 