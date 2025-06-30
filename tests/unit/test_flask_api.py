import subprocess
import requests
import time
import json
import os
import threading
from dotenv import load_dotenv
load_dotenv()

# Enable test mode to skip credential validation
os.environ["MCP_SKIP_VALIDATION"] = "true"

# Configuration - using real values from .env
API_URL = os.getenv("apiUrl")
JWT_TOKEN = os.getenv("jwtToken")
SOURCE_ID = os.getenv("sourceId")
QUESTION = os.getenv("question", "What are the main trends in this data?")

# Check required environment variables
if not API_URL or not JWT_TOKEN:
    print("ERROR: Missing required environment variables!")
    print("Please ensure .env file contains:")
    print("- apiUrl=your_api_url")
    print("- jwtToken=your_jwt_token")
    print("- sourceId=your_source_id (optional)")
    print("- question=your_question (optional)")
    exit(1)

print(f"Using API URL: {API_URL}")
print(f"Using JWT Token: {JWT_TOKEN[:20]}...")
print(f"Using Source ID: {SOURCE_ID}")
print(f"Using Question: {QUESTION}")

# Server configuration
PORT = int(os.getenv("MCP_CLIENT_PORT", 33000))
SESSION_ID = os.getenv("SESSION_ID", "test-session-125")

base_url = f"http://127.0.0.1:{PORT}"

