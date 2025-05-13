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
    filename="mcp_server_debug.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True
)
logging.info("[STARTUP] mcp_server.py: script started")

# Create MCP server instance
mcp = FastMCP("Insight Digger MCP")
logging.info("[STARTUP] FastMCP instance created")

# Helper: Get API base URL for the Flask server
API_BASE_URL = os.getenv("MCP_FLASK_API_URL", "http://localhost:5000/api")

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
@mcp.tool(description="Validate API settings by testing the connection to the external data API.")
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

@mcp.tool(description="List available data sources from the external API.")
async def list_sources(apiUrl: str, jwtToken: str, search: str = "", page: int = 1, limit: int = 10) -> dict:
    """
    List available data sources from the external API.

    Args:
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.
        search (str, optional): Search term to filter sources. Defaults to "".
        page (int, optional): Page number for pagination. Defaults to 1.
        limit (int, optional): Number of sources per page. Defaults to 10.

    Returns:
        dict: List of sources and pagination info, or error status.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    params = {"search": search, "page": page, "limit": limit}
    try:
        result = await get("/sources", headers=headers, params=params)
        return result
    except Exception as e:
        logging.error(f"list_sources error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: list_sources")

@mcp.tool(description="Get the structure/schema for a given data source.")
async def get_source_structure(apiUrl: str, jwtToken: str, sourceId: str) -> dict:
    """
    Retrieve the structure/schema for a specified data source.

    Args:
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.
        sourceId (str): ID of the data source.

    Returns:
        dict: Source structure or error status.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    try:
        result = await get(f"/source/{sourceId}/structure", headers=headers)
        return result
    except Exception as e:
        logging.error(f"get_source_structure error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: get_source_structure")

@mcp.tool(description="Analyze columns for a given source structure and optional descriptions.")
async def analyze_columns(sourceStructure: dict, columnDescriptions: dict = None) -> dict:
    """
    Analyze columns for a given source structure, optionally using provided column descriptions.

    Args:
        sourceStructure (dict): The structure/schema of the data source.
        columnDescriptions (dict, optional): Optional descriptions for columns.

    Returns:
        dict: Column analysis results or error status.
    """
    payload = {"sourceStructure": sourceStructure}
    if columnDescriptions:
        payload["columnDescriptions"] = columnDescriptions
    try:
        result = await post("/analyze-columns", json=payload)
        if isinstance(result, list):
            return {"status": "success", "columnAnalysis": result}
        return result
    except Exception as e:
        logging.error(f"analyze_columns error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: analyze_columns")

@mcp.tool(description="Generate analysis strategy for a question and column analysis.")
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

@mcp.tool(description="Create dashboard configuration from question, column analysis, and strategy.")
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
        return result
    except Exception as e:
        logging.error(f"create_configuration error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: create_configuration")

@mcp.tool(description="Generate dashboard config (markdown) from question and source structure.")
async def generate_config(question: str, sourceStructure: dict, columnDescriptions: dict = None, apiSettings: dict = None) -> dict:
    """
    Generate a dashboard configuration (in markdown) from a question and source structure.

    Args:
        question (str): The analytical question to answer.
        sourceStructure (dict): The structure/schema of the data source.
        columnDescriptions (dict, optional): Optional descriptions for columns.
        apiSettings (dict, optional): API settings for authentication.

    Returns:
        dict: Markdown configuration or error status.
    """
    payload = {"question": question, "sourceStructure": sourceStructure}
    if columnDescriptions:
        payload["columnDescriptions"] = columnDescriptions
    if apiSettings:
        payload["apiSettings"] = apiSettings
    try:
        result = await post("/generate-config", json=payload)
        return result
    except Exception as e:
        logging.error(f"generate_config error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: generate_config")

