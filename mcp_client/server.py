import os
import sys
import threading
import time
from flask import Flask, jsonify, request
import socket
from mcp_client.manager import MCPServerManager
import copy
import json

# Dictionary to store session-specific data, keyed by session_id
session_data_map = {}

# Create Flask app
app = Flask(__name__)

# We no longer need a single global mcp_manager or session_params
# session_params = {}
# mcp_manager = MCPServerManager()

# Configurable list of sensitive parameter names to filter out
SENSITIVE_PARAMS = os.getenv("MCP_SENSITIVE_PARAMS", "apiUrl,jwtToken").split(",")

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

# Helper function to get or create session data
def get_or_create_session_data(session_id):
    if session_id not in session_data_map:
        session_data_map[session_id] = {
            'mcp_manager': MCPServerManager(),
            'session_params': {}
        }
    return session_data_map[session_id]

# Helper function to clear session data
def clear_session_data(session_id):
    if session_id in session_data_map:
        try:
            session_data_map[session_id]['mcp_manager'].stop()
        except Exception as e:
            print(f"[ERROR] Failed to stop MCP server for session_id {session_id}: {e}", flush=True)
        del session_data_map[session_id]

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    # This endpoint doesn't need session_id
    return jsonify({"status": "ok"})

@app.route('/init', methods=['POST'])
def init():
    """
    Initialize the MCP client session.
    Accepts JSON with session_id, apiUrl, jwtToken, and other params.
    Stores them in memory per session and starts the per-session MCP server subprocess.
    Returns status.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        apiUrl = data.get('apiUrl')
        jwtToken = data.get('jwtToken')
        
        if not session_id or not apiUrl or not jwtToken:
            return jsonify({"status": "error", "error": "Missing session_id, apiUrl, or jwtToken"}), 400

        session_data = get_or_create_session_data(session_id)
        
        # Store API credentials and any other init params in session-specific memory
        session_data['session_params'].clear() # Clear previous session params
        session_data['session_params'].update(data) # Store all init data
        
        # Start the per-session MCP server manager
        # Pass API credentials to the manager if needed during its start
        try:
            session_data['mcp_manager'].start() # Manager starts the subprocess for this session
            print(f"[MCP CLIENT] MCP Manager started for session_id: {session_id}", flush=True)
        except Exception as mgr_e:
             print(f"[MCP CLIENT] Error starting MCP Manager for session_id {session_id}: {mgr_e}", flush=True)
             clear_session_data(session_id) # Clean up on manager start failure
             return jsonify({"status": "error", "error": f"Failed to start MCP server for session: {mgr_e}"}), 500

        return jsonify({"status": "ok"})
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /init error for session_id {data.get('session_id')}:", e, traceback.format_exc(), flush=True)
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Cleanly shut down the MCP client *session* and its server subprocess.
    Accepts JSON with session_id.
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')

        clear_session_data(session_id) # This stops the manager and clears data

        return jsonify({"status": "ok", "message": f"Session {session_id} shut down."})
    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /shutdown error for session_id {data.get('session_id', 'N/A')}:", e, traceback.format_exc(), flush=True)
        # Even on error, try to clear session data
        try:
            if 'session_id' in locals() and session_id in session_data_map:
                 del session_data_map[session_id]
        except Exception:
             pass # Ignore errors during cleanup attempt
        return jsonify({"status": "error", "error": str(e)}), 500

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
            
        session_data = session_data_map.get(session_id)
        if not session_data or not session_data['mcp_manager'].session:
            # Check if manager session is ready before allowing tool listing
            return jsonify({"status": "error", "error": f"MCP server not initialized or ready for session {session_id}. Please run /init first."}), 409 # Conflict

        mcp_manager = session_data['mcp_manager']

        tools = mcp_manager.get_tool_schemas()
        # Filter each tool schema
        filtered_tools = [filter_tool_schema(tool) for tool in tools]

        # Add general workflow guidance for LLMs
        workflow_guidance = {
            "workflow": {
                "description": "This is a data analysis workflow that helps users analyze data sources and generate insights. The workflow has two main paths: one-shot analysis and step-by-step analysis.",
                "steps": [
                    {
                        "step": 1,
                        "description": "Source Selection",
                        "guidance": "First, ask the user for a source name or part of a name to search. Use the 'list_sources' tool with the search parameter to find matching sources. Present the results to the user and ask them to select a specific source by its ID.",
                        "tool": "list_sources"
                    },
                    {
                        "step": 2,
                        "description": "Source Structure Review",
                        "guidance": "After source selection, use 'get_source_structure' to fetch detailed information about the source's columns and data types. Present this information to the user in a user-friendly format (e.g., markdown table). This helps users understand what data is available for analysis.",
                        "tool": "get_source_structure"
                    },
                    {
                        "step": 3,
                        "description": "Question Formulation",
                        "guidance": "Based on the source structure, help the user formulate a clear analytical question. Suggest possible questions that would have business value given the available data. Once the user provides their question, ask if they prefer: a) One-shot analysis (direct answer) or b) Step-by-step analysis (with configuration review).",
                        "tools": ["analyze_source_question", "prepare_analysis_configuration"]
                    },
                    {
                        "step": 4,
                        "description": "Analysis Path Selection",
                        "guidance": "Based on user preference: a) For one-shot analysis: Use 'analyze_source_question' to get direct results and inform user that it would take time to generate the results.. b) For step-by-step: Use 'prepare_analysis_configuration' to generate a dashboard configuration for review.",
                        "tools": ["analyze_source_question", "prepare_analysis_configuration"]
                    },
                    {
                        "step": 5,
                        "description": "Configuration Review (Step-by-Step Only)",
                        "guidance": "If using step-by-step analysis, present the generated dashboard configuration to the user in markdown format. Wait for their confirmation or modifications. If they make changes, use the modified configuration in the next step. If they confirm proposed configuration, don't add it to parameters in next call, it will use cached value",
                        "tool": "prepare_analysis_configuration"
                    },
                    {
                        "step": 6,
                        "description": "Analysis Execution",
                        "guidance": "a) For one-shot: Results are already available. b) For step-by-step: Use 'execute_analysis_from_config' with the confirmed/modified configuration to generate the final results. Inform user that it would take time to generate the results.",
                        "tools": ["analyze_source_question", "execute_analysis_from_config"]
                    },
                    {
                        "step": 7,
                        "description": "Results Presentation",
                        "guidance": "Present the final results to the user, including: 1) A clear summary of insights, 2) A link to the interactive dashboard, 3) Any relevant intermediate results if requested.",
                        "tools": ["analyze_source_question", "execute_analysis_from_config"]
                    }
                ],
                "important_notes": [
                    "All data returned in responses or used as inputs is automatically cached - no need to repeat parameters in subsequent tool calls unless they've been modified",
                    "Present technical information in user-friendly formats",
                    "Wait for user confirmation at key decision points",
                    "Offer suggestions and guidance based on the data structure"
                ]
            }
        }

        return jsonify({
            "tools": filtered_tools,
            "workflow_guidance": workflow_guidance
        })
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
        
        session_data = session_data_map.get(session_id)
        if not session_data or not session_data['mcp_manager'].session:
             return jsonify({"status": "error", "error": f"MCP server not initialized or ready for session {session_id}. Please run /init first."}), 409 # Conflict

        mcp_manager = session_data['mcp_manager']
        session_params = session_data['session_params']

        # 1. Standard injection of sensitive/session-wide parameters (LLM params take precedence if provided)
        for key in ("jwtToken", "apiUrl"):
            if key not in params and key in session_params: # Only inject if not provided by LLM
                params[key] = session_params[key]

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
                if param_name not in params and param_name in session_params:
                    if param_name not in ("jwtToken", "apiUrl"):
                        print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' not in LLM call, injecting from session cache for session_id {session_id}.", flush=True)
                        params[param_name] = session_params[param_name]
                elif param_name in params:
                    pass # Keep LLM provided value
        else:
            print(f"[MCP CLIENT] Warning: Could not find schema for tool '{tool_name}'. Skipping generic parameter injection for session_id {session_id}.", flush=True)

        # 3. Cache all current parameters (LLM-provided or client-injected) before calling the tool.
        for key, value in params.items():
            if key not in ("jwtToken", "apiUrl"):
                 try:
                     json.dumps(value)
                     session_data['session_params'][key] = value
                 except TypeError:
                      print(f"[MCP CLIENT] Warning: Parameter '{key}' for tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)

        try:
            result = mcp_manager.call_tool(tool_name, params)

            # 4. Automatic caching of all outputs from successful tool calls
            if isinstance(result, dict) and result.get("status") == "success":
                # Cache everything including intermediate data
                for key, value in result.items():
                    if key != "status": # Don't cache the status field itself
                        try:
                            json.dumps(value)
                            if key == "intermediate" and isinstance(value, dict):
                                # For intermediate data, cache each nested field separately
                                for nested_key, nested_value in value.items():
                                    try:
                                        json.dumps(nested_value)
                                        session_data['session_params'][nested_key] = nested_value
                                    except TypeError:
                                        print(f"[MCP CLIENT] Warning: Nested intermediate key '{nested_key}' from tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)
                            else:
                                # Cache non-intermediate fields as before
                                session_data['session_params'][key] = value
                        except TypeError:
                            print(f"[MCP CLIENT] Warning: Output key '{key}' from tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)

                # Create a filtered response without intermediate data
                filtered_result = {k: v for k, v in result.items() if k != "intermediate"}
                print(f"[MCP CLIENT RESPONSE] /call-tool response for session_id {session_id}, tool {tool_name}: {json.dumps(filtered_result)}", flush=True)
                return jsonify(filtered_result)
            
            print(f"[MCP CLIENT RESPONSE] /call-tool response for session_id {session_id}, tool {tool_name}: {json.dumps(result)}", flush=True)
            return jsonify(result)
            
        except Exception as e:
            error_response = {"status": "error", "error": f"Error executing tool '{tool_name}': {str(e)}"}
            print(f"[MCP CLIENT RESPONSE] /call-tool error response for session_id {session_id}, tool {tool_name}: {json.dumps(error_response)}", flush=True)
            return jsonify(error_response), 500

    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /call-tool error for session_id {data.get('session_id', 'N/A')}:", e, traceback.format_exc(), flush=True)
        error_response = {"error": str(e)}
        print(f"[MCP CLIENT RESPONSE] /call-tool error response for session_id {data.get('session_id', 'N/A')}: {json.dumps(error_response)}", flush=True)
        return jsonify(error_response), 500

def run_server():
    """
    Run the Flask app on a dynamic port (port=0 lets the OS pick a free port),
    or a fixed port if MCP_CLIENT_PORT is set in the environment.
    Returns the port number actually used.
    """
    # Now that the port is set in config.py, the application startup code
    # should ensure MCP_CLIENT_PORT env var is set before launching this script,
    # or modify this to read from a config file directly if env var isn't preferred.
    port = int(os.environ.get("MCP_CLIENT_PORT", 0))
    if port == 0:
         # This fallback for dynamic port might still be useful for testing,
         # but in production with the application-wide client, a fixed port is expected.
        print("[MCP CLIENT] MCP_CLIENT_PORT environment variable not set, finding a dynamic port.", flush=True)
        # Create a socket to find a free port
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()

    print(f"[MCP CLIENT] Flask server starting on port {port}", flush=True)
    # Flask app.run is blocking, so this is the main loop for the process.
    app.run(host='127.0.0.1', port=port, threaded=True) # threaded=True allows handling multiple requests concurrently
    # Code after app.run() will only execute if the server stops without os._exit(0)
    print(f"[MCP CLIENT] Flask server stopped on port {port}", flush=True)
    return port

if __name__ == '__main__':
    # In the application-wide client setup, this __main__ block is the entry point
    # for the subprocess launched by the main application startup code.
    port = run_server()
    print(f"[MCP CLIENT] HTTP server finished on port {port}") # This line might not be reached due to os._exit(0)
    sys.stdout.flush() 