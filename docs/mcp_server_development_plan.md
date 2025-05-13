# MCP Server Module: Development Plan & API Documentation

## **Overview**

This module will expose your application's core analytical workflow as a set of MCP tools, allowing external MCP clients (such as AI Chart) to automate or orchestrate the entire process—from data source selection to insight generation—via a single, unified interface.

The MCP server will:
- Provide a **"one-shot" tool** for fully automated analysis (source + question → answer + dashboard).
- Expose **granular tools** for each step, enabling advanced/controlled workflows.
- Internally, each MCP tool will wrap the logic of an existing route or service in `app.py`.

---

## **Goals**

- **Seamless Orchestration:** Allow MCP clients to run the full analysis workflow with minimal user input.
- **Transparency & Control:** Support both automated and step-by-step (controlled) workflows.
- **Reusability:** Leverage existing business logic and error handling in `app.py`.
- **Statelessness:** All tools require explicit parameters (credentials, source, question, etc.) for composability and safety.
- **Extensibility:** Easy to add new tools or modify workflow steps in the future.

---

## **User Communication Logic**

- **Default (Automated) Flow:**  
  The user (via MCP client) provides the data source and analytical question. The MCP server runs all steps under the hood and returns the final answer and dashboard link.
- **Advanced (Controlled) Flow:**  
  The MCP client can call granular tools to review/modify intermediate results (e.g., column analysis, strategy) before proceeding to the next step.

---

## **MCP Tools: API Specification**

### 1. **One-Shot Tool**

#### `analyze_source_question`
- **Purpose:** Run the entire workflow (from source selection to insight generation) in one call.
- **Inputs:**
  - `apiUrl` (str): URL of the external data API.
  - `jwtToken` (str): JWT token for authentication.
  - `sourceId` (str): ID of the data source to analyze.
  - `question` (str): Analytical question to answer.
  - `columnDescriptions` (dict, optional): Optional column descriptions.
- **Outputs:**
  - `summary` (str): Final answer/insight.
  - `dashboardUrl` (str): Link to the created dashboard.
  - `intermediate` (dict, optional): (If requested) All intermediate results (column analysis, strategy, config, etc.).
- **Logic:**
  1. Get source structure (`/api/source/<source_id>/structure`)
  2. Analyze columns (`/api/analyze-columns`)
  3. Generate strategy (`/api/generate-strategy`)
  4. Create configuration (`/api/create-configuration`)
  5. Create dashboard (`/api/create-dashboard`)
  6. Get chart data (`/api/charts/data`)
  7. Analyze charts (`/api/analyze-charts`)
  8. Generate summary (`/api/generate-summary`)
  9. Return summary and dashboard URL (and optionally, all intermediate results)

---

### 2. **Granular Tools (Step-by-Step)**

Each tool below corresponds to a step in the workflow and wraps the logic of an existing route in `app.py`.

#### `validate_settings`
- **Purpose:** Test connection to the external API.
- **Inputs:** `apiUrl`, `jwtToken`
- **Output:** Success/error status.
- **Logic:** Calls `/api/settings/validate`.

#### `list_sources`
- **Purpose:** List available data sources.
- **Inputs:** `apiUrl`, `jwtToken`, `search?`, `page?`, `limit?`
- **Output:** List of sources.
- **Logic:** Calls `/api/sources`.

#### `get_source_structure`
- **Purpose:** Get structure/schema for a given source.
- **Inputs:** `apiUrl`, `jwtToken`, `sourceId`
- **Output:** Source structure.
- **Logic:** Calls `/api/source/<source_id>/structure`.

#### `analyze_columns`
- **Purpose:** Analyze columns for a given source structure.
- **Inputs:** `sourceStructure`, `columnDescriptions?`
- **Output:** Column analysis.
- **Logic:** Calls `/api/analyze-columns`.

#### `generate_strategy`
- **Purpose:** Generate analysis strategy for a question and column analysis.
- **Inputs:** `question`, `columnAnalysis`
- **Output:** Strategy.
- **Logic:** Calls `/api/generate-strategy`.

#### `create_configuration`
- **Purpose:** Create dashboard configuration from question, column analysis, and strategy.
- **Inputs:** `question`, `columnAnalysis`, `strategy`
- **Output:** Dashboard configuration.
- **Logic:** Calls `/api/create-configuration`.

#### `generate_config`
- **Purpose:** One-shot: question + source structure → dashboard config (markdown).
- **Inputs:** `question`, `sourceStructure`, `columnDescriptions?`
- **Output:** Markdown configuration.
- **Logic:** Calls `/api/generate-config`.

#### `create_dashboard`
- **Purpose:** Create dashboard from config, source structure, and API settings.
- **Inputs:** `markdownConfig`, `sourceStructure`, `apiSettings`
- **Output:** Dashboard URL, charts.
- **Logic:** Calls `/api/create-dashboard`.

