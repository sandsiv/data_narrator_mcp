"""
Standalone MCP Server for Insight Digger
---------------------------------------
This module exposes the analytical workflow as MCP tools, using FastMCP and calling the Flask endpoints via HTTP.

MCP Tools Exposed:
- analyze_source_question: Run the full analysis workflow (one-shot).
- validate_settings: Test connection to the external API.
- list_sources: List available data sources.
- get_source_structure: Get structure/schema for a given source.
- analyze_columns: Analyze columns for a given source structure.
- generate_strategy: Generate analysis strategy for a question and column analysis.
- create_configuration: Create dashboard configuration from question, column analysis, and strategy.
- generate_config: One-shot: question + source structure → dashboard config (markdown).
- create_dashboard: Create dashboard from config, source structure, and API settings.
- get_charts_data: Fetch data for multiple charts.
- analyze_charts: Analyze chart data for insights.
- generate_summary: Generate a summary from insights and strategy.

How to run:
    mcp run mcp_server.py

Do NOT run this file directly with 'python mcp_server.py'.
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP
import asyncio
import logging

# Setup file logging
logging.basicConfig(
    filename="/tmp/mcp_server.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True
)
logging.warning("[STARTUP] mcp_server.py: script started")

# Create MCP server instance
mcp = FastMCP("Insight Digger MCP")
logging.warning("[STARTUP] FastMCP instance created")

# Helper: Get API base URL for the Flask server
API_BASE_URL = os.getenv("INSIGHT_DIGGER_API_URL", "https://internal.sandsiv.com/data-narrator/api")

# Set default timeouts
DEFAULT_TIMEOUT = httpx.Timeout(60.0)
LONG_TIMEOUT = httpx.Timeout(300.0)

# Helper: Async HTTP POST
async def post(endpoint, json=None, timeout=DEFAULT_TIMEOUT):
    url = f"{API_BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=json)
        resp.raise_for_status()
        return resp.json()

# Helper: Async HTTP GET
async def get(endpoint, headers=None, params=None, timeout=DEFAULT_TIMEOUT):
    url = f"{API_BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

# --- MCP Tools ---
@mcp.tool(description="Validate API settings by testing the connection to the external data API. Args: apiUrl (str), jwtToken (str). Returns: {{'status': 'success'|'error', 'error': str (if status == 'error')}}.")
async def validate_settings(apiUrl: str, jwtToken: str) -> dict:
    """
    Test the connection to the external data API using the provided URL and JWT token.

    Args:
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.

    Returns:
        dict: {
            "status": "success" | "error",
            "error": str (if status == "error")
        }

    Usage:
        Call this tool before other operations to ensure the API credentials are valid.
    """
    try:
        result = await post("/settings/validate", json={"apiUrl": apiUrl, "jwtToken": jwtToken})
        return result
    except Exception as e:
        logging.error(f"validate_settings error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: validate_settings")

@mcp.tool(description="List available data sources. This is typically the FIRST interactive step in data analysis. The user will select a source from this list, and its 'id' (returned in the 'data' array) will be used as 'sourceId' in other tools like 'prepare_analysis_configuration' or 'analyze_source_question'. Call this to allow the user to see and choose a data source, but ask user to provie a source name to search first. Use name provided by the user as 'search' parameter to filter the list. Avoid using this tool without 'search' value. Consider limit and page parameters in case of many sources with names that fit the search. Returns: {{'count': int, 'data': [{'id': str, 'title': str, 'type': str, 'updated': str, 'numberOfColumns': int}]}}.")
async def list_sources(apiUrl: str, jwtToken: str, search: str = "", page: int = 1, limit: int = 10) -> dict:
    """
    List available data sources from the external API, allowing the user to choose one for analysis.
    (Detailed comments here are for human developers; LLM guidance is in the decorator description.)
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    params = {"search": search, "page": page, "limit": limit}
    try:
        full_result = await get("/sources", headers=headers, params=params)
        
        # Transform the result to a simpler structure for the LLM
        simplified_sources = []
        if isinstance(full_result.get("data"), list):
            for source_data in full_result["data"]:
                num_columns = 0
                if isinstance(source_data.get("attributes"), list):
                    num_columns = len(source_data["attributes"])
                
                simplified_sources.append({
                    "id": source_data.get("id"),
                    "title": source_data.get("title"),
                    "type": source_data.get("type"),
                    "updated": source_data.get("updated"), # or maxUpdated, choose one
                    "numberOfColumns": num_columns
                })
        
        return {
            "count": full_result.get("count", 0),
            "data": simplified_sources # Return the list of simplified source objects
            # Add other pagination fields if necessary, e.g., from full_result if they exist
        }
    except Exception as e:
        logging.error(f"list_sources error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: list_sources")

