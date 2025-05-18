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
# --- New Configuration ---
# The test client now expects the server to be running on a fixed port
# Set MCP_CLIENT_PORT environment variable before running the test
PORT = int(os.getenv("MCP_CLIENT_PORT", 33000)) # Default to 33000 if env var not set
SESSION_ID = os.getenv("SESSION_ID", "test-session-123") # Unique ID for this test run
# --- End New Configuration ---

# We no longer start/stop the server process from the test client itself.
# Assume the server is already running as a service on the specified PORT.
base_url = f"http://127.0.0.1:{PORT}"

# Helper to print server output (optional, requires server to be run with tee or similar)
# In a service setup, you'd typically view logs via systemd-journald or log files
# def print_subprocess_output(proc):
#     for line in proc.stdout:
#         print("[MCP CLIENT OUT]", line, end="")
#     for line in proc.stderr:
#         print("[MCP CLIENT ERR]", line, end="")

try:
    # Wait for /health to respond (server readiness)
    print(f"[TEST] Waiting for server on port {PORT} to respond...")
    for _ in range(30):
        try:
            resp = requests.get(f"{base_url}/health", timeout=0.5)
            if resp.status_code == 200:
                print("[MCP CLIENT] /health responded OK")
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        print(f"MCP client server did not respond to /health on port {PORT} in time. Is it running?")
        exit(1)

    # 1. POST /init for a specific session
    print(f"\n[TEST] /init for session {SESSION_ID}...")
    init_payload = {
        "session_id": SESSION_ID,
        "apiUrl": API_URL,
        "jwtToken": JWT_TOKEN
    }
    resp = requests.post(f"{base_url}/init", json=init_payload)
    init_response = resp.json()
    print("Result:", init_response)
    if init_response.get("status") != "ok":
        print("Error during /init, aborting test.")
        exit(1)

    # 2. POST /tools for the specific session
    # Changed to POST to send session_id
    print(f"\n[TEST] /tools for session {SESSION_ID}...")
    tools_payload = {"session_id": SESSION_ID}
    resp = requests.post(f"{base_url}/tools", json=tools_payload)
    tools_json = resp.json()
    print("Result:", tools_json)

    # Show what LLM would get for tool descriptions
    print("\n[LLM TOOL DESCRIPTIONS JSON]\n" + json.dumps(tools_json, indent=2))

    # 3. POST /call-tool (list_sources) for the specific session
    print(f"\n[TEST] /call-tool (list_sources with search) for session {SESSION_ID}...")
    list_sources_payload = {
        "session_id": SESSION_ID, # Add session_id
        "tool": "list_sources",
        "params": {"search": "[20230110] Detect Detractor Model", "limit": 1}
    }
    print("Sending payload:", json.dumps(list_sources_payload, indent=2))
    resp = requests.post(f"{base_url}/call-tool", json=list_sources_payload)

    source_id_to_use = None
    try:
        list_sources_result = resp.json()
        print("Result:", json.dumps(list_sources_result, indent=2))
        # Assuming status=success and data array is present and not empty for success
        if resp.status_code == 200 and isinstance(list_sources_result.get("data"), list) and list_sources_result["data"]:
            source_id_to_use = list_sources_result["data"][0].get("id")
            print(f"Extracted sourceId: {source_id_to_use}")
        elif isinstance(list_sources_result.get("data"), list) and not list_sources_result["data"]:
             print("No sources found matching the search criteria (data array is empty).")
        else:
            print(f"list_sources call failed (status {resp.status_code}) or returned unexpected structure.")
            # print("Response content:", list_sources_result) # Avoid printing large response again

    except Exception as e:
        print("Raw result (list_sources):", resp.text)
        print(f"Error processing list_sources response: {e}")

    if not source_id_to_use:
        print("\nWarning: Cannot proceed with analysis tests without a sourceId from list_sources.")
    else:
        # 4. POST /call-tool (prepare_analysis_configuration) for the specific session
        print(f"\n[TEST] /call-tool (prepare_analysis_configuration) for session {SESSION_ID}...")
        prepare_payload = {
            "session_id": SESSION_ID, # Add session_id
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
                # print(f"Extracted markdownConfig (first 100 chars): {markdown_config_to_use[:100] if markdown_config_to_use else 'None'}...")
            else:
                print("prepare_analysis_configuration call was not successful.")
        except Exception as e:
            print("Raw result (prepare_analysis_configuration):", resp.text)
            print(f"Error processing prepare_analysis_configuration response: {e}")

        if not markdown_config_to_use:
            print("\nWarning: Cannot proceed with execute_analysis_from_config test without markdownConfig.")
        else:
            # 5. POST /call-tool (execute_analysis_from_config) for the specific session
            print(f"\n[TEST] /call-tool (execute_analysis_from_config) for session {SESSION_ID}...")
            execute_payload = {
                "session_id": SESSION_ID, # Add session_id
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

    # --- New Test Case: Call with Invalid Session ID ---
    print("\n[TEST] Call /tools with invalid session ID...")
    invalid_session_id = "invalid-session-xyz"
    invalid_tools_payload = {"session_id": invalid_session_id}
    resp = requests.post(f"{base_url}/tools", json=invalid_tools_payload)
    print("Result:", resp.json())
    if resp.status_code == 400: # Or 404/409 depending on desired API behavior; code uses 400 if missing, 409 if not initialized
        print("PASS: Received expected error for invalid session ID.")
    else:
        print(f"FAIL: Expected status 400/409 for invalid session ID, but got {resp.status_code}.")
    # --- End New Test Case ---


    # 6. POST /shutdown for the specific session
    print(f"\n[TEST] /shutdown for session {SESSION_ID}...")
    shutdown_payload = {"session_id": SESSION_ID} # Add session_id
    resp = requests.post(f"{base_url}/shutdown", json=shutdown_payload)
    print("Result:", resp.json())
    if resp.status_code == 200 and resp.json().get("status") == "ok":
        print("PASS: Session shut down successfully.")
    else:
         print(f"FAIL: Shutdown failed with status {resp.status_code} or unexpected response.")


    # --- New Test Case: Call After Shutdown ---
    print(f"\n[TEST] Call /tools again for session {SESSION_ID} after shutdown...")
    post_shutdown_tools_payload = {"session_id": SESSION_ID}
    resp = requests.post(f"{base_url}/tools", json=post_shutdown_tools_payload)
    print("Result:", resp.json())
    # Expecting an error because the session data should be cleared
    if resp.status_code == 400 or resp.status_code == 409: # Code returns 400 if session_id missing, 409 if manager not initialized/ready
        print("PASS: Received expected error when accessing session after shutdown.")
    else:
        print(f"FAIL: Expected status 400/409 after session shutdown, but got {resp.status_code}.")
    # --- End New Test Case ---


except requests.exceptions.ConnectionError as e:
    print(f"\n[TEST] Error: Could not connect to MCP client server on port {PORT}. Is it running?")
    print(f"Details: {e}")
except Exception as e:
    import traceback
    print(f"\n[TEST] An unexpected error occurred during the test run:")
    print(e)
    traceback.print_exc()
finally:
    # No subprocess to terminate here, as the server runs externally.
    print("\n[TEST] Test run finished.") 