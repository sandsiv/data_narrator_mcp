import os
import sys
import threading
import time
import atexit
from flask import Flask, jsonify, request
import socket
from mcp_client.manager import MCPServerManager
from mcp_client.session_manager import MCPSessionManager
from mcp_client.config import MCPConfig
import copy
import json
import requests
from urllib.parse import urlparse
from functools import wraps
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Redis-only session manager
try:
    # Validate configuration first
    if not MCPConfig.validate_config():
        print("[MCP CLIENT] Configuration validation failed, exiting", flush=True)
        sys.exit(1)
    
    session_manager = MCPSessionManager()
    print("[MCP CLIENT] Redis-only session manager initialized", flush=True)
except Exception as e:
    print(f"[MCP CLIENT] Failed to initialize session manager: {e}", flush=True)
    print("[MCP CLIENT] Please ensure Redis is running and properly configured", flush=True)
    sys.exit(1)

# Register cleanup on exit
atexit.register(lambda: session_manager.shutdown())

# Create Flask app
app = Flask(__name__)

# Configuration from config.py
SENSITIVE_PARAMS = MCPConfig.Security.SENSITIVE_PARAMS
API_BASE_URL = MCPConfig.API.BASE_URL

def validate_api_url(url):
    """Validate API URL format."""
    try:
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
        if parsed.scheme not in ['http', 'https']:
            return False
        return True
    except:
        return False

def validate_jwt_token(token):
    """Basic JWT token format validation."""
    if not token or not isinstance(token, str):
        return False
    parts = token.split('.')
    return len(parts) == 3

