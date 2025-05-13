from mcp_client.server import run_server
 
if __name__ == '__main__':
    port = run_server()
    print(f"[MCP CLIENT] HTTP server started on port {port}") 