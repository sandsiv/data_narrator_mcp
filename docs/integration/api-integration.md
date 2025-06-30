# Insight Digger MCP - Integration Guide for AI Chat Systems

## 1. Overview

The Insight Digger MCP (Model-Controlled Pliant) system is designed to perform complex data analysis, generate insights, and create dashboards based on user questions. It interacts with a backend data API to fetch source information and data. This guide details how an AI/LLM, orchestrated by a chat system, can interact with the Insight Digger MCP solution, which runs as a persistent service.

**High-Level Architecture:**

```
+-------------+     HTTP     +---------------------------+     MCP     +-------------------+     HTTP      +-------------------+
| Chat System | <----------> | MCP Client (Flask API)    | <---------> | MCP Server (Tools)| <---------> | Backend Data API  |
| (with LLM)  |              | (mcp_client/server.py)    |             | (mcp_server.py)   |             | (Your Platform API) |
|             |              | (Persistent Service,      |             | (Per-Session      |             |                   |
|             |              |  handles multiple sessions)|             |  Subprocess)      |             |                   |
+-------------+              +---------------------------+             +-------------------+             +-------------------+
                                      |
                                      +--- Manages MCP Protocol & Per-Session Subprocesses (mcp_client/manager.py)
```

*   **Chat System:** The user-facing interface, which uses an LLM to understand user requests and drive the analytical workflow.
*   **MCP Client (Flask API):** A Python Flask application (`mcp_client/server.py`) that runs as a **persistent service** on a **fixed port**. It exposes a simple HTTP API that the chat system's backend interacts with. It handles:
    *   Managing multiple concurrent user sessions, each identified by a unique `session_id`.
    *   Authentication setup (`apiUrl`, `jwtToken`) for the Backend Data API, performed **per session** via the `/init` endpoint.
    *   Exposing available MCP tools to the LLM (on a per-session basis).
    *   Forwarding LLM tool calls to the appropriate MCP Server subprocess (one per session).
    *   Intelligent **per-session** client-side caching of parameters and tool results to simplify multi-step operations for the LLM.
*   **MCP Server (Tools):** A Python script (`mcp_server.py`) that defines a set of analytical tools. An instance of this server is run as a subprocess **for each active session** by the MCP Client. These tools make HTTP calls to the Backend Data API.
*   **Backend Data API:** Your existing platform's API that provides access to data sources, metadata, and dashboarding capabilities.

## 2. MCP Client API (`mcp_client/server.py`)

The chat system's backend will primarily interact with these HTTP endpoints provided by `mcp_client/server.py`. **All endpoints (except `/health`) require a `session_id` in their JSON payload to identify the user session.**

### 2.1. `POST /init`

*   **Purpose:** Initializes an MCP client **session** for a specific user interaction and securely provides the necessary credentials for the Backend Data API for that session. This step **must** be performed by the chat system's backend *before* any LLM interaction for that session begins.
*   **Request JSON Payload:**
    ```json
    {
      "session_id": "UNIQUE_USER_SESSION_IDENTIFIER",
      "apiUrl": "YOUR_BACKEND_API_URL",
      "jwtToken": "YOUR_JWT_TOKEN"
    }
    ```
*   **Response JSON:**
    ```json
    {
      "status": "ok"
    }
    ```
*   **Security Critical:**
    *   `apiUrl` and `jwtToken` are sensitive credentials for your Backend Data API.
    *   The chat system must obtain these securely (e.g., from its own configuration or a secure vault) for each user session.
    *   **These credentials should NEVER be exposed to, requested from, or handled by the LLM.** The MCP Client stores them in its memory associated with the provided `session_id` and injects them into calls to the MCP Server tools as needed for that session.

### 2.2. `POST /tools` (Note: Method changed from GET to POST)

*   **Purpose:** Lists all MCP tools available for the LLM to use for a given **session**, along with their descriptions and input schemas.
*   **Request JSON Payload:**
    ```json
    {
      "session_id": "UNIQUE_USER_SESSION_IDENTIFIER"
    }
    ```
*   **Response JSON:** An array of tool objects. Example structure for one tool:
    ```json
    {
      "tools": [
        {
          "name": "list_sources",
          "description": "List available data sources...",
          "inputSchema": {
            "type": "object",
            "properties": {
              "search": {"type": "string", "description": "Search term..."},
              "page": {"type": "integer"},
              "limit": {"type": "integer"}
            },
            "required": []
          }
        }
        // ... other tools
      ]
    }
    ```
    The LLM should provide the `tool` name and the `params` dictionary based on the tool's function and schema. **The LLM should NOT include `apiUrl` or `jwtToken` in `params`.**