@mcp.tool(description="Fetches and analyzes the structure of a given data source. This is a key step after selecting a source. It returns a detailed analysis of the columns, which should be presented to the user to help them formulate a specific analytical question. The full source structure and the analysis are cached for subsequent steps.")
async def analyze_source_structure(apiUrl: str, jwtToken: str, sourceId: str) -> dict:
    """
    Retrieves the structure for a source, analyzes its columns, and returns the analysis.
    This tool combines getting the source structure and analyzing its columns into a single step.
    It caches both the full source structure and the column analysis for use in subsequent tools.

    Args:
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.
        sourceId (str): The ID of the data source to analyze.

    Returns:
        dict: A success message and the column analysis, with full data in an 'intermediate' field for caching.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    try:
        # Step 1: Get source structure
        logging.info(f"analyze_source_structure: getting structure for sourceId {sourceId}")
        full_structure = await get(f"/source/{sourceId}/structure", headers=headers)
        
        # Step 2: Analyze columns using the retrieved structure
        logging.info(f"analyze_source_structure: analyzing columns for sourceId {sourceId}")
        payload = {"sourceStructure": full_structure}
        # Assuming '/analyze-columns' returns a structure like {"status": "success", "columnAnalysis": [...]}
        analysis_result = await post("/analyze-columns", json=payload)

        # Ensure the analysis was successful and contains the expected data
        if not (analysis_result.get("status") == "success" and "columnAnalysis" in analysis_result):
            logging.error(f"analyze_source_structure: column analysis failed or returned unexpected format: {analysis_result}")
            # Return the error from the analysis step
            return analysis_result or {"status": "error", "error": "Column analysis failed."}

        column_analysis = analysis_result["columnAnalysis"]

        # Step 3: Prepare the response for the LLM
        return {
            "status": "success",
            "message": "Successfully retrieved and analyzed the source structure.",
            "columnAnalysis": column_analysis, # This goes to the LLM
            "intermediate": {
                "sourceStructure": full_structure,
                "columnAnalysis": column_analysis # Also cache it for subsequent steps
            }
        }

    except Exception as e:
        logging.error(f"analyze_source_structure error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: analyze_source_structure")

@mcp.tool(description="Generate analysis strategy for a question and column analysis. This is a granular step in the analysis workflow.")
async def generate_strategy(question: str, columnAnalysis: list) -> dict:
    """
    Generate an analysis strategy for a given question and column analysis.

    Args:
        question (str): The analytical question to answer.
        columnAnalysis (list): Results from column analysis.

    Returns:
        dict: Strategy for analysis or error status.
    """
    payload = {"question": question, "columnAnalysis": columnAnalysis}
    try:
        result = await post("/generate-strategy", json=payload)
        return result
    except Exception as e:
        logging.error(f"generate_strategy error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: generate_strategy")

@mcp.tool(description="Create dashboard configuration from question, column analysis, and strategy. This is a granular step in the analysis workflow.")
async def create_configuration(question: str, columnAnalysis: list, strategy: dict) -> dict:
    """
    Create a dashboard configuration from the question, column analysis, and strategy.

    Args:
        question (str): The analytical question to answer.
        columnAnalysis (list): Results from column analysis.
        strategy (dict): Analysis strategy.

    Returns:
        dict: Dashboard configuration or error status.
    """
    payload = {"question": question, "columnAnalysis": columnAnalysis, "strategy": strategy}
    try:
        result = await post("/create-configuration", json=payload)
        # Remap 'configuration' to 'markdownConfig' for workflow consistency
        if result.get("status") == "success" and "configuration" in result:
            result["markdownConfig"] = result.pop("configuration")
        return result
    except Exception as e:
        logging.error(f"create_configuration error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: create_configuration")

@mcp.tool(description="Generate dashboard config (markdown) from question and source structure. Returns: dict (markdown configuration).")
async def generate_config(question: str, sourceStructure: dict, apiUrl: str = None, jwtToken: str = None) -> dict:
    """
    Generate a dashboard configuration (in markdown) from a question and source structure.

    Args:
        question (str): The analytical question to answer.
        sourceStructure (dict): The structure/schema of the data source.
        apiUrl (str, optional): The base URL of the external API.
        jwtToken (str, optional): JWT token for authentication.

    Returns:
        dict: Markdown configuration or error status.
    """
    payload = {"question": question, "sourceStructure": sourceStructure}
    if apiUrl and jwtToken:
        payload["apiSettings"] = {"apiUrl": apiUrl, "jwtToken": jwtToken}
    try:
        result = await post("/generate-config", json=payload)
        return result
    except Exception as e:
        logging.error(f"generate_config error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: generate_config")

@mcp.tool(description="Create a dashboard from config, source structure, and API settings. This is a granular step in the analysis workflow.")
async def create_dashboard(markdownConfig: str, sourceStructure: dict, apiUrl: str, jwtToken: str) -> dict:
    """
    Create a dashboard from the provided markdown config, source structure, and API settings.

    Args:
        markdownConfig (str): Dashboard configuration in markdown format.
        sourceStructure (dict): The structure/schema of the data source.
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.

    Returns:
        dict: Dashboard URL, charts, or error status.
    """
    apiSettings = {"apiUrl": apiUrl, "jwtToken": jwtToken}
    payload = {"markdownConfig": markdownConfig, "sourceStructure": sourceStructure, "apiSettings": apiSettings}
    try:
        result = await post("/create-dashboard", json=payload)
        # Remap 'charts' to 'chartConfigs' for workflow consistency
        if result.get("status") == "success" and "charts" in result:
            result["chartConfigs"] = result.pop("charts")
        return result
    except Exception as e:
        logging.error(f"create_dashboard error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: create_dashboard")

@mcp.tool(description="Fetch data for multiple charts. This step is granular. It returns a summary of fetched charts (e.g., their names). The full data is cached for the next step and not returned to the LLM.")
async def get_charts_data(chartConfigs: list, apiUrl: str, jwtToken: str) -> dict:
    """
    Fetch data for multiple charts using the provided chart configurations and API settings.
    It returns a summary of charts for which data was fetched. The full chart data is passed
    in an 'intermediate' field to be cached by the client but not shown to the LLM.

    Args:
        chartConfigs (list): List of chart configuration dicts.
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.

    Returns:
        dict: A summary for the LLM, with full data in an 'intermediate' field for caching.
    """
    apiSettings = {"apiUrl": apiUrl, "jwtToken": jwtToken}
    payload = {"chartConfigs": chartConfigs, "apiSettings": apiSettings}
    try:
        result = await post("/charts/data", json=payload)

        if result.get("status") == "success" and "chartData" in result:
            chart_names = []
            chart_data = result.get("chartData", {})
            for chart_id, chart_info in chart_data.items():
                config = chart_info.get("configuration", {})
                # Try to find a descriptive name for the chart
                chart_name = config.get("title", config.get("name", config.get("chart_type", chart_id)))
                chart_names.append(chart_name)

            return {
                "status": "success",
                "message": f"Successfully fetched data for {len(chart_names)} charts.",
                "chartsWithData": chart_names,
                "intermediate": {
                    "chartData": chart_data
                }
            }
        else:
            # Return error or unexpected response as is
            return result

    except Exception as e:
        logging.error(f"get_charts_data error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: get_charts_data")

@mcp.tool(description="""Analyzes data from all charts and returns detailed insights. This is the final analytical step. After receiving the insights, you MUST synthesize them into a final report for the user. Your report should:
1. Start with a brief summary that directly answers the user's original question.
2. Follow the previously generated analysis strategy, using insights to address each point.
3. Support findings with specific data points and note any limitations.
4. Present the full analysis in markdown format, and include the 'dashboardUrl' at the end.""")
async def analyze_charts(chartData: dict, question: str, apiUrl: str, jwtToken: str) -> dict:
    """
    Analyze chart data for insights, given a question and API settings. The returned insights are meant to be used by the LLM to generate a final summary.

    Args:
        chartData (dict): Data for the charts.
        question (str): The analytical question to answer.
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.

    Returns:
        dict: Insights or error status.
    """
    apiSettings = {"apiUrl": apiUrl, "jwtToken": jwtToken}
    payload = {"chartData": chartData, "question": question, "apiSettings": apiSettings}
    try:
        result = await post("/analyze-charts", json=payload)
        return result
    except Exception as e:
        logging.error(f"analyze_charts error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: analyze_charts")

# Print all registered tools after all definitions
print("[DEBUG] All tools registered:", list(getattr(mcp, "_tools", {}).keys()))
print("[DEBUG] MCP server ready for protocol connection.")