@mcp.tool(description="Create a dashboard from config, source structure, and API settings.")
async def create_dashboard(markdownConfig: str, sourceStructure: dict, apiSettings: dict) -> dict:
    """
    Create a dashboard from the provided markdown config, source structure, and API settings.

    Args:
        markdownConfig (str): Dashboard configuration in markdown format.
        sourceStructure (dict): The structure/schema of the data source.
        apiSettings (dict): API settings for authentication.

    Returns:
        dict: Dashboard URL, charts, or error status.
    """
    payload = {"markdownConfig": markdownConfig, "sourceStructure": sourceStructure, "apiSettings": apiSettings}
    try:
        result = await post("/create-dashboard", json=payload)
        return result
    except Exception as e:
        logging.error(f"create_dashboard error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: create_dashboard")

@mcp.tool(description="Fetch data for multiple charts using chart configs and API settings.")
async def get_charts_data(chartConfigs: list, apiSettings: dict) -> dict:
    """
    Fetch data for multiple charts using the provided chart configurations and API settings.

    Args:
        chartConfigs (list): List of chart configuration dicts.
        apiSettings (dict): API settings for authentication.

    Returns:
        dict: Chart data or error status.
    """
    payload = {"chartConfigs": chartConfigs, "apiSettings": apiSettings}
    try:
        result = await post("/charts/data", json=payload)
        return result
    except Exception as e:
        logging.error(f"get_charts_data error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: get_charts_data")

@mcp.tool(description="Analyze chart data for insights based on a question and API settings.")
async def analyze_charts(chartData: dict, question: str, apiSettings: dict) -> dict:
    """
    Analyze chart data for insights, given a question and API settings.

    Args:
        chartData (dict): Data for the charts.
        question (str): The analytical question to answer.
        apiSettings (dict): API settings for authentication.

    Returns:
        dict: Insights or error status.
    """
    payload = {"chartData": chartData, "question": question, "apiSettings": apiSettings}
    try:
        result = await post("/analyze-charts", json=payload)
        return result
    except Exception as e:
        logging.error(f"analyze_charts error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: analyze_charts")

@mcp.tool(description="Generate a summary from insights, question, strategy, and API settings.")
async def generate_summary(insights: list, question: str, strategy: dict, apiSettings: dict, errors: list = None) -> dict:
    """
    Generate a summary from insights, question, strategy, and API settings.

    Args:
        insights (list): List of insights from chart analysis.
        question (str): The analytical question to answer.
        strategy (dict): Analysis strategy.
        apiSettings (dict): API settings for authentication.
        errors (list, optional): List of errors from previous steps.

    Returns:
        dict: Summary or error status.
    """
    payload = {"insights": insights, "question": question, "strategy": strategy, "apiSettings": apiSettings}
    if errors:
        payload["errors"] = errors
    try:
        result = await post("/generate-summary", json=payload)
        return result
    except Exception as e:
        logging.error(f"generate_summary error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: generate_summary")

