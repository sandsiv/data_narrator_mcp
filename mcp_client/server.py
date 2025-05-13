import os
import sys
import threading
import time
from flask import Flask, jsonify, request
import socket
from mcp_client.manager import MCPServerManager

# Create Flask app
app = Flask(__name__)

# Store the time of the last activity for idle timeout
last_activity = time.time()
IDLE_TIMEOUT = 3600  # 1 hour in seconds

# Store session parameters in memory (not persisted)
session_params = {}

# Global MCP server manager instance
mcp_manager = MCPServerManager()

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
    List available MCP tools.
    """
    global last_activity
    last_activity = time.time()
    try:
        tools = mcp_manager.list_tools()
        return jsonify({"tools": tools})
    except Exception as e:
        import traceback
        print("[MCP CLIENT] /tools error:", e, traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/call-tool', methods=['POST'])
def call_tool():
    """
    Call an MCP tool by name with parameters.
    Inject JWT/apiUrl from session_params if required by the tool.
    """
    global last_activity
    last_activity = time.time()
    data = request.get_json(force=True)
    tool = data.get('tool')
    params = data.get('params', {})
    for key in ("jwtToken", "apiUrl"):
        if key in session_params and key not in params:
            params[key] = session_params[key]
    try:
        result = mcp_manager.call_tool(tool, params)
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