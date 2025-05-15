# Insight Digger MCP - Integration Guide for AI Chat Systems

## 1. Overview

The Insight Digger MCP (Model-Controlled Pliant) system is designed to perform complex data analysis, generate insights, and create dashboards based on user questions. It interacts with a backend data API to fetch source information and data. This guide details how an AI/LLM, orchestrated by a chat system, can interact with the Insight Digger MCP solution.

**High-Level Architecture:**

```
+-------------+     HTTP     +-----------------------+     MCP     +-------------------+     HTTP      +-------------------+
| Chat System | <----------> | MCP Client (Flask API)| <---------> | MCP Server (Tools)| <---------> | Backend Data API  |
| (with LLM)  |              | (mcp_client/server.py)|             | (mcp_server.py)   |             | (Your Platform API) |
+-------------+              +-----------------------+             +-------------------+             +-------------------+
                                      |
                                      +--- Manages MCP Protocol & Subprocess (mcp_client/manager.py)
```

*   **Chat System:** The user-facing interface, which uses an LLM to understand user requests and drive the analytical workflow.
*   **MCP Client (Flask API):** A Python Flask application (`mcp_client/server.py`) that exposes a simple HTTP API. The chat system's backend interacts with this API. It handles:
    *   Authentication setup (`apiUrl`, `jwtToken`) for the Backend Data API.
    *   Exposing available MCP tools to the LLM.
    *   Forwarding LLM tool calls to the MCP Server.
    *   Intelligent client-side caching of parameters and tool results to simplify multi-step operations for the LLM.
*   **MCP Server (Tools):** A Python script (`mcp_server.py`) that defines a set of analytical tools (e.g., listing data sources, generating analysis configurations, creating dashboards). These tools make HTTP calls to the Backend Data API.
*   **Backend Data API:** Your existing platform's API that provides access to data sources, metadata, and dashboarding capabilities.

## 2. MCP Client API (`mcp_client/server.py`)

The chat system's backend will primarily interact with these HTTP endpoints provided by `mcp_client/server.py`.

### 2.1. `POST /init`

*   **Purpose:** Initializes the MCP client session and securely provides the necessary credentials for the Backend Data API. This step **must** be performed by the chat system's backend *before* any LLM interaction begins.
*   **Request JSON Payload:**
    ```json
    {
      "apiUrl": "YOUR_BACKEND_API_URL",
      "jwtToken": "YOUR_JWT_TOKEN"
    }
    ```
*   **Response JSON:**
    ```json
    {
      "status": "ok",
      "port": 12345 // The port the MCP Client is running on
    }
    ```
*   **Security Critical:**
    *   `apiUrl` and `jwtToken` are sensitive credentials for your Backend Data API.
    *   The chat system must obtain these securely (e.g., from its own configuration or a secure vault).
    *   **These credentials should NEVER be exposed to, requested from, or handled by the LLM.** The MCP Client stores them in its session and injects them into calls to the MCP Server tools as needed.

### 2.2. `GET /tools`

*   **Purpose:** Lists all MCP tools available for the LLM to use, along with their descriptions and input schemas.
*   **Request:** No payload needed.
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
*   **Note:** The schemas provided by this endpoint will automatically filter out sensitive parameters like `apiUrl` and `jwtToken`. The LLM will not see these as required inputs for the tools.

### 2.3. `POST /call-tool`

*   **Purpose:** Executes a specific MCP tool. This is the primary endpoint the LLM will instruct the chat system to call.
*   **Request JSON Payload:**
    ```json
    {
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

*   **Purpose:** Gracefully shuts down the MCP Client and the underlying MCP Server subprocess.
*   **Request:** No payload needed.
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
    *   Before any tool is called via `/call-tool`, the client first attempts to inject missing parameters (see below).
    *   Then, *all parameters* that are about to be sent to the tool (whether originally from the LLM or injected by the client) are automatically cached in the client's session memory. The parameter name is used as the cache key.
    *   This means if the LLM provides `question: "What is X?"` to one tool, this `question` is cached.

*   **Automatic Output Caching:**
    *   When an MCP Server tool successfully completes, all key-value pairs in its JSON response (except for a top-level `status` field, if present) are automatically cached in the client's session memory. The key from the response is used as the cache key.
    *   Example: If `prepare_analysis_configuration` returns `{"sourceStructure": {...}, "markdownConfig": "..."}`, both `sourceStructure` and `markdownConfig` are cached.

*   **Automatic Parameter Injection:**
    *   When the LLM instructs a call to a tool via `/call-tool`:
        1.  `apiUrl` and `jwtToken` (from `/init`) are automatically injected if not explicitly (and incorrectly) sent by the LLM.
        2.  For all other parameters defined in the target tool's input schema: If the LLM does *not* provide a value for a parameter, but a value for a key with the *same name* exists in the client's session cache (from a previous input or output), the client will automatically inject that cached value.
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

### Phase 1: Initialization (Chat System Backend - No LLM Involved)

1.  **Secure Credentials:** The chat system backend obtains `API_URL` and `JWT_TOKEN` for the Backend Data API from its secure configuration.
2.  **Start MCP Client Subprocess:** The chat system backend executes the command to start the `mcp_client` process (e.g., `python -u -m mcp_client`). It's crucial to start it with unbuffered output (`-u`) if parsing stdout in real-time.
3.  **Capture Port from Stdout:** The chat system backend **must** monitor the standard output of the `mcp_client` subprocess. The `mcp_client` will print a line indicating the port it has started on, typically formatted like:
    `[MCP CLIENT] Flask server thread starting on port <PORT_NUMBER>`
    The chat system needs to parse this line to extract the `<PORT_NUMBER>`.
4.  **Construct Base URL:** Once the port is captured, the base URL for API calls will be `http://127.0.0.1:<PORT_NUMBER>`.
5.  **Call `/init`:** The chat system backend makes a `POST` request to `<BASE_URL>/init` with the JSON payload:
    ```json
    {"apiUrl": "API_URL_VALUE", "jwtToken": "JWT_TOKEN_VALUE"}
    ```