#### `get_charts_data`
- **Purpose:** Fetch data for multiple charts.
- **Inputs:** `chartConfigs`, `apiSettings`
- **Output:** Chart data.
- **Logic:** Calls `/api/charts/data`.

#### `analyze_charts`
- **Purpose:** Analyze chart data for insights.
- **Inputs:** `chartData`, `question`, `apiSettings`
- **Output:** Insights.
- **Logic:** Calls `/api/analyze-charts`.

#### `generate_summary`
- **Purpose:** Generate a summary from insights and strategy.
- **Inputs:** `insights`, `question`, `strategy`, `apiSettings`
- **Output:** Summary.
- **Logic:** Calls `/api/generate-summary`.

---

## **Development Steps**

### **1. Project Setup**
- Create a new module, e.g., `mcp_server.py`.
- Add `mcp` to your dependencies:  
  `pip install "mcp[cli]"`

### **2. MCP Server Initialization**
- Import and initialize `FastMCP`:
  ```python
  from mcp.server.fastmcp import FastMCP
  mcp = FastMCP("Insight Digger MCP")
  ```

### **3. Tool Implementation**
- For each tool, define a function with the `@mcp.tool()` decorator.
- Each function should:
  - Accept all required parameters as arguments.
  - Call the corresponding service logic or endpoint (preferably directly, or via HTTP if needed).
  - Return results in the expected format.
  - Handle and report errors clearly.
- For the "one-shot" tool, orchestrate all steps, passing results from one to the next.

### **4. ASGI Integration**
- Expose the MCP server as an ASGI app using `mcp.sse_app()`.
- Mount it in your main app (e.g., at `/mcp`), so both the Flask API and MCP server are available.

### **5. Documentation & Comments**
- Document each tool with clear docstrings.
- Add comments explaining the mapping between MCP tools and existing endpoints.

### **6. Testing**
- Test each tool individually and the full "one-shot" workflow.
- Ensure error handling and edge cases are covered.

---

## **Example: One-Shot Tool Implementation (Pseudocode)**

```python
@mcp.tool()
async def analyze_source_question(
    apiUrl: str,
    jwtToken: str,
    sourceId: str,
    question: str,
    columnDescriptions: dict = None
) -> dict:
    """
    Run the full analysis workflow for a given source and question.
    Returns summary, dashboardUrl, and optionally intermediate results.
    """
    # 1. Get source structure
    # 2. Analyze columns
    # 3. Generate strategy
    # 4. Create configuration
    # 5. Create dashboard
    # 6. Get chart data
    # 7. Analyze charts
    # 8. Generate summary
    # 9. Return results
```

---

## **Appendix: Tool Summary Table**

| Tool Name                | Inputs                                    | Output/Result                        | Calls/Logic                                  |
|--------------------------|-------------------------------------------|--------------------------------------|-----------------------------------------------|
| analyze_source_question  | apiUrl, jwtToken, sourceId, question, columnDescriptions? | summary, dashboardUrl, intermediate? | Orchestrates all steps                        |
| validate_settings        | apiUrl, jwtToken                          | status                               | /api/settings/validate                        |
| list_sources             | apiUrl, jwtToken, search?, page?, limit?  | sources list                         | /api/sources                                  |
| get_source_structure     | apiUrl, jwtToken, sourceId                | source structure                     | /api/source/<source_id>/structure             |
| analyze_columns          | sourceStructure, columnDescriptions?      | column analysis                      | /api/analyze-columns                          |
| generate_strategy        | question, columnAnalysis                  | strategy                             | /api/generate-strategy                        |
| create_configuration     | question, columnAnalysis, strategy        | dashboard configuration              | /api/create-configuration                     |
| generate_config          | question, sourceStructure, columnDescriptions? | markdown config                  | /api/generate-config                          |
| create_dashboard         | markdownConfig, sourceStructure, apiSettings | dashboardUrl, charts              | /api/create-dashboard                         |
| get_charts_data          | chartConfigs, apiSettings                 | chartData                            | /api/charts/data                              |
| analyze_charts           | chartData, question, apiSettings          | insights                             | /api/analyze-charts                           |
| generate_summary         | insights, question, strategy, apiSettings | summary                              | /api/generate-summary                         |

---

## **Conclusion**

This plan provides a clear, modular, and extensible approach for exposing your application's analytical workflow as MCP tools. It supports both fully automated and step-by-step workflows, leverages your existing logic, and is designed for robust, stateless operation.

**You can use this document as a blueprint for implementation and as user-facing documentation for MCP clients.**  
Let me know if you want any adjustments or further details before starting development! 