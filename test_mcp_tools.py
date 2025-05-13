import os
import sys
import asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

# Load environment variables from .env
load_dotenv()

API_URL = os.getenv("apiUrl")
JWT_TOKEN = os.getenv("jwtToken")
SOURCE_ID = os.getenv("sourceId")
QUESTION = os.getenv("question")
SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", "mcp_server.py")

missing = [k for k, v in [("apiUrl", API_URL), ("jwtToken", JWT_TOKEN), ("sourceId", SOURCE_ID), ("question", QUESTION)] if not v]
if missing:
    print(f"Missing required .env variables: {', '.join(missing)}")
    sys.exit(1)

async def main():
    print("\n--- MCP Tools Health Check (STDIO) ---\n")
    server_params = StdioServerParameters(
        command="mcp",
        args=["run", SERVER_SCRIPT],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # List available tools
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            print("Available tools:", tool_names)

            # Step-by-step data for chaining
            source_structure = None
            column_analysis = None
            strategy = None
            config = None
            dashboard = None
            chart_data = None
            insights = None

            # 1. validate_settings
            print("\n[TEST] validate_settings ...")
            result_obj = await session.call_tool("validate_settings", {"apiUrl": API_URL, "jwtToken": JWT_TOKEN})
            result = json.loads(result_obj.content[0].text)
            print("Result:", result)

            # 2. list_sources
            print("\n[TEST] list_sources ...")
            result_obj = await session.call_tool("list_sources", {"apiUrl": API_URL, "jwtToken": JWT_TOKEN, "search": "", "page": 1, "limit": 5})
            result = json.loads(result_obj.content[0].text)
            print("Result:", result)

            # 3. get_source_structure
            print("\n[TEST] get_source_structure ...")
            result_obj = await session.call_tool("get_source_structure", {"apiUrl": API_URL, "jwtToken": JWT_TOKEN, "sourceId": SOURCE_ID})
            source_structure = json.loads(result_obj.content[0].text)
            print("Result:", source_structure)

            try:
                json.dumps(source_structure)
                print("[DEBUG] source_structure is JSON serializable")
            except Exception as e:
                print("[DEBUG] source_structure is NOT JSON serializable:", e)
            print("[DEBUG] source_structure size (chars):", len(json.dumps(source_structure)))

            # 4. analyze_columns
            print("\n[TEST] analyze_columns ...")
            result_obj = await session.call_tool("analyze_columns", {"sourceStructure": source_structure})
            column_analysis_result = json.loads(result_obj.content[0].text)
            print("Result:", column_analysis_result)
            column_analysis = column_analysis_result.get("columnAnalysis")

            # 5. generate_strategy
            print("\n[TEST] generate_strategy ...")
            result_obj = await session.call_tool("generate_strategy", {"question": QUESTION, "columnAnalysis": column_analysis})
            strategy_result = json.loads(result_obj.content[0].text)
            print("Result:", strategy_result)
            strategy = strategy_result.get("strategy")

            # 6. create_configuration
            print("\n[TEST] create_configuration ...")
            result_obj = await session.call_tool("create_configuration", {"question": QUESTION, "columnAnalysis": column_analysis, "strategy": strategy})
            config_result = json.loads(result_obj.content[0].text)
            print("Result:", config_result)
            config = config_result.get("configuration")

            # 7. generate_config
            print("\n[TEST] generate_config ...")
            result_obj = await session.call_tool(
                "generate_config",
                {
                    "question": QUESTION,
                    "sourceStructure": source_structure,
                    "apiSettings": {"apiUrl": API_URL, "jwtToken": JWT_TOKEN}
                }
            )
            gen_config_result = json.loads(result_obj.content[0].text)
            print("Result:", gen_config_result)

            # 8. create_dashboard
            print("\n[TEST] create_dashboard ...")
            result_obj = await session.call_tool("create_dashboard", {"markdownConfig": config, "sourceStructure": source_structure, "apiSettings": {"apiUrl": API_URL, "jwtToken": JWT_TOKEN}})
            dashboard_result = json.loads(result_obj.content[0].text)
            print("Result:", dashboard_result)
            dashboard = dashboard_result

            # 9. get_charts_data
            print("\n[TEST] get_charts_data ...")
            result_obj = await session.call_tool("get_charts_data", {"chartConfigs": dashboard.get("charts", []), "apiSettings": {"apiUrl": API_URL, "jwtToken": JWT_TOKEN}})
            chart_data_result = json.loads(result_obj.content[0].text)
            print("Result:", chart_data_result)
            chart_data = chart_data_result.get("chartData")

            # 10. analyze_charts
            print("\n[TEST] analyze_charts ...")
            result_obj = await session.call_tool("analyze_charts", {"chartData": chart_data, "question": QUESTION, "apiSettings": {"apiUrl": API_URL, "jwtToken": JWT_TOKEN}})
            analyze_charts_result = json.loads(result_obj.content[0].text)
            print("Result:", analyze_charts_result)
            insights = analyze_charts_result.get("insights")

            # 11. generate_summary
            print("\n[TEST] generate_summary ...")
            result_obj = await session.call_tool("generate_summary", {"insights": insights, "question": QUESTION, "strategy": strategy, "apiSettings": {"apiUrl": API_URL, "jwtToken": JWT_TOKEN}})
            summary_result = json.loads(result_obj.content[0].text)
            print("Result:", summary_result)

            # 12. analyze_source_question (one-shot)
#            print("\n[TEST] analyze_source_question (one-shot) ...")
#            result_obj = await session.call_tool("analyze_source_question", {"apiUrl": API_URL, "jwtToken": JWT_TOKEN, "sourceId": SOURCE_ID, "question": QUESTION})
#            one_shot_result = json.loads(result_obj.content[0].text)
#            print("Result:", one_shot_result)

    print("\n--- MCP Tools Health Check Complete ---\n")

if __name__ == "__main__":
    asyncio.run(main()) 