*   **Response JSON:** The JSON result directly from the executed MCP Server tool. Structure varies by tool.

### 2.3. `POST /call-tool`

*   **Purpose:** Executes a specific MCP tool. This is the primary endpoint the LLM will instruct the chat system to call.
*   **Request JSON Payload:**
    ```json
    {
      "session_id": "UNIQUE_USER_SESSION_IDENTIFIER",
      "tool": "tool_name_from_get_tools_list",
      "params": {
        // Parameters specific to the tool, as defined in its inputSchema
        // e.g., for list_sources: "search": "my data"
      }
    }
    ```
    The LLM should provide the `tool` name and the `params` dictionary based on the tool's function and schema. **The LLM should NOT include `apiUrl` or `jwtToken` in `params`.**
*   **Response JSON:** The JSON result directly from the executed MCP Server tool. Structure varies by tool.

### 2.4. `POST /shutdown`

*   **Purpose:** Gracefully shuts down a specific MCP client **session** and its underlying MCP Server subprocess. This releases resources associated with that `session_id`.
*   **Request JSON Payload:**
    ```json
    {
      "session_id": "UNIQUE_USER_SESSION_IDENTIFIER"
    }
    ```
*   **Response JSON:**
    ```json
    {
      "status": "ok"
    }
    ```

### 2.5. `GET /health`

*   **Purpose:** A simple health check endpoint for the MCP Client.
*   **Request:** No payload needed.
*   **Response JSON:**
    ```json
    {
      "status": "ok"
    }
    ```

### 2.6. Client-Side Caching and Parameter Injection

The MCP Client (`mcp_client/server.py`) implements an intelligent caching and injection mechanism to simplify multi-step analytical workflows for the LLM.

*   **Automatic Input Caching:**
    *   Before any tool is called via `/call-tool` for a specific `session_id`, the client first attempts to inject missing parameters (see below) from that session's cache.
    *   Then, *all parameters* that are about to be sent to the tool (whether originally from the LLM or injected by the client for that session) are automatically cached in the client's memory associated with that `session_id`. The parameter name is used as the cache key.
    *   This means if the LLM provides `question: "What is X?"` to one tool for a session, this `question` is cached for that session.

*   **Automatic Output Caching:**
    *   When an MCP Server tool successfully completes for a session, all key-value pairs in its JSON response (except for a top-level `status` field, if present) are automatically cached in the client's memory associated with that `session_id`. The key from the response is used as the cache key.
    *   Example: If `prepare_analysis_configuration` for a session returns `{"sourceStructure": {...}, "markdownConfig": "..."}`, both `sourceStructure` and `markdownConfig` are cached for that session.

