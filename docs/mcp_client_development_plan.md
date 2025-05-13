# MCP Client Development Plan

## Overview

This document outlines the development plan for an **MCP client** that is started "on demand" by a chat system. The client will:
- Receive a JWT token as an initial parameter (never passing it through the LLM)
- Start `mcp_server.py` as a subprocess (via STDIO)
- Expose HTTP endpoints for the chat system to interact with the MCP tools
- Manage the lifecycle of the MCP server and client, ensuring secure, efficient, and reliable operation

---

## 1. Architecture

### Components
- **Chat System**: Triggers the need for data access and starts the MCP client
- **MCP Client**: Receives JWT, starts MCP server, exposes HTTP API
- **MCP Server**: Exposes tools via STDIO (as subprocess)
- **LLM**: Never sees the JWT; only receives tool results

### Data Flow
```
User → Chat System → MCP Client (HTTP API) → MCP Server (STDIO) → Data Source
```

---

## 2. Startup & Initialization

1. **Chat system detects need for MCP tools** (e.g., user enters a chat branch requiring data access)
2. **Chat system starts MCP client** as a new process/thread, passing the JWT token and any other required parameters (e.g., API URL, source ID)
3. **MCP client starts `mcp_server.py`** as a subprocess using STDIO
4. **MCP client initializes a session** with the MCP server, passing the JWT token as needed for each tool call
5. **MCP client exposes HTTP endpoints** for the chat system to call MCP tools

---

## 3. Security & Token Handling

- **JWT token is never passed through the LLM**
- **JWT is only in memory** in the chat backend and MCP client
- **MCP client injects JWT** into each tool call as required
- **Token expiry**: MCP client should detect and handle token expiry, returning clear errors to the chat system
- **No sensitive data is logged**

---

## 4. HTTP API Design (MCP Client)

The MCP client should expose endpoints such as:

- `GET /tools` — List available tools (with descriptions and schemas)
- `POST /call-tool` — Call a tool by name, passing parameters (including JWT as needed)
  - Request: `{ "tool": "tool_name", "params": { ... } }`
  - Response: `{ "result": ... }` or `{ "error": ... }`
- `POST /shutdown` — Cleanly shut down the MCP client and server

---

## 5. Lifecycle Management

- **On demand startup**: MCP client and server are started only when needed
- **Session isolation**: Each chat session/branch gets its own MCP client/server instance
- **Shutdown**: MCP client and server are shut down when no longer needed (e.g., when the chat branch ends)
- **Resource cleanup**: Ensure all subprocesses are terminated and resources released
- **Timeouts**: Implement idle timeouts to auto-shutdown if inactive

---

## 6. Error Handling & Monitoring

- **Startup errors**: If MCP server fails to start, return error to chat system
- **Tool call errors**: Return clear error messages for failed tool calls
- **Token expiry**: Detect and report token expiry, allow for token refresh if needed
- **Logging**: Log only non-sensitive events (startup, shutdown, errors)
- **Health checks**: Optionally expose a `/health` endpoint

---

## 7. Integration with Chat System

- **Trigger**: Chat system starts MCP client when user enters relevant chat branch
- **Communication**: Chat system calls MCP client HTTP API to list tools and call tools
- **Shutdown**: Chat system calls `/shutdown` when done, or MCP client auto-shuts down after timeout
- **No JWT in LLM**: All JWT/token handling is backend-only

---

## 8. Implementation Steps

1. **Project setup**
   - Create a new Python module for the MCP client
   - Add dependencies: `mcp`, `fastapi` (or `flask`), `httpx`, `subprocess`, etc.
2. **Subprocess management**
   - Implement logic to start/stop `mcp_server.py` as a subprocess
   - Pipe STDIO for communication
3. **MCP protocol integration**
   - Use `mcp.client.stdio` to communicate with the server
   - Implement tool listing and tool call logic
4. **HTTP API**
   - Use FastAPI/Flask to expose endpoints (`/tools`, `/call-tool`, `/shutdown`, `/health`)
5. **JWT/token handling**
   - Accept JWT as a parameter at startup
   - Inject JWT into tool calls as needed
6. **Lifecycle & error management**
   - Handle startup/shutdown, timeouts, and errors robustly
7. **Testing**
   - Write unit and integration tests for all endpoints and flows
   - Test with real chat system triggers
8. **Documentation**
   - Document API, usage, and integration steps for chat system developers

---

## 9. Example Usage Flow

1. User enters chat branch → Chat system starts MCP client with JWT
2. Chat system calls `GET /tools` to discover available tools
3. Chat system calls `POST /call-tool` to invoke tools as needed
4. Chat system receives results, passes to LLM for response
5. When done, chat system calls `POST /shutdown` (or client auto-shuts down)

---

## 10. Future Extensions

- Support for multiple concurrent sessions (pooling)
- Support for HTTP-based MCP server (if/when available)
- Token refresh endpoint
- Metrics and advanced monitoring

---

## 11. References

- [Builder.io: How to Build Your Own MCP Server](https://www.builder.io/blog/mcp-server)
- [Anthropic Docs: Tool Use with Claude](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview)
- Your own `test_mcp_tools.py` for subprocess and protocol examples 