def validate_credentials_direct(api_url, jwt_token):
    """
    Validate credentials by calling the API directly (without MCP server).
    Returns: (is_valid: bool, error_message: str)
    """
    try:
        # Input validation
        if not validate_api_url(api_url):
            return False, "Invalid API URL format"
        
        if not validate_jwt_token(jwt_token):
            return False, "Invalid JWT token format"
        
        # For development/testing: Skip validation in certain cases
        if "localhost" in API_BASE_URL or "127.0.0.1" in API_BASE_URL:
            print(f"[MCP CLIENT] Development mode: Skipping credential validation for {api_url}", flush=True)
            return True, None
        
        # Test mode: Skip validation if environment variable is set
        if os.getenv("MCP_SKIP_VALIDATION", "").lower() in ["true", "1", "yes"]:
            print(f"[MCP CLIENT] Test mode: Skipping credential validation (MCP_SKIP_VALIDATION=true)", flush=True)
            return True, None
        
        # Make validation request (same as validate_settings tool)
        validation_url = f"{API_BASE_URL}/settings/validate"
        payload = {"apiUrl": api_url, "jwtToken": jwt_token}
        
        response = requests.post(
            validation_url, 
            json=payload, 
            timeout=MCPConfig.API.VALIDATION_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Check for success response
        if result.get("status") == "success":
            return True, None
        
        # Handle error response from API
        if result.get("status") == "error":
            error_msg = result.get("error", "Authentication failed")
            return False, error_msg
        
        # Unexpected response format
        return False, "Unexpected response from validation service"
        
    except requests.exceptions.Timeout:
        return False, "Validation request timed out"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to validation service"
    except requests.exceptions.HTTPError as e:
        # Return the actual error instead of bypassing it
        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                return False, f"API validation failed: {error_detail.get('error', str(e))}"
            except:
                return False, f"API validation failed: {str(e)}"
        else:
            return False, f"HTTP error during validation: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def is_session_active(session_id):
    """Check if session exists in Redis."""
    return session_manager.session_exists(session_id)

def filter_tool_schema(tool_schema, sensitive_params=None):
    """
    Remove sensitive parameters from a tool schema dict (supports JSON Schema in 'inputSchema').
    Args:
        tool_schema (dict): The tool schema as returned by the MCP server.
        sensitive_params (list): List of parameter names to remove.
    Returns:
        dict: Filtered tool schema.
    """
    if sensitive_params is None:
        sensitive_params = SENSITIVE_PARAMS
    schema = copy.deepcopy(tool_schema)
    # Remove from 'inputSchema' if present
    if "inputSchema" in schema and isinstance(schema["inputSchema"], dict):
        props = schema["inputSchema"].get("properties", {})
        for param in sensitive_params:
            props.pop(param, None)
        # Also remove from 'required' if present
        if "required" in schema["inputSchema"]:
            schema["inputSchema"]["required"] = [
                r for r in schema["inputSchema"]["required"] if r not in sensitive_params
            ]
    return schema

# Helper function to get session data from Redis
def get_session_data(session_id):
    """Get session data from Redis (automatically resets TTL)."""
    return session_manager.get_session_data(session_id)

# Helper function to clear session data
def clear_session_data(session_id):
    """Clear session data from Redis."""
    return session_manager.delete_session(session_id)

# Helper function to create MCP manager on-demand
def create_mcp_manager_for_request(session_id):
    """Create MCP manager for this request (not cached)."""
    return session_manager.create_mcp_manager(session_id)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    # This endpoint doesn't need session_id
    return jsonify({"status": "ok"})

@app.route('/init', methods=['POST'])
def init():
    """
    Initialize the MCP client session with secure credential validation.
    Accepts JSON with session_id, apiUrl, jwtToken, and other params.
    
    Security Flow:
    1. Check if session already exists and is active → return success immediately
    2. Validate credentials directly (5sec timeout) → return 401 if invalid  
    3. Store credentials in Redis and return success
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        apiUrl = data.get('apiUrl')
        jwtToken = data.get('jwtToken')
        
        if not session_id or not apiUrl or not jwtToken:
            return jsonify({"status": "error", "error": "Missing session_id, apiUrl, or jwtToken"}), 400

        # SECURITY: Check if session already exists and is active
        if is_session_active(session_id):
            print(f"[MCP CLIENT] Session {session_id} already active, returning success", flush=True)
            return jsonify({"status": "ok"})

        # SECURITY: Validate credentials directly before creating session
        print(f"[MCP CLIENT] Validating credentials for session_id: {session_id}", flush=True)
        is_valid, error_message = validate_credentials_direct(apiUrl, jwtToken)
        
        if not is_valid:
            print(f"[MCP CLIENT] Credential validation failed for session_id {session_id}: {error_message}", flush=True)
            
            # Determine if it's an authentication error (401) or server error (500)
            if any(keyword in error_message.lower() for keyword in ['forbidden', '403', 'authentication', 'credentials', 'token']):
                return jsonify({"status": "error", "error": error_message}), 401
            else:
                return jsonify({"status": "error", "error": error_message}), 500

        print(f"[MCP CLIENT] Credentials validated successfully for session_id: {session_id}", flush=True)

        # Create session in Redis with all init data
        if not session_manager.create_session(session_id, data):
            return jsonify({"status": "error", "error": "Failed to create session"}), 500

        print(f"[MCP CLIENT] Session created successfully for session_id: {session_id}", flush=True)
        return jsonify({"status": "ok"})
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /init error for session_id {data.get('session_id')}:", e, traceback.format_exc(), flush=True)
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Cleanly shut down the MCP client *session*.
    Accepts JSON with session_id.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')

        clear_session_data(session_id) # This deletes the session from Redis

        return jsonify({"status": "ok", "message": f"Session {session_id} shut down."})
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /shutdown error for session_id {data.get('session_id', 'N/A')}:", e, traceback.format_exc(), flush=True)
        # Even on error, try to clear session data
        try:
            if 'session_id' in locals():
                session_manager.delete_session(session_id)
        except Exception:
             pass # Ignore errors during cleanup attempt
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/tools-schema', methods=['GET'])
def get_tools_schema():
    """
    Get tool schemas without requiring authentication.
    This allows the bridge to show actual tool descriptions to Claude before authentication.
    Returns the raw tool schemas from the MCP server.
    """
    try:
        print("[MCP CLIENT] /tools-schema: Fetching tool schemas without authentication", flush=True)
        
        # Create a temporary MCP manager to get tool schemas
        temp_manager = MCPServerManager()
        
        try:
            # Start the manager temporarily
            temp_manager.start()
            
            # Get tool schemas
            tools = temp_manager.get_tool_schemas()
            
            # Filter out sensitive parameters only
            filtered_tools = []
            for tool in tools:
                filtered_tool = filter_tool_schema(tool)
                filtered_tools.append(filtered_tool)
            
            print(f"[MCP CLIENT] /tools-schema: Successfully fetched {len(filtered_tools)} tool schemas", flush=True)
            
            # Add comprehensive system information for Claude Desktop
            system_info = {
                "system_name": "Sandsiv+ Insight Digger",
                "system_type": "Enterprise Data Analysis Platform",
                "purpose": "Transform business questions into interactive dashboards and AI-powered insights using Sandsiv+ data sources",
                "when_to_use": [
                    "User wants to analyze data from Sandsiv+ platform",
                    "User asks about business metrics, KPIs, or data trends",
                    "User needs to create dashboards or data visualizations",
                    "User mentions Sandsiv+, data analysis, or business intelligence",
                    "User wants to explore available data sources",
                    "User has analytical questions about their business data"
                ],
                "capabilities": [
                    "Connect to Sandsiv+ data sources securely",
                    "Analyze data structure and recommend visualization strategies",
                    "Generate interactive dashboards with multiple chart types",
                    "Extract AI-powered insights from data patterns",
                    "Support complex multi-step analytical workflows",
                    "Provide comprehensive analytical reports"
                ],
                "workflow_overview": "7-step process: Authentication → Source Discovery → Structure Analysis → Strategy Planning → Configuration → Dashboard Creation → Insight Generation",
                "authentication_required": True,
                "enterprise_features": [
                    "JWT-based secure authentication",
                    "Intelligent parameter caching - automatically injects data from previous tool calls",
                    "Session management with workflow state preservation",
                    "Multi-tenant data isolation",
                    "Granular workflow optimization for timeout-sensitive clients"
                ],
                "caching_behavior": {
                    "description": "The system automatically caches and injects parameters from previous tool calls. Claude should NOT repeat parameters that were used in previous steps.",
                    "auto_injected_params": ["apiUrl", "jwtToken", "sourceId", "columnAnalysis", "strategy", "sourceStructure", "chartConfigs", "markdownConfig", "chartData"],
                    "guidance": "Only provide parameters that are new or have changed. The system will automatically use cached values from the workflow session."
                }
            }
            
            return jsonify({
                "status": "success",
                "tools": filtered_tools,
                "system_info": system_info
            })
            
        finally:
            # Always clean up the temporary manager
            try:
                temp_manager.stop()
            except Exception as cleanup_e:
                print(f"[MCP CLIENT] Warning: Error cleaning up temporary manager: {cleanup_e}", flush=True)
                
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /tools-schema error:", e, traceback.format_exc(), flush=True)
        return jsonify({
            "status": "error", 
            "error": f"Failed to fetch tool schemas: {str(e)}"
        }), 500

@app.route('/tools', methods=['POST'])
# Changed to POST to accept session_id in body consistently with other endpoints
def list_tools():
    """
    List available MCP tools for a specific session, filtering out sensitive parameters.
    Accepts JSON with session_id.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({"status": "error", "error": "Missing session_id"}), 400
            
        # Touch session to reset TTL and verify it exists
        if not session_manager.touch_session(session_id):
            return jsonify({"status": "error", "error": f"Session {session_id} not found or expired. Please run /init first."}), 409

        # Create MCP manager for this request
        mcp_manager = create_mcp_manager_for_request(session_id)
        if not mcp_manager:
            return jsonify({"status": "error", "error": f"Failed to initialize MCP server for session {session_id}."}), 500

        try:
            tools = mcp_manager.get_tool_schemas()
            # Filter each tool schema
            filtered_tools = [filter_tool_schema(tool) for tool in tools]

            # Add general workflow guidance for LLMs
            workflow_guidance = {
                "workflow": {
                    "description": "This is a data analysis workflow. For clients with strict timeouts (e.g., < 60s), the **Granular Step-by-Step Workflow** is strongly recommended. For clients that can handle long-running requests, alternative composite tools are available.",
                    "recommended_workflow": {
                        "title": "Granular Step-by-Step Workflow ",
                        "description": "Execute each step of the analysis as a separate, fast-running tool call. The client-side caching will automatically pass results from one step to the next.",
                        "steps": [
                            {
                                "step": 1,
                                "description": "Source Selection: Ask the user for a source name to search for.",
                                "tool": "list_sources",
                                "guidance": "Use the 'list_sources' tool with the user's search term. Present the results and ask the user to select a source by its 'id'."
                            },
                            {
                                "step": 2,
                                "description": "Analyze Source Structure: Fetch and analyze the schema for the selected source.",
                                "tool": "analyze_source_structure",
                                "guidance": "Use 'analyze_source_structure' with the 'sourceId' from the previous step. Present the 'columnAnalysis' to the user to help them formulate a question."
                            },
                            {
                                "step": 3,
                                "description": "Generate Strategy: Create an analysis strategy based on the user's question.",
                                "tool": "generate_strategy",
                                "guidance": "After the user formulates a question, use 'generate_strategy'. The 'question' and 'columnAnalysis' are passed automatically."
                            },
                            {
                                "step": 4,
                                "description": "Create Configuration: Generate the dashboard configuration for user review.",
                                "tool": "create_configuration",
                                "guidance": "Use 'create_configuration' to generate the markdown configuration. The 'question', 'columnAnalysis', and 'strategy' are used from the cache. The tool returns 'markdownConfig'. Present this to the user for review and potential modification."
                            },
                            {
                                "step": 5,
                                "description": "Create Dashboard: Create the actual dashboard.",
                                "tool": "create_dashboard",
                                "guidance": "Use 'create_dashboard'. The 'markdownConfig' (potentially modified by the user) and 'sourceStructure' are used. This will return 'dashboardUrl' and 'chartConfigs'."
                            },
                            {
                                "step": 6,
                                "description": "Fetch Chart Data: Get the data for all charts in the dashboard.",
                                "tool": "get_charts_data",
                                "guidance": "Use 'get_charts_data'. The 'chartConfigs' from the previous step are used automatically. The tool returns a list of chart names for which data was found. Inform the user about the charts being analyzed."
                            },
                            {
                                "step": 7,
                                "description": "Generate Final Analysis: Generate AI insights for each chart and synthesize a final report.",
                                "tool": "analyze_charts",
                                "guidance": "Use 'analyze_charts' to get the detailed insights. This is the final tool call. After this, you must synthesize the returned insights, the cached strategy, and the original question into a comprehensive markdown report for the user, as per the tool's description. Present the final report and the 'dashboardUrl'."
                            }
                        ]
                    },
                    "important_notes": [
                        "All data returned in responses or used as inputs is automatically cached by the client - no need to repeat parameters in subsequent tool calls unless they've been modified.",
                        "The client automatically injects required parameters like 'apiUrl' and 'jwtToken' from the session.",
                        "Present technical information in user-friendly formats (e.g., use markdown tables for source structure).",
                        "Wait for user confirmation at key decision points (like source selection and configuration review)."
                    ]
                }
            }

            return jsonify({
                "tools": filtered_tools,
                "workflow_guidance": workflow_guidance
            })
        finally:
            # Always clean up the MCP manager after use
            try:
                mcp_manager.stop()
            except Exception as cleanup_e:
                print(f"[MCP CLIENT] Warning: Error cleaning up MCP manager: {cleanup_e}", flush=True)
                
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /tools error for session_id {data.get('session_id')}:", e, traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/call-tool', methods=['POST'])
def call_tool():
    """
    Call an MCP tool by name with parameters for a specific session.
    Injects JWT/apiUrl and other session params if required.
    Caches all outputs from successful tool calls into the session.
    Accepts JSON with session_id, tool, and params.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        tool_name = data.get('tool')
        
        # Ensure params is a dictionary
        params = data.get('params')
        if params is None:
            params = {}
        elif not isinstance(params, dict):
            return jsonify({"status": "error", "error": "params must be a dictionary"}), 400
        
        if not session_id or not tool_name:
             return jsonify({"status": "error", "error": "Missing session_id or tool name"}), 400
        
        # Get session data from Redis (automatically resets TTL)
        session_data = session_manager.get_session_data(session_id)
        if not session_data:
             return jsonify({"status": "error", "error": f"Session {session_id} not found or expired. Please run /init first."}), 409

        # Create MCP manager for this request
        mcp_manager = create_mcp_manager_for_request(session_id)
        if not mcp_manager:
             return jsonify({"status": "error", "error": f"Failed to initialize MCP server for session {session_id}."}), 500

        try:
            # 1. Standard injection of sensitive/session-wide parameters (LLM params take precedence if provided)
            for key in ("jwtToken", "apiUrl"):
                if key not in params and key in session_data: # Only inject if not provided by LLM
                    params[key] = session_data[key]

            # 2. Generic injection of other parameters from session cache if not provided by the LLM
            try:
                all_tool_schemas = mcp_manager.get_tool_schemas()
            except Exception as schema_e:
                print(f"[MCP CLIENT] Error fetching schemas for injection for session_id {session_id}: {schema_e}", flush=True)
                all_tool_schemas = []

            target_tool_schema = next((s for s in all_tool_schemas if s.get("name") == tool_name), None)

            if target_tool_schema:
                input_schema_props = target_tool_schema.get("inputSchema", {}).get("properties", {})
                for param_name in input_schema_props.keys():
                    if param_name not in params and param_name in session_data:
                        if param_name not in ("jwtToken", "apiUrl"):
                            print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' not in LLM call, injecting from session cache for session_id {session_id}.", flush=True)
                            params[param_name] = session_data[param_name]
                    elif param_name in params:
                        pass # Keep LLM provided value
            else:
                print(f"[MCP CLIENT] Warning: Could not find schema for tool '{tool_name}'. Skipping generic parameter injection for session_id {session_id}.", flush=True)

            # 3. Prepare updates for session cache (LLM-provided or client-injected parameters)
            cache_updates = {}
            for key, value in params.items():
                if key not in ("jwtToken", "apiUrl"):
                     try:
                         json.dumps(value)  # Test serializability
                         cache_updates[key] = value
                     except TypeError:
                          print(f"[MCP CLIENT] Warning: Parameter '{key}' for tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)

            # Update session cache with input parameters
            if cache_updates:
                session_manager.update_session_data(session_id, cache_updates)

            # Call the tool
            result = mcp_manager.call_tool(tool_name, params)

            # Cache all outputs from successful tool calls if the result is a dictionary
            if isinstance(result, dict):
                # Only cache on success status
                if result.get("status") == "success":
                    # Prepare output cache updates
                    output_cache_updates = {}
                    for key, value in result.items():
                        if key != "status": # Don't cache the status field itself
                            try:
                                json.dumps(value) # Check if serializable before caching
                                if key == "intermediate" and isinstance(value, dict):
                                    # For intermediate data, cache each nested field separately
                                    for nested_key, nested_value in value.items():
                                        try:
                                            json.dumps(nested_value) # Check nested serializability
                                            output_cache_updates[nested_key] = nested_value
                                        except TypeError:
                                            print(f"[MCP CLIENT] Warning: Nested intermediate key '{nested_key}' from tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)
                                else:
                                    # Cache non-intermediate fields as before
                                    output_cache_updates[key] = value
                            except TypeError:
                                print(f"[MCP CLIENT] Warning: Output key '{key}' from tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)
                    
                    # Update session cache with output data
                    if output_cache_updates:
                        session_manager.update_session_data(session_id, output_cache_updates)

                # Always create a filtered response without intermediate data if the result is a dict
                filtered_result = {k: v for k, v in result.items() if k != "intermediate"}
                print(f"[MCP CLIENT RESPONSE] /call-tool response for session_id {session_id}, tool {tool_name}: {json.dumps(filtered_result)}", flush=True)
                return jsonify(filtered_result)
            
            # If result is not a dictionary (e.g., simple type), return as is
            print(f"[MCP CLIENT RESPONSE] /call-tool response for session_id {session_id}, tool {tool_name}: {json.dumps(result)}", flush=True)
            return jsonify(result)
            
        except Exception as e:
            error_response = {"status": "error", "error": f"Error executing tool '{tool_name}': {str(e)}"}
            print(f"[MCP CLIENT RESPONSE] /call-tool error response for session_id {session_id}, tool {tool_name}: {json.dumps(error_response)}", flush=True)
            return jsonify(error_response), 500
        finally:
            # Always clean up the MCP manager after use
            try:
                mcp_manager.stop()
            except Exception as cleanup_e:
                print(f"[MCP CLIENT] Warning: Error cleaning up MCP manager: {cleanup_e}", flush=True)

    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /call-tool error for session_id {data.get('session_id', 'N/A')}:", e, traceback.format_exc(), flush=True)
        error_response = {"error": str(e)}
        print(f"[MCP CLIENT RESPONSE] /call-tool error response for session_id {data.get('session_id', 'N/A')}: {json.dumps(error_response)}", flush=True)
        return jsonify(error_response), 500

def run_server():
    """
    Run the Flask app using configuration from MCPConfig.
    Returns the port number actually used.
    """
    port = MCPConfig.Server.PORT
    host = MCPConfig.Server.HOST
    
    print(f"[MCP CLIENT] Flask server starting on {host}:{port}", flush=True)
    print(f"[MCP CLIENT] Session idle TTL: {MCPConfig.Session.IDLE_TTL}s", flush=True)
    print(f"[MCP CLIENT] Redis: {MCPConfig.Redis.HOST}:{MCPConfig.Redis.PORT}", flush=True)
    print(f"[MCP CLIENT] Architecture: Redis-only (stateless, multi-worker compatible)", flush=True)
    
    # Flask app.run is blocking, so this is the main loop for the process.
    app.run(host=host, port=port, threaded=True) # threaded=True allows handling multiple requests concurrently
    # Code after app.run() will only execute if the server stops without os._exit(0)
    print(f"[MCP CLIENT] Flask server stopped on {host}:{port}", flush=True)
    return port

if __name__ == '__main__':
    # In the application-wide client setup, this __main__ block is the entry point
    # for the subprocess launched by the main application startup code.
    port = run_server()
    print(f"[MCP CLIENT] HTTP server finished on port {port}") # This line might not be reached due to os._exit(0)
    sys.stdout.flush() 