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
        "jwtToken": JWT_TOKEN
    })
    init_response = resp.json()
    print("Result:", init_response)
    if init_response.get("status") != "ok":
        print("Error during /init, aborting test.")
        client_proc.terminate()
        exit(1)

    # 2. GET /tools
    print("\n[TEST] /tools ...")
    resp = requests.get(f"{base_url}/tools")
    tools_json = resp.json()
    print("Result:", tools_json)

    # Show what LLM would get for tool descriptions
    print("\n[LLM TOOL DESCRIPTIONS JSON]\n" + json.dumps(tools_json, indent=2))

    # 3. POST /call-tool (list_sources)
    print("\n[TEST] /call-tool (list_sources with search) ...")
    list_sources_payload = {
        "tool": "list_sources",
        "params": {"search": "[20230110] Detect Detractor Model", "limit": 1}
    }
    print("Sending payload:", json.dumps(list_sources_payload, indent=2))
    resp = requests.post(f"{base_url}/call-tool", json=list_sources_payload)
    
    source_id_to_use = None
    try:
        list_sources_result = resp.json()
        print("Result:", json.dumps(list_sources_result, indent=2))
        if resp.status_code == 200 and isinstance(list_sources_result.get("data"), list) and list_sources_result["data"]:
            source_id_to_use = list_sources_result["data"][0].get("id")
            print(f"Extracted sourceId: {source_id_to_use}")
        elif isinstance(list_sources_result.get("data"), list) and not list_sources_result["data"]:
             print("No sources found matching the search criteria (data array is empty).")
        else:
            print(f"list_sources call failed (status {resp.status_code}) or returned unexpected structure.")
            print("Response content:", list_sources_result)
    except Exception as e:
        print("Raw result (list_sources):", resp.text)
        print(f"Error processing list_sources response: {e}")

    if not source_id_to_use:
        print("Cannot proceed without a sourceId. Terminating test.")
    else:
        # 4. POST /call-tool (prepare_analysis_configuration)
        print("\n[TEST] /call-tool (prepare_analysis_configuration) ...")
        prepare_payload = {
            "tool": "prepare_analysis_configuration",
            "params": {
                "sourceId": source_id_to_use,
                "question": QUESTION
            }
        }
        print("Sending payload:", json.dumps(prepare_payload, indent=2))
        resp = requests.post(f"{base_url}/call-tool", json=prepare_payload)
        
        markdown_config_to_use = None
        try:
            prepare_result = resp.json()
            print("Result:", json.dumps(prepare_result, indent=2))
            if prepare_result.get("status") == "success":
                markdown_config_to_use = prepare_result.get("markdownConfig")
                print(f"Extracted markdownConfig (first 100 chars): {markdown_config_to_use[:100] if markdown_config_to_use else 'None'}...")
            else:
                print("prepare_analysis_configuration call was not successful.")
        except Exception as e:
            print("Raw result (prepare_analysis_configuration):", resp.text)
            print(f"Error processing prepare_analysis_configuration response: {e}")

        if not markdown_config_to_use:
            print("Cannot proceed without markdownConfig. Terminating test.")
        else:
            # 5. POST /call-tool (execute_analysis_from_config)
            print("\n[TEST] /call-tool (execute_analysis_from_config) ...")
            execute_payload = {
                "tool": "execute_analysis_from_config",
                "params": {
                    "markdownConfig": markdown_config_to_use
                }
            }
            print("Sending payload:", json.dumps(execute_payload, indent=2))
            resp = requests.post(f"{base_url}/call-tool", json=execute_payload)
            try:
                execute_result = resp.json()
                print("Result:", json.dumps(execute_result, indent=2))
            except Exception as e:
                print("Raw result (execute_analysis_from_config):", resp.text)
                print(f"Error processing execute_analysis_from_config response: {e}")

    # 6. POST /shutdown
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