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
    filename="mcp_server.log",
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
# logging.info("Registered tool: validate_settings")

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

@mcp.tool(description="Get detailed structure (columns, data types) for a specific 'sourceId'. Call this AFTER the user selects a 'sourceId' from 'list_sources', if they need more details about the data before formulating a question or if 'columnDescriptions' are planned for 'prepare_analysis_configuration'. The output (source schema) can be presented to the user in user friendly way (e.g. markdown table). Returns: dict (source structure schema).")
async def get_source_structure(apiUrl: str, jwtToken: str, sourceId: str) -> dict:
    """
    Retrieve the structure/schema for a specified data source.
    (Detailed comments here are for human developers; LLM guidance is in the decorator description.)
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    try:
        result = await get(f"/source/{sourceId}/structure", headers=headers)
        return {"status": "success", "sourceStructure": result}
    except Exception as e:
        logging.error(f"get_source_structure error: {repr(e)}")
        return {"status": "error", "error": str(e)}
logging.info("Registered tool: get_source_structure")

@mcp.tool(description="Analyze columns for a given source structure. Returns: dict (column analysis results).")
async def analyze_columns(sourceStructure: dict) -> dict:
    """
    Analyze columns for a given source structure.

    Args:
        sourceStructure (dict): The structure/schema of the data source.

    Returns:
        dict: Column analysis results or error status.
    """
    payload = {"sourceStructure": sourceStructure}
    try:
        result = await post("/analyze-columns", json=payload)
        if isinstance(result, list):
            return {"status": "success", "columnAnalysis": result}
        return result
    except Exception as e:
        logging.error(f"analyze_columns error: {repr(e)}")
        return {"status": "error", "error": str(e)}
# logging.info("Registered tool: analyze_columns")

# @mcp.tool(description="Generate analysis strategy for a question and column analysis.")
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
# logging.info("Registered tool: generate_strategy")

# @mcp.tool(description="Create dashboard configuration from question, column analysis, and strategy.")
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
# logging.info("Registered tool: create_configuration")

@mcp.tool(description="Generate dashboard config (markdown) from question and source structure. Returns: dict (markdown configuration).")
async def generate_config(question: str, sourceStructure: dict, apiSettings: dict = None) -> dict:
    """
    Generate a dashboard configuration (in markdown) from a question and source structure.

    Args:
        question (str): The analytical question to answer.
        sourceStructure (dict): The structure/schema of the data source.
        apiSettings (dict, optional): API settings for authentication.

    Returns:
        dict: Markdown configuration or error status.
    """
    payload = {"question": question, "sourceStructure": sourceStructure}
    if apiSettings:
        payload["apiSettings"] = apiSettings
    try:
        result = await post("/generate-config", json=payload)
        return result
    except Exception as e:
        logging.error(f"generate_config error: {repr(e)}")
        return {"status": "error", "error": str(e)}
# logging.info("Registered tool: generate_config")

# @mcp.tool(description="Create a dashboard from config, source structure, and API settings.")
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
# logging.info("Registered tool: create_dashboard")

# @mcp.tool(description="Fetch data for multiple charts using chart configs and API settings.")
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
# logging.info("Registered tool: get_charts_data")

# @mcp.tool(description="Analyze chart data for insights based on a question and API settings.")
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
# logging.info("Registered tool: analyze_charts")

# @mcp.tool(description="Generate a summary from insights, question, strategy, and API settings.")
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
# logging.info("Registered tool: generate_summary")

@mcp.tool(description="ONE-SHOT ANALYSIS: Runs the full analysis workflow directly from a 'sourceId' and 'question' to generate insights, a summary, and a dashboard URL. Use this when the user prefers a direct answer WITHOUT an intermediate review step of the analysis configuration. Returns: {{'summary': str, 'dashboardUrl': str, 'intermediate': {{...}}}}. Present 'summary' and 'dashboardUrl' to the user.")
async def analyze_source_question(
    apiUrl: str,
    jwtToken: str,
    sourceId: str,
    question: str
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
        apiUrl (str): The base URL of the external API. (Handled by MCP Client)
        jwtToken (str): JWT token for authentication. (Handled by MCP Client)
        sourceId (str): ID of the data source to analyze (selected by user).
        question (str): Analytical question to answer (formulated by user).

    Returns:
        dict: {
            "summary": str,               // Final textual answer/insight for the user.
            "dashboardUrl": str,          // Link to the interactive dashboard supporting the summary.
            "intermediate": {             // Detailed intermediate results for transparency/debugging.
                "sourceStructure": dict,
                "columnAnalysis": list,
                "strategy": dict,
                "configuration": str,     // The markdown configuration used
                "dashboard": {"dashboardUrl": str, "charts": list},
                "chartData": {"chartData": dict, "errors": list},
                "insights": {"insights": list, "errors": list}
            }
        } or error status.
        The LLM should primarily present the 'summary' and 'dashboardUrl' to the user.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    try:
        # Step 1: Get source structure (returns structure directly)
        source_structure = await get(f"/source/{sourceId}/structure", headers=headers, timeout=LONG_TIMEOUT)

        # Step 2: Analyze columns
        payload = {"sourceStructure": source_structure}
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

# --- New Step-by-Step Tools ---

@mcp.tool(description="STEP 1 of 2-STEP ANALYSIS: Analyzes 'sourceId' and 'question' to generate a 'markdownConfig' (dashboard configuration text) for user review. Also returns 'sourceStructure', 'columnAnalysis', and 'strategy' which are needed for STEP 2 ('execute_analysis_from_config'). Use this when the user wants to inspect or modify the analysis plan before execution. When returning the 'markdownConfig' to the user, present it as a markdown formatted text, not as a JSON object and wait for user's response. Returns: {{'status': 'success'|'error', 'markdownConfig': str}}. Present 'markdownConfig' to the user for review/modification.")
async def prepare_analysis_configuration(
    apiUrl: str,
    jwtToken: str,
    sourceId: str,
    question: str
) -> dict:
    """
    Analyzes the source data structure and the user's question to generate a
    proposed dashboard configuration (in markdown). This allows review and
    modification before executing the full analysis.

    Internally, this tool:
        1. Fetches source structure for the given 'sourceId'.
        2. Analyzes columns.
        3. Generates an analysis 'strategy' based on the 'question' and column analysis.
        4. Creates the 'markdownConfig' based on the 'question', column analysis, and 'strategy'.

    Args:
        apiUrl (str): The base URL of the external API. (Handled by MCP Client)
        jwtToken (str): JWT token for authentication. (Handled by MCP Client)
        sourceId (str): ID of the data source to analyze (selected by user).
        question (str): Analytical question to answer (formulated by user).

    Returns:
        dict: {
            "status": "success" | "error",
            "markdownConfig": str,       // The generated dashboard configuration in markdown format. LLM should present this to the user for review and potential modification.
            "intermediate": {            // Internal data needed for subsequent steps, not shown to LLM
                "sourceStructure": dict, // The source structure used for this configuration
                "columnAnalysis": list,  // Results from the internal column analysis
                "strategy": dict         // The generated analysis strategy
            },
            "error": str (if status == "error")
        }
        The LLM should present 'markdownConfig' to the user. If the user approves or modifies it, then 'execute_analysis_from_config' should be called next, passing the (potentially modified) 'markdownConfig', along with the 'question', 'sourceStructure', and 'strategy' returned by this tool.
    """
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    intermediate_results = {}
    try:
        # Step 1: Get source structure
        source_structure = await get(f"/source/{sourceId}/structure", headers=headers, timeout=LONG_TIMEOUT)
        intermediate_results["sourceStructure"] = source_structure

        # Step 2: Analyze columns
        payload_analyze_cols = {"sourceStructure": source_structure}
        column_analysis_resp = await post("/analyze-columns", json=payload_analyze_cols, timeout=LONG_TIMEOUT)
        if column_analysis_resp.get("status") != "success":
            return {"status": "error", "error": column_analysis_resp.get("error", "Column analysis failed during preparation"), "intermediate": intermediate_results}
        column_analysis = column_analysis_resp["columnAnalysis"]
        intermediate_results["columnAnalysis"] = column_analysis

        # Step 3: Generate strategy
        strategy_resp = await post("/generate-strategy", json={"question": question, "columnAnalysis": column_analysis}, timeout=LONG_TIMEOUT)
        if strategy_resp.get("status") != "success":
            return {"status": "error", "error": strategy_resp.get("error", "Strategy generation failed during preparation"), "intermediate": intermediate_results}
        strategy = strategy_resp["strategy"]
        intermediate_results["strategy"] = strategy

        # Step 4: Create configuration (markdown)
        # Assumes /create-configuration returns the markdown string in "configuration" field
        config_resp = await post("/create-configuration", json={"question": question, "columnAnalysis": column_analysis, "strategy": strategy}, timeout=LONG_TIMEOUT)
        if config_resp.get("status") != "success":
            return {"status": "error", "error": config_resp.get("error", "Configuration creation failed during preparation"), "intermediate": intermediate_results}
        markdown_config = config_resp["configuration"] # This should be the markdown string

        return {
            "status": "success",
            "markdownConfig": markdown_config,
            "intermediate": intermediate_results
        }
    except Exception as e:
        logging.error(f"prepare_analysis_configuration error: {repr(e)}")
        return {"status": "error", "error": str(e), "intermediate": intermediate_results}
logging.info("Registered tool: prepare_analysis_configuration")

@mcp.tool(description="STEP 2 of 2-STEP ANALYSIS: Executes analysis using a 'markdownConfig', 'question', 'sourceStructure', and 'strategy'. Call this AFTER 'prepare_analysis_configuration' AND after the user has reviewed (and potentially modified) the 'markdownConfig'. Generates the final summary and dashboard. Can be called without arguments, then MCP will use all cached intermediate results from 'prepare_analysis_configuration'. If user wants to modify the 'markdownConfig', then this tool should be called with the modified 'markdownConfig', the rest of the arguments would be taken from cached intermediate results. Returns: {{'status': 'success'|'error', 'summary': str, 'dashboardUrl': str, 'intermediate': {{...}}}}. Present 'summary' and 'dashboardUrl' to the user.")
async def execute_analysis_from_config(
    apiUrl: str,
    jwtToken: str,
    question: str,
    markdownConfig: str,
    sourceStructure: dict,
    strategy: dict
) -> dict:
    """
    Executes the data analysis using a provided dashboard configuration (markdown),
    source structure, and strategy. Creates the dashboard, fetches chart data,
    analyzes it, and generates a final summary.

    Args:
        apiUrl (str): The base URL of the external API. (Handled by MCP Client)
        jwtToken (str): JWT token for authentication. (Handled by MCP Client)
        question (str): The original analytical question. This MUST be provided by the LLM, matching the question used for 'prepare_analysis_configuration'.
        markdownConfig (str): The dashboard configuration in markdown format. This MUST be provided by the LLM. It should be the output from 'prepare_analysis_configuration', potentially modified by the user.
        sourceStructure (dict): The source structure corresponding to the 'markdownConfig'. This MUST be provided by the LLM, obtained from 'prepare_analysis_configuration' output.
        strategy (dict): The analysis strategy corresponding to the 'markdownConfig'. This MUST be provided by the LLM, obtained from 'prepare_analysis_configuration' output.

    Returns:
        dict: {
            "status": "success" | "error",
            "summary": str,          // Final textual answer/insight for the user.
            "dashboardUrl": str,     // Link to the interactive dashboard supporting the summary.
            "intermediate": dict,    // Detailed intermediate results (charts, data, insights).
            "error": str (if status == "error")
        }
        The LLM should primarily present the 'summary' and 'dashboardUrl' to the user.
    """
    api_settings = {"apiUrl": apiUrl, "jwtToken": jwtToken}
    intermediate_results = {}
    try:
        # Step 1: Create dashboard (corresponds to original step 5)
        dashboard_resp = await post("/create-dashboard", json={"markdownConfig": markdownConfig, "sourceStructure": sourceStructure, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if dashboard_resp.get("status") != "success":
            return {"status": "error", "error": dashboard_resp.get("error", "Dashboard creation failed during execution"), "intermediate": intermediate_results}
        dashboard_url = dashboard_resp["dashboardUrl"]
        charts = dashboard_resp["charts"]
        intermediate_results["dashboard"] = {"dashboardUrl": dashboard_url, "charts": charts}

        # Step 2: Get chart data (corresponds to original step 6)
        chart_data_resp = await post("/charts/data", json={"chartConfigs": charts, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if chart_data_resp.get("status") != "success":
            return {"status": "error", "error": chart_data_resp.get("error", "Chart data fetch failed during execution"), "intermediate": intermediate_results}
        chart_data = chart_data_resp["chartData"]
        chart_errors = chart_data_resp.get("errors", [])
        intermediate_results["chartData"] = {"chartData": chart_data, "errors": chart_errors}

        # Step 3: Analyze charts (corresponds to original step 7)
        insights_resp = await post("/analyze-charts", json={"chartData": chart_data, "question": question, "apiSettings": api_settings}, timeout=LONG_TIMEOUT)
        if insights_resp.get("status") != "success":
            return {"status": "error", "error": insights_resp.get("error", "Chart analysis failed during execution"), "intermediate": intermediate_results}
        insights = insights_resp["insights"]
        insights_errors = insights_resp.get("errors", [])
        intermediate_results["insights"] = {"insights": insights, "errors": insights_errors}

        # Step 4: Generate summary (corresponds to original step 8)
        all_errors = chart_errors + insights_errors
        summary_payload = {
            "insights": insights,
            "question": question,
            "strategy": strategy, # Use the strategy passed in
            "apiSettings": api_settings
        }
        if all_errors:
            summary_payload["errors"] = all_errors

        summary_resp = await post("/generate-summary", json=summary_payload, timeout=LONG_TIMEOUT)
        if summary_resp.get("status") != "success":
            return {"status": "error", "error": summary_resp.get("error", "Summary generation failed during execution"), "intermediate": intermediate_results}
        summary = summary_resp["summary"]

        return {
            "status": "success",
            "summary": summary,
            "dashboardUrl": dashboard_url,
            "intermediate": intermediate_results
        }
    except Exception as e:
        logging.error(f"execute_analysis_from_config error: {repr(e)}")
        return {"status": "error", "error": str(e), "intermediate": intermediate_results}
logging.info("Registered tool: execute_analysis_from_config")

# Print all registered tools after all definitions
print("[DEBUG] All tools registered:", list(getattr(mcp, "_tools", {}).keys()))
print("[DEBUG] MCP server ready for protocol connection.") 