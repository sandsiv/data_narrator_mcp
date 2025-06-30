#!/usr/bin/env python3
"""
Entry point for starting the MCP server
"""

import sys
import os

# Add the src/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import and run the MCP server
def main():
    """Entry point for the MCP server"""
    import subprocess
    import sys
    import os
    
    # Get the path to the MCP server file
    server_file = os.path.join(os.path.dirname(__file__), '..', 'insight_digger_mcp', 'mcp_server', 'server.py')
    server_file = os.path.abspath(server_file)
    
    # Run the MCP server using mcp run
    venv_bin = os.path.dirname(sys.executable)
    mcp_cmd = os.path.join(venv_bin, "mcp")
    
    try:
        subprocess.run([mcp_cmd, "run", server_file], check=True)
    except subprocess.CalledProcessError as e:
        print(f"MCP Server failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("MCP Server shutting down...")

if __name__ == '__main__':
    main() 