6.  **Health Check (Recommended):** After `/init`, it's good practice to call `GET <BASE_URL>/health` to confirm the MCP Client is fully responsive and initialized before proceeding to LLM interactions.

### Phase 2: LLM-Driven Analysis (Chat System orchestrates LLM via `/tools` and `/call-tool`)

1.  **Tool Presentation:**
    *   Chat System: Calls `GET /tools` on the MCP Client.
    *   Chat System: Provides the list of tools (name, description, input schema) to the LLM as part of its system prompt or available functions.

2.  **Example User-Guided/Step-by-Step Flow:**
    *   **User:** "I want to analyze my sales data to see what affects performance."
    *   **LLM Task:** Identify the correct data source.
        *   LLM instructs Chat System to call: `POST /call-tool` with `{"tool": "list_sources", "params": {"search": "sales data"}}`
    *   **Chat System:** Receives list of sources (e.g., `[{"id": "src123", "title": "Q4 Sales Data", ...}]`).
    *   **LLM Task:** Present options to user if multiple, or confirm if one. User selects/confirms. `sourceId` is now "src123". (This `sourceId` is now cached by the client as it was an output of `list_sources`).
    *   **(Optional) LLM Task:** If user asks for more details or LLM needs context for `columnDescriptions`.
        *   LLM instructs Chat System to call: `POST /call-tool` with `{"tool": "get_source_structure", "params": {"sourceId": "src123"}}`
        *   Chat System: Gets detailed structure. LLM can use this to discuss columns with user. (The output `sourceStructure` is cached by the client).
    *   **User:** "My question is: What are the key drivers for high sales in Q4?" (`question` is now known).
    *   **LLM Task:** Prepare the analysis.
        *   LLM instructs Chat System to call: `POST /call-tool` with `{"tool": "prepare_analysis_configuration", "params": {"sourceId": "src123", "question": "What are the key drivers for high sales in Q4?"}}`
        *   (Note: `sourceId` was an output of `list_sources`, so it's in client cache. If LLM omits `sourceId` here, client *should* inject it. `question` is new input, client will cache it).
    *   **Chat System:** Receives `{"markdownConfig": "...", "sourceStructure": {...}, ...}`.
    *   **LLM Task:** Review `markdownConfig`. (Optional: present to user for review/modification).
        *   Let's assume LLM/user modifies the `markdownConfig` slightly to `modified_markdown_config_string`.
    *   **LLM Task:** Execute the analysis.
        *   LLM instructs Chat System to call: `POST /call-tool` with `{"tool": "execute_analysis_from_config", "params": {"markdownConfig": "modified_markdown_config_string"}}`
        *   (Client will inject cached `sourceStructure`, `strategy`, and `question` from the `prepare_analysis_configuration` step).
    *   **Chat System:** Receives `{"summary": "...", "dashboardUrl": "...", ...}`.
    *   **LLM Task:** Present the summary and dashboard URL to the user.

3.  **Example Fast Track Flow:**
    *   **User:** "For source 'src123', tell me what drives high sales in Q4."
    *   **LLM Task:** Directly analyze.
        *   LLM instructs Chat System to call: `POST /call-tool` with `{"tool": "analyze_source_question", "params": {"sourceId": "src123", "question": "What drives high sales in Q4?"}}`
    *   **Chat System:** Receives `{"summary": "...", "dashboardUrl": "...", ...}`.
    *   **LLM Task:** Present summary and dashboard URL.

### Phase 3: Shutdown (Chat System Backend)

1.  When the user session with Insight Digger ends, or the chat system is shutting down, it should call `POST /shutdown` on the MCP Client to release resources.

## 5. Key Considerations for LLM Prompting

*   **Sensitive Data:** Explicitly instruct the LLM **NOT** to ask for, handle, or attempt to use `