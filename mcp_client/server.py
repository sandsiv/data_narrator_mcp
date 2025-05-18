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

# Store the time of the last activity for idle timeout
# This timeout will now apply to the entire MCP client process if no requests are received
last_activity = time.time()
IDLE_TIMEOUT = 3600  # 1 hour in seconds

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
        print(f"[MCP CLIENT] Created session data for session_id: {session_id}", flush=True)
    return session_data_map[session_id]

# Helper function to clear session data
def clear_session_data(session_id):
    if session_id in session_data_map:
        # Stop the session's MCP server subprocess before deleting
        try:
            session_data_map[session_id]['mcp_manager'].stop() # Use stop() method
            print(f"[MCP CLIENT] Stopped MCP server for session_id: {session_id}", flush=True)
        except Exception as e:
            print(f"[MCP CLIENT] Error stopping MCP server for session_id {session_id}: {e}", flush=True)
            
        del session_data_map[session_id]
        print(f"[MCP CLIENT] Cleared session data for session_id: {session_id}", flush=True)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    global last_activity
    last_activity = time.time()
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
    global last_activity
    last_activity = time.time()
    
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
    global last_activity
    last_activity = time.time()
    
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
    global last_activity
    last_activity = time.time()
    
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
        return jsonify({"tools": filtered_tools})
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
    global last_activity
    last_activity = time.time()

    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        tool_name = data.get('tool')
        params = data.get('params', {})
        
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
        # This requires knowing the tool's schema to identify expected parameters.
        # Note: Fetching tool schemas on every call is inefficient. Could cache this per session.
        try:
            all_tool_schemas = mcp_manager.get_tool_schemas() # Get schemas for this session's manager
        except Exception as schema_e:
            print(f"[MCP CLIENT] Error fetching schemas for injection for session_id {session_id}: {schema_e}", flush=True)
            # Proceed without schema injection if schemas can't be fetched
            all_tool_schemas = []

        target_tool_schema = next((s for s in all_tool_schemas if s.get("name") == tool_name), None)

        if target_tool_schema:
            input_schema_props = target_tool_schema.get("inputSchema", {}).get("properties", {})
            for param_name in input_schema_props.keys():
                if param_name not in params and param_name in session_params:
                    # Don't re-inject sensitive params if they were handled above or if they are explicitly SENSITIVE_PARAMS (already filtered from LLM view)
                    # This also avoids injecting them if they were NOT in session_params during step 1 but are now in session_params from a previous tool's output.
                    if param_name not in ("jwtToken", "apiUrl"):
                        print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' not in LLM call, injecting from session cache for session_id {session_id}.", flush=True)
                        params[param_name] = session_params[param_name]
                elif param_name in params:
                    # print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' provided in LLM call, using explicit value for session_id {session_id}.", flush=True)
                    pass # Keep LLM provided value
        else:
            print(f"[MCP CLIENT] Warning: Could not find schema for tool '{tool_name}'. Skipping generic parameter injection for session_id {session_id}.", flush=True)

        # 3. Cache all current parameters (LLM-provided or client-injected) before calling the tool.
        # This makes LLM-provided inputs (and client-injected values) available for subsequent, different tool calls if not overridden.
        # print(f"[MCP CLIENT] Caching current input parameters for tool '{tool_name}' before execution for session_id {session_id}.", flush=True)
        for key, value in params.items():
            # jwtToken and apiUrl are primarily managed via /init and Step 1 injection.
            # We cache other LLM-provided or client-injected values here, ensuring they are serializable.
            # Basic types are generally serializable; complex objects might cause issues.
            if key not in ("jwtToken", "apiUrl"): # Don't overwrite init params from tool calls
                 try:
                     # Attempt to JSON serialize the value to check if it's cacheable
                     json.dumps(value)
                     session_data['session_params'][key] = value
                     # print(f"[MCP CLIENT] Cached input param '{key}' into session cache for session_id {session_id}.", flush=True)
                 except TypeError:
                      print(f"[MCP CLIENT] Warning: Parameter '{key}' for tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)

        try:
            result = mcp_manager.call_tool(tool_name, params)

            # 4. Automatic caching of all outputs from successful tool calls
            if isinstance(result, dict) and result.get("status") == "success":
                # print(f"[MCP CLIENT] Caching outputs from successful call to tool '{tool_name}' for session_id {session_id}.", flush=True)
                for key, value in result.items():
                    if key != "status": # Don't cache the status field itself
                         try:
                             # Attempt to JSON serialize the value before caching output
                             json.dumps(value)
                             session_data['session_params'][key] = value
                             # print(f"[MCP CLIENT] Cached '{key}' from '{tool_name}' output into session cache for session_id {session_id}.", flush=True)
                         except TypeError:
                              print(f"[MCP CLIENT] Warning: Output key '{key}' from tool '{tool_name}' is not JSON serializable. Not caching for session_id {session_id}.", flush=True)

            return jsonify(result)
            
        except Exception as e:
            # Basic error handling for the tool call itself
            print(f"[MCP CLIENT] Error calling tool '{tool_name}' for session_id {session_id}: {e}", flush=True)
            return jsonify({"status": "error", "error": f"Error executing tool '{tool_name}': {str(e)}"}), 500

    except Exception as e:
        import traceback
        print(f"[MCP CLIENT] /call-tool error for session_id {data.get('session_id', 'N/A')}:", e, traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500

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

    # Start idle timeout monitor in a background thread
    # This timeout now applies to inactivity for *any* session.
    def idle_monitor():
        while True:
            time.sleep(10)
            # Check overall last activity timestamp
            if time.time() - last_activity > IDLE_TIMEOUT:
                print("[MCP CLIENT] Idle timeout reached. Shutting down.", flush=True)
                
                # Optionally, iterate through sessions and stop their managers gracefully first
                # for sid in list(session_data_map.keys()): # Iterate over a copy of keys
                #     try:
                #         session_data_map[sid]['mcp_manager'].stop()
                #         print(f"[MCP CLIENT] Stopped MCP server for session_id {sid} due to idle timeout.", flush=True)
                #     except Exception as e:
                #         print(f"[MCP CLIENT] Error stopping MCP server for session_id {sid} during idle shutdown: {e}", flush=True)
                # session_data_map.clear() # Clear all session data map

                os._exit(0)  # Force exit from any thread (main Flask process)

    threading.Thread(target=idle_monitor, daemon=True).start()

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