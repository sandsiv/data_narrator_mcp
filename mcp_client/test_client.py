import subprocess
import requests
import time
import json
import os
import threading
from dotenv import load_dotenv
load_dotenv()

# Configuration (replace with real values or load from .env)
API_URL = os.getenv("apiUrl", "http://example.com/api")
JWT_TOKEN = os.getenv("jwtToken", "test-jwt-token")
SOURCE_ID = os.getenv("sourceId", "test-source-id")
QUESTION = os.getenv("question", "What are the top sales?")

client_proc = subprocess.Popen([
    "python", "-u", "-m", "mcp_client"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Read lines from stdout until we see the port
port = None
for _ in range(50):
    line = client_proc.stdout.readline()
    print("[MCP CLIENT OUT]", line, end="")
    if "Flask server thread starting on port" in line:
        port = int(line.strip().split()[-1])
        break
    time.sleep(0.1)
if not port:
    print("Failed to detect MCP client port.")
    client_proc.terminate()
    exit(1)

base_url = f"http://127.0.0.1:{port}"

try:
    # Wait for /health to respond (server readiness)
    for _ in range(30):
        try:
            resp = requests.get(f"{base_url}/health", timeout=0.5)
            if resp.status_code == 200:
                print("[MCP CLIENT] /health responded OK")
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        print("MCP client did not respond to /health in time.")
        client_proc.terminate()
        exit(1)

    def print_subprocess_output(proc):
        for line in proc.stdout:
            print("[MCP CLIENT OUT]", line, end="")
        for line in proc.stderr:
            print("[MCP CLIENT ERR]", line, end="")

    threading.Thread(target=print_subprocess_output, args=(client_proc,), daemon=True).start()

    # 1. POST /init
    print("\n[TEST] /init ...")
    resp = requests.post(f"{base_url}/init", json={
        "apiUrl": API_URL,
        "jwtToken": JWT_TOKEN,
        "sourceId": SOURCE_ID,
        "question": QUESTION
    })
    print("Result:", resp.json())

    # 2. GET /tools
    print("\n[TEST] /tools ...")
    resp = requests.get(f"{base_url}/tools")
    print("Result:", resp.json())

    # 3. POST /call-tool (list_sources)
    print("\n[TEST] /call-tool (list_sources) ...")
    resp = requests.post(f"{base_url}/call-tool", json={
        "tool": "list_sources",
        "params": {}
    })
    try:
        print("Result:", json.dumps(resp.json(), indent=2))
    except Exception:
        print("Raw result:", resp.text)

    # 4. POST /shutdown
    print("\n[TEST] /shutdown ...")
    try:
        resp = requests.post(f"{base_url}/shutdown")
        print("Result:", resp.json())
    except requests.exceptions.ConnectionError as e:
        print("[TEST] MCP client shutdown: connection closed (expected if process exited immediately)")

    # Wait for process to exit
    client_proc.wait(timeout=10)
    print("\n[MCP CLIENT] Process exited.")
finally:
    # Ensure the subprocess is terminated
    if client_proc.poll() is None:
        print("[TEST] Terminating MCP client subprocess...")
        client_proc.terminate()
        try:
            client_proc.wait(timeout=5)
        except Exception:
            client_proc.kill() 