@mcp.tool(description="Run the full analysis workflow (one-shot): source + question → answer + dashboard.")
async def analyze_source_question(
    apiUrl: str,
    jwtToken: str,
    sourceId: str,
    question: str,
    columnDescriptions: dict = None
) -> dict:
    """
    Run the full analysis workflow for a given source and question (one-shot tool).

    This tool orchestrates all steps:
        1. Get source structure
        2. Analyze columns
        3. Generate strategy
        4. Create configuration
        5. Create dashboard
        6. Get chart data
        7. Analyze charts
        8. Generate summary
        9. Return summary, dashboard URL, and all intermediate results

    Args:
        apiUrl (str): The base URL of the external API.
        jwtToken (str): JWT token for authentication.
        sourceId (str): ID of the data source to analyze.
        question (str): Analytical question to answer.
        columnDescriptions (dict, optional): Optional column descriptions.

    Returns:
        dict: {
            "summary": str,  # Final answer/insight
            "dashboardUrl": str,  # Link to the created dashboard
            "intermediate": dict  # All intermediate results (column analysis, strategy, config, etc.)
        } or error status.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    try:
        # Step 1: Get source structure (returns structure directly)
        source_structure = await get(f"/source/{sourceId}/structure", headers=headers, timeout=LONG_TIMEOUT)

        # Step 2: Analyze columns
        payload = {"sourceStructure": source_structure}
        if columnDescriptions:
            payload["columnDescriptions"] = columnDescriptions
        column_analysis_resp = await post("/analyze-columns", json=payload, timeout=LONG_TIMEOUT)
        if column_analysis_resp.get("status") != "success":
            return {"status": "error", "error": column_analysis_resp.get("error", "Column analysis failed")}
        column_analysis = column_analysis_resp["columnAnalysis"]

        # Step 3: Generate strategy
        strategy_resp = await post("/generate-strategy", json={"question": question, "columnAnalysis": column_analysis}, timeout=LONG_TIMEOUT)
        if strategy_resp.get("status") != "success":
            return {"status": "error", "error": strategy_resp.get("error", "Strategy generation failed")}
        strategy = strategy_resp["strategy"]

        # Step 4: Create configuration
        config_resp = await post("/create-configuration", json={"question": question, "columnAnalysis": column_analysis, "strategy": strategy}, timeout=LONG_TIMEOUT)
        if config_resp.get("status") != "success":
            return {"status": "error", "error": config_resp.get("error", "Configuration creation failed")}
        config = config_resp["configuration"]

        # Step 5: Create dashboard
        api_settings = {"apiUrl": apiUrl, "jwtToken": jwtToken}
        dashboard_resp = await post("/create-dashboard", json={"markdownConfig": config, "sourceStructure": source_structure, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if dashboard_resp.get("status") != "success":
            return {"status": "error", "error": dashboard_resp.get("error", "Dashboard creation failed")}
        dashboard_url = dashboard_resp["dashboardUrl"]
        charts = dashboard_resp["charts"]

        # Step 6: Get chart data
        chart_data_resp = await post("/charts/data", json={"chartConfigs": charts, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if chart_data_resp.get("status") != "success":
            return {"status": "error", "error": chart_data_resp.get("error", "Chart data fetch failed")}
        chart_data = chart_data_resp["chartData"]
        chart_errors = chart_data_resp.get("errors", [])

        # Step 7: Analyze charts
        insights_resp = await post("/analyze-charts", json={"chartData": chart_data, "question": question, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if insights_resp.get("status") != "success":
            return {"status": "error", "error": insights_resp.get("error", "Chart analysis failed")}
        insights = insights_resp["insights"]
        insights_errors = insights_resp.get("errors", [])

        # Step 8: Generate summary
        summary_resp = await post("/generate-summary", json={
            "insights": insights,
            "question": question,
            "strategy": strategy,
            "apiSettings": api_settings,
            "errors": chart_errors + insights_errors
        }, timeout=LONG_TIMEOUT)
        if summary_resp.get("status") != "success":
            return {"status": "error", "error": summary_resp.get("error", "Summary generation failed")}
        summary = summary_resp["summary"]

        # Step 9: Return results (include all intermediate results for transparency)
        return {
            "summary": summary,
            "dashboardUrl": dashboard_url,
            "intermediate": {
                "sourceStructure": source_structure,
                "columnAnalysis": column_analysis,
                "strategy": strategy,
                "configuration": config,
                "dashboard": {"dashboardUrl": dashboard_url, "charts": charts},
                "chartData": {"chartData": chart_data, "errors": chart_errors},
                "insights": {"insights": insights, "errors": insights_errors}
            }
        }
    except Exception as e:
        logging.error(f"analyze_source_question error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: analyze_source_question")

# Print all registered tools after all definitions
print("[DEBUG] All tools registered:", list(getattr(mcp, "_tools", {}).keys()))
print("[DEBUG] MCP server ready for protocol connection.") 