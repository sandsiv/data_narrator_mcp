import os
import sys
import threading
import time
from flask import Flask, jsonify, request
import socket
from mcp_client.manager import MCPServerManager
import copy

# Create Flask app
app = Flask(__name__)

# Store the time of the last activity for idle timeout
last_activity = time.time()
IDLE_TIMEOUT = 3600  # 1 hour in seconds

# Store session parameters in memory (not persisted)
session_params = {}

# Global MCP server manager instance
mcp_manager = MCPServerManager()

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

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    global last_activity
    last_activity = time.time()
    return jsonify({"status": "ok"})

@app.route('/init', methods=['POST'])
def init():
    """
    Initialize the MCP client session. Accepts JSON with JWT and other params.
    Stores them in memory for this session only.
    Returns the port number and status.
    """
    global last_activity
    last_activity = time.time()
    data = request.get_json(force=True)
    # Store all params in memory (never log or expose JWT)
    session_params.clear()
    session_params.update(data)
    # Start MCP server manager with environment if needed
    mcp_manager.start()
    # Return port (Flask doesn't expose it directly, so use environ)
    port = request.environ.get('SERVER_PORT', None)
    return jsonify({"status": "ok", "port": port})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Cleanly shut down the MCP client and server subprocess.
    """
    global last_activity
    last_activity = time.time()
    print("[MCP CLIENT] Shutdown requested, exiting...", flush=True)
    os._exit(0)

@app.route('/tools', methods=['GET'])
def list_tools():
    """
    List available MCP tools with full schema for LLM use,
    filtering out sensitive parameters.
    """
    global last_activity
    last_activity = time.time()
    try:
        tools = mcp_manager.get_tool_schemas()
        # Filter each tool schema
        filtered_tools = [filter_tool_schema(tool) for tool in tools]
        return jsonify({"tools": filtered_tools})
    except Exception as e:
        import traceback
        print("[MCP CLIENT] /tools error:", e, traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/call-tool', methods=['POST'])
def call_tool():
    """
    Call an MCP tool by name with parameters.
    Injects JWT/apiUrl from session_params if required.
    Injects other parameters from session cache if they are expected by the tool and not provided by the LLM.
    Caches all outputs from successful tool calls into the session.
    """
    global last_activity
    last_activity = time.time()
    data = request.get_json(force=True)
    tool_name = data.get('tool')
    params = data.get('params', {})

    # 1. Standard injection of sensitive/session-wide parameters (LLM params take precedence if provided)
    for key in ("jwtToken", "apiUrl"):
        if key not in params and key in session_params: # Only inject if not provided by LLM
            params[key] = session_params[key]

    # 2. Generic injection of other parameters from cache if not provided by LLM
    # This requires knowing the tool's schema to identify expected parameters.
    all_tool_schemas = mcp_manager.get_tool_schemas() # Assumes this returns a list of full schemas
    target_tool_schema = next((s for s in all_tool_schemas if s.get("name") == tool_name), None)

    if target_tool_schema:
        input_schema_props = target_tool_schema.get("inputSchema", {}).get("properties", {})
        for param_name in input_schema_props.keys():
            if param_name not in params and param_name in session_params:
                # Don't re-inject sensitive params if they were handled above or if they are explicitly SENSITIVE_PARAMS (already filtered from LLM view)
                # This also avoids injecting them if they were NOT in session_params during step 1 but are now in session_params from a previous tool's output.
                if param_name not in ("jwtToken", "apiUrl"):
                    print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' not in LLM call, injecting from session cache.", flush=True)
                    params[param_name] = session_params[param_name]
            elif param_name in params:
                print(f"[MCP CLIENT] Parameter '{param_name}' for tool '{tool_name}' provided in LLM call, using explicit value.", flush=True)
    else:
        print(f"[MCP CLIENT] Warning: Could not find schema for tool '{tool_name}'. Skipping generic parameter injection.", flush=True)

    # 3. Cache all current parameters (LLM-provided or client-injected) before calling the tool.
    # This makes LLM-provided inputs (and client-injected values) available for subsequent, different tool calls if not overridden.
    print(f"[MCP CLIENT] Caching current input parameters for tool '{tool_name}' before execution.", flush=True)
    for key, value in params.items():
        # jwtToken and apiUrl are primarily managed via /init and Step 1 injection.
        # We cache other LLM-provided or client-injected values here.
        if key not in ("jwtToken", "apiUrl"):
             session_params[key] = value
             print(f"[MCP CLIENT] Cached input param '{key}' into session.", flush=True)
        # else: jwtToken & apiUrl are already in session_params from /init or just injected by Step 1;
        # no need to re-cache them here unless LLM explicitly provided them, which is against the desired flow.

    try:
        result = mcp_manager.call_tool(tool_name, params)

        # 4. Automatic caching of all outputs from successful tool calls (renumbered step)
        if isinstance(result, dict) and result.get("status") == "success":
            print(f"[MCP CLIENT] Caching outputs from successful call to tool '{tool_name}'.", flush=True)
            for key, value in result.items():
                if key != "status": # Don't cache the status field itself
                    session_params[key] = value
                    print(f"[MCP CLIENT] Cached '{key}' from '{tool_name}' output into session.", flush=True)
        
        return jsonify(result)
    except Exception as e:
        import traceback
        print("[MCP CLIENT] /call-tool error:", e, traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500

def run_server():
    """
    Run the Flask app on a dynamic port (port=0 lets the OS pick a free port),
    or a fixed port if MCP_CLIENT_PORT is set in the environment.
    Returns the port number actually used.
    """
    port = int(os.environ.get("MCP_CLIENT_PORT", 0))
    if port == 0:
        # Create a socket to find a free port
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()

    # Start idle timeout monitor in a background thread
    def idle_monitor():
        while True:
            time.sleep(10)
            if time.time() - last_activity > IDLE_TIMEOUT:
                print("[MCP CLIENT] Idle timeout reached. Shutting down.")
                os._exit(0)  # Force exit from any thread

    threading.Thread(target=idle_monitor, daemon=True).start()

    print(f"[MCP CLIENT] Flask server thread starting on port {port}", flush=True)
    app.run(host='127.0.0.1', port=port, threaded=True)
    return port

if __name__ == '__main__':
    port = run_server()
    print(f"[MCP CLIENT] HTTP server started on port {port}")
    sys.stdout.flush() 