*   **Automatic Parameter Injection (per session):**
    *   When the LLM instructs a call to a tool via `/call-tool` (which will include a `session_id` from the chat system):
        1.  `apiUrl` and `jwtToken` (from the session's `/init` call) are automatically injected if not explicitly (and incorrectly) sent by the LLM.
        2.  For all other parameters defined in the target tool's input schema: If the LLM does *not* provide a value for a parameter, but a value for a key with the *same name* exists in the client's cache for that `session_id` (from a previous input or output in the same session), the client will automatically inject that cached value.
        3.  **LLM-provided parameters always take precedence over cached values for a given call.**

*   **Implications & Guidance for LLM:**
    *   The LLM does not need to explicitly manage or pass around common intermediate data like `sourceId`, `question`, `sourceStructure`, `strategy`, or `markdownConfig` between related tool calls.
    *   For a sequence like `prepare_analysis_configuration` followed by `execute_analysis_from_config`, the LLM typically only needs to provide `sourceId` and `question` to the first tool, and then the potentially modified `markdownConfig` to the second. The client handles the rest.
    *   This "latest write wins" for cached values (both inputs and outputs).

## 3. MCP Server Tools (`mcp_server.py`)

These are the primary tools the LLM will interact with, via the MCP Client's `/call-tool` endpoint. The client handles `apiUrl` and `jwtToken` injection.

*   **`list_sources`**
    *   **Description:** List available data sources. Use this as the first step to find the `sourceId`.
    *   **LLM Inputs:** `search` (optional string), `page` (optional int), `limit` (optional int).
    *   **Output:** `{"count": N, "data": [{"id": "...", "title": "...", "type": "...", "updated": "...", "numberOfColumns": N}, ...]}`. Provides a simplified list for discovery.

*   **`get_source_structure`**
    *   **Description:** Get detailed structure (columns, data types) for a specific `sourceId`. Useful for understanding data attributes before formulating a complex question or providing column descriptions.
    *   **LLM Inputs:** `sourceId` (string).
    *   **Output:** The detailed source schema/structure object from the backend.

*   **`prepare_analysis_configuration`** (Step 1 of Step-by-Step Analysis)
    *   **Description:** Analyzes source & question to generate a dashboard configuration for review. The MCP client will cache outputs (`markdownConfig`, `sourceStructure`, `columnAnalysis`, `strategy`) and the input `question` for potential use in subsequent steps.
    *   **LLM Inputs:** `sourceId` (string), `question` (string), `columnDescriptions` (optional dict).
    *   **Key Outputs for LLM:** `markdownConfig` (string). (Other outputs like `sourceStructure`, `columnAnalysis`, `strategy` are returned and cached by the client).

*   **`execute_analysis_from_config`** (Step 2 of Step-by-Step Analysis)
    *   **Description:** Executes analysis. Provide `markdownConfig` (potentially modified after Step 1). The client automatically tries to use cached `sourceStructure`, `strategy`, and original `question` from Step 1 if not explicitly provided.
    *   **LLM Inputs:** `markdownConfig` (string).
    *   **Key Outputs for LLM:** `summary` (string), `dashboardUrl` (string), and an `intermediate` results dictionary.

*   **`analyze_source_question`** (Fast Track)
    *   **Description:** FAST TRACK: Run the full analysis workflow in one shot (source + question generating dashboard and insights). Use for straightforward analyses where intermediate review of process is not needed.
    *   **LLM Inputs:** `sourceId` (string), `question` (string), `columnDescriptions` (optional dict).
    *   **Key Outputs for LLM:** `summary` (string), `dashboardUrl` (string), and an `intermediate` results dictionary.

## 4. Recommended Integration Workflow

The MCP Client (`mcp_client/server.py`) now runs as a persistent service.

### Phase 1: MCP Client Service Startup (One-Time Setup / DevOps)

1.  **Start MCP Client Service:**
    *   The `mcp_client/server.py` script is started as a long-running service. This is typically done once during your application deployment.
    *   It must be configured to listen on a **fixed port** by setting the `MCP_CLIENT_PORT` environment variable.
    *   Example command: `MCP_CLIENT_PORT=5000 python -u -m mcp_client.server`
    *   For production, use a process manager like `systemd`, `supervisor`, Docker, or similar to ensure it stays running.
2.  **Chat System Configuration:**
    *   The chat system backend is configured with the `BASE_URL` of the MCP Client service (e.g., `http://127.0.0.1:5000` if running on the same host, or the appropriate network address if running elsewhere).
3.  **Health Check (Recommended):**
    *   After starting the service, it's good practice for the chat system (or an operator) to call `GET <BASE_URL>/health` to confirm the MCP Client service is responsive before it starts handling user sessions.

### Phase 1.5: Per-User Session Initialization (Chat System Backend - For Each New User Chat)

For each new user interaction or chat session that requires Insight Digger capabilities:

1.  **Secure Credentials & Session ID:**
    *   The chat system backend obtains `API_URL` and `JWT_TOKEN` for the Backend Data API (these might be user-specific or system-wide).
    *   The chat system backend generates a **unique `session_id`** string to identify this specific user's interaction with the MCP. This `session_id` must be managed by the chat system and used for all subsequent calls for this user session.
2.  **Call `/init` for the Session:**
    *   The chat system backend makes a `POST` request to `<BASE_URL>/init` with the JSON payload:
        ```json
        {
          "session_id": "THE_GENERATED_UNIQUE_SESSION_ID",
          "apiUrl": "API_URL_VALUE",
          "jwtToken": "JWT_TOKEN_VALUE"
        }
        ```
    *   This initializes a dedicated session within the MCP Client, including starting an `mcp_server.py` subprocess for this session.
3.  **Confirmation:** Check the response from `/init` for `{"status": "ok"}`.

### Phase 2: LLM-Driven Analysis (Chat System orchestrates LLM via `/tools` and `/call-tool` for a given `session_id`)

Once a session is initialized:

1.  **Tool Presentation:**
    *   Chat System: Calls `POST <BASE_URL>/tools` on the MCP Client, including the `session_id` in the payload:
        ```json
        {"session_id": "THE_CURRENT_SESSION_ID"}
        ```
    *   Chat System: Provides the list of tools (name, description, input schema) to the LLM as part of its system prompt or available functions.

2.  **Example User-Guided/Step-by-Step Flow (all calls include `session_id`):**
    *   **User:** "I want to analyze my sales data to see what affects performance."
    *   **LLM Task:** Identify the correct data source.
        *   LLM instructs Chat System to call: `POST <BASE_URL>/call-tool` with:
            ```json
            {
              "session_id": "THE_CURRENT_SESSION_ID",
              "tool": "list_sources",
              "params": {"search": "sales data"}
            }
            ```
    *   **Chat System:** Receives list of sources. (This `sourceId` and other outputs are cached by the client *for this session*).
    *   **(Optional) LLM Task:** If user asks for more details.
        *   LLM instructs Chat System to call: `POST <BASE_URL>/call-tool` with:
            ```json
            {
              "session_id": "THE_CURRENT_SESSION_ID",
              "tool": "get_source_structure",
              "params": {"sourceId": "src123"}
            }
            ```
    *   **User:** "My question is: What are the key drivers for high sales in Q4?"
    *   **LLM Task:** Prepare the analysis.
        *   LLM instructs Chat System to call: `POST <BASE_URL>/call-tool` with:
            ```json
            {
              "session_id": "THE_CURRENT_SESSION_ID",
              "tool": "prepare_analysis_configuration",
              "params": {"sourceId": "src123", "question": "What are the key drivers for high sales in Q4?"}
            }
            ```
    *   **Chat System:** Receives `{"markdownConfig": "...", ...}`.
    *   **LLM Task:** Review `markdownConfig`.
    *   **LLM Task:** Execute the analysis.
        *   LLM instructs Chat System to call: `POST <BASE_URL>/call-tool` with:
            ```json
            {
              "session_id": "THE_CURRENT_SESSION_ID",
              "tool": "execute_analysis_from_config",
              "params": {"markdownConfig": "modified_markdown_config_string"}
            }
            ```
    *   **Chat System:** Receives `{"summary": "...", "dashboardUrl": "...", ...}`.
    *   **LLM Task:** Present the summary and dashboard URL to the user.

3.  **Example Fast Track Flow (call includes `session_id`):**
    *   **User:** "For source 'src123', tell me what drives high sales in Q4."
    *   **LLM Task:** Directly analyze.
        *   LLM instructs Chat System to call: `POST <BASE_URL>/call-tool` with:
            ```json
            {
              "session_id": "THE_CURRENT_SESSION_ID",
              "tool": "analyze_source_question",
              "params": {"sourceId": "src123", "question": "What drives high sales in Q4?"}
            }
            ```
    *   **Chat System:** Receives `{"summary": "...", "dashboardUrl": "...", ...}`.
    *   **LLM Task:** Present summary and dashboard URL.

### Phase 3: Session Shutdown (Chat System Backend)

1.  When the user session with Insight Digger ends (e.g., user logs out, chat session times out, or explicitly finishes the analysis task), the chat system backend **must** call `POST <BASE_URL>/shutdown` on the MCP Client, including the `session_id` to release resources for that specific session:
    ```json
    {
      "session_id": "THE_CURRENT_SESSION_ID"
    }
    ```
    This stops the `mcp_server.py` subprocess for that session and clears its cached data. The MCP Client service itself continues running to serve other sessions.

## 5. Key Considerations for LLM Prompting

*   **Sensitive Data:** Explicitly instruct the LLM **NOT** to ask for, handle, or attempt to use `apiUrl`, `jwtToken`.
*   **`session_id` Management:** The LLM should **not** be concerned with `session_id`. The chat system backend is responsible for generating, managing, and including the correct `session_id` in all API calls to the MCP Client. The LLM's tool call instructions should only specify the `tool` name and `params`.
*   **Client-Side Caching:** Remind the LLM that common parameters (like `sourceId`, `question`, `sourceStructure`, `markdownConfig`) are often cached by the client *within a session*. It doesn't need to pass them repeatedly between related tool calls for the same analysis flow unless they need to be overridden.
*   **Tool Schemas:** The LLM should rely on the tool schemas provided by `POST /tools` (for the current session) to understand required and optional parameters for each tool.