try:
    # Wait for /health to respond (server readiness)
    print(f"\nWaiting for server on port {PORT}...")
    for _ in range(30):
        try:
            resp = requests.get(f"{base_url}/health", timeout=0.5)
            if resp.status_code == 200:
                print("Server ready")
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        print(f"Server did not respond on port {PORT} in time")
        exit(1)

    # 1. POST /init for a specific session
    print(f"\n=== TEST 1: Initialize session {SESSION_ID} ===")
    init_payload = {
        "session_id": SESSION_ID,
        "apiUrl": API_URL,
        "jwtToken": JWT_TOKEN
    }
    resp = requests.post(f"{base_url}/init", json=init_payload)
    init_response = resp.json()
    print("Init result:", init_response)
    if init_response.get("status") != "ok":
        print("❌ FAIL: Error during initialization, aborting test.")
        print("Response:", init_response)
        exit(1)
    print("✅ PASS: Session initialized successfully")

    # 2. POST /tools for the specific session
    print(f"\n=== TEST 2: Fetch tools for session {SESSION_ID} ===")
    tools_payload = {"session_id": SESSION_ID}
    resp = requests.post(f"{base_url}/tools", json=tools_payload)
    tools_json = resp.json()
    
    if "tools" in tools_json:
        tool_names = [tool.get("name") for tool in tools_json["tools"]]
        print(f"✅ PASS: Found {len(tool_names)} tools: {tool_names}")
    else:
        print("❌ FAIL: No tools found in response")
        print("Response:", tools_json)

    # 3. POST /call-tool (validate_settings)
    print(f"\n=== TEST 3: Validate settings ===")
    validate_payload = {
        "session_id": SESSION_ID,
        "tool": "validate_settings",
        "params": {}  # apiUrl and jwtToken should be auto-injected
    }
    resp = requests.post(f"{base_url}/call-tool", json=validate_payload)
    validate_result = resp.json()
    print("Validate result:", validate_result)
    
    if validate_result.get("status") == "success":
        print("✅ PASS: Settings validation successful")
    else:
        print("❌ FAIL: Settings validation failed")

    # 4. POST /call-tool (list_sources)
    print(f"\n=== TEST 4: List sources ===")
    list_sources_payload = {
        "session_id": SESSION_ID,
        "tool": "list_sources",
        "params": {"search": "", "limit": 5}  # Empty search to get some results
    }
    resp = requests.post(f"{base_url}/call-tool", json=list_sources_payload)

    source_id_to_use = None  # Will be determined from API response
    try:
        list_sources_result = resp.json()
        print("List sources result:", json.dumps(list_sources_result, indent=2))
        
        if resp.status_code == 200 and list_sources_result.get("status") == "success" and isinstance(list_sources_result.get("data"), list):
            if list_sources_result["data"]:
                # Use SOURCE_ID from .env if available and exists in the results, otherwise use the first available
                if SOURCE_ID:
                    # Check if the SOURCE_ID from .env exists in the results
                    found_source = next((s for s in list_sources_result["data"] if s.get("id") == SOURCE_ID), None)
                    if found_source:
                        source_id_to_use = SOURCE_ID
                        print(f"✅ Using SOURCE_ID from .env: {source_id_to_use}")
                    else:
                        source_id_to_use = list_sources_result["data"][0].get("id")
                        print(f"⚠️  SOURCE_ID from .env not found, using first available: {source_id_to_use}")
                else:
                    source_id_to_use = list_sources_result["data"][0].get("id")
                    print(f"✅ Using first available source: {source_id_to_use}")
                
                print(f"✅ PASS: Found {len(list_sources_result['data'])} sources")
            else:
                print("⚠️  WARNING: No sources found in response")
        else:
            print("❌ FAIL: list_sources call failed")
            print(f"Status code: {resp.status_code}, Response: {list_sources_result}")
    except Exception as e:
        print("❌ FAIL: Error processing list_sources response:", e)
        print("Raw response:", resp.text)

    # 5. Test the granular workflow if we have a source
    if source_id_to_use and list_sources_result.get("status") == "success":
        print(f"\n=== TEST 5: Analyze source structure ===")
        analyze_payload = {
            "session_id": SESSION_ID,
            "tool": "analyze_source_structure",
            "params": {"sourceId": source_id_to_use}
        }
        resp = requests.post(f"{base_url}/call-tool", json=analyze_payload)
        analyze_result = resp.json()
        
        if analyze_result.get("status") == "success":
            print("✅ PASS: Source structure analyzed successfully")
            print(f"Column analysis available: {'columnAnalysis' in analyze_result}")
        else:
            print("❌ FAIL: Source structure analysis failed")
            print("Result:", analyze_result)

        # 6. Generate strategy
        print(f"\n=== TEST 6: Generate strategy ===")
        strategy_payload = {
            "session_id": SESSION_ID,
            "tool": "generate_strategy",
            "params": {"question": QUESTION}  # columnAnalysis should be auto-injected
        }
        resp = requests.post(f"{base_url}/call-tool", json=strategy_payload)
        strategy_result = resp.json()
        
        if strategy_result.get("status") == "success":
            print("✅ PASS: Strategy generated successfully")
        else:
            print("❌ FAIL: Strategy generation failed")
            print("Result:", strategy_result)

        # 7. Create configuration
        print(f"\n=== TEST 7: Create configuration ===")
        config_payload = {
            "session_id": SESSION_ID,
            "tool": "create_configuration",
            "params": {}  # question, columnAnalysis, strategy should be auto-injected
        }
        resp = requests.post(f"{base_url}/call-tool", json=config_payload)
        config_result = resp.json()
        
        if config_result.get("status") == "success":
            print("✅ PASS: Configuration created successfully")
            print(f"Markdown config available: {'markdownConfig' in config_result}")
        else:
            print("❌ FAIL: Configuration creation failed")
            print("Result:", config_result)

    else:
        print("\n⚠️  SKIPPING: Advanced workflow tests (no sourceId available)")

    # 8. Test with invalid session ID
    print(f"\n=== TEST 8: Invalid session ID ===")
    invalid_session_id = "invalid-session-xyz"
    invalid_tools_payload = {"session_id": invalid_session_id}
    resp = requests.post(f"{base_url}/tools", json=invalid_tools_payload)
    
    if resp.status_code in [400, 409]:
        print("✅ PASS: Received expected error for invalid session ID")
    else:
        print(f"❌ FAIL: Expected status 400/409 for invalid session ID, but got {resp.status_code}")
        print("Response:", resp.json())

    # 9. Shutdown session
    print(f"\n=== TEST 9: Shutdown session ===")
    shutdown_payload = {"session_id": SESSION_ID}
    resp = requests.post(f"{base_url}/shutdown", json=shutdown_payload)
    shutdown_result = resp.json()
    
    if resp.status_code == 200 and shutdown_result.get("status") == "ok":
        print("✅ PASS: Session shut down successfully")
    else:
        print(f"❌ FAIL: Shutdown failed with status {resp.status_code}")
        print("Response:", shutdown_result)

    # 10. Test access after shutdown
    print(f"\n=== TEST 10: Access after shutdown ===")
    post_shutdown_tools_payload = {"session_id": SESSION_ID}
    resp = requests.post(f"{base_url}/tools", json=post_shutdown_tools_payload)
    
    if resp.status_code in [400, 409]:
        print("✅ PASS: Received expected error when accessing session after shutdown")
    else:
        print(f"❌ FAIL: Expected status 400/409 after session shutdown, but got {resp.status_code}")
        print("Response:", resp.json())

    print(f"\n🎉 TEST SUITE COMPLETED")

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ ERROR: Could not connect to MCP client server on port {PORT}. Is it running?")
    print(f"Details: {e}")
    print(f"Start the server with: python -u -m mcp_client.server")
except Exception as e:
    import traceback
    print(f"\n❌ ERROR: An unexpected error occurred during the test run:")
    print(e)
    traceback.print_exc()
finally:
    print("\n[TEST] Test run finished.") 