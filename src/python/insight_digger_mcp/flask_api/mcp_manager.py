import subprocess
import threading
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import sys
import concurrent.futures
import os
import psutil  # For process monitoring

class MCPServerManager:
    """
    Manages the MCP server subprocess and protocol session.
    Handles starting/stopping the server, and tool communication.
    """
    def __init__(self, server_script='src/python/insight_digger_mcp/mcp_server/server.py'):
        self.server_script = server_script
        self.process = None
        self.session = None
        self.loop = None
        self.lock = threading.Lock()
        self.session_ready = threading.Event()
        self._tools_cache = None
        self._session_thread = None
        self._should_stop = False
        self._session_error = None
        
        # Process tracking for orphaned process cleanup
        self._subprocess_pid = None
        self._created_at = time.time()

    def start(self, api_env=None):
        """
        Start the MCP server subprocess and initialize protocol session.
        This should be called once per client session.
        
        # NOTE: If you want to pass JWT or other secrets to the MCP server as environment variables,
        # you can pass them in api_env (a dict). Currently, the server expects JWT/apiUrl as tool params.
        """
        with self.lock:
            if self.session is not None:
                return  # Already started
            self._should_stop = False
            self._session_error = None
            self._session_thread = threading.Thread(target=self._session_worker, args=(api_env,), daemon=True)
            self._session_thread.start()
            # Wait for session to be ready or error
            self.session_ready.wait(timeout=30)
            if self.session is None:
                raise RuntimeError(f"MCP session failed to start: {self._session_error}")

    def _session_worker(self, api_env):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._session_lifetime(api_env))
            self.loop.close()
        except Exception as e:
            import traceback
            self._session_error = f"{e}\n{traceback.format_exc()}"
            print("[MCP CLIENT] MCP session worker error:", self._session_error, flush=True)
            self.session_ready.set()  # Unblock waiting threads

    async def _session_lifetime(self, api_env):
        # Get the path to the virtual environment's bin directory
        venv_bin = os.path.dirname(sys.executable)
        mcp_cmd = os.path.join(venv_bin, "mcp")

        # Ensure subprocess inherits environment variables
        # Start with current environment and merge api_env if provided
        subprocess_env = os.environ.copy()
        if api_env:
            subprocess_env.update(api_env)

        server_params = StdioServerParameters(
            command=mcp_cmd,
            args=["run", self.server_script],
            env=subprocess_env
        )
        async with stdio_client(server_params) as (read, write):
            self._read, self._write = read, write
            
            # Try to capture the subprocess PID for tracking
            try:
                # The stdio_client should have started a subprocess
                # We need to find it by looking for our server script in process list
                self._find_subprocess_pid()
            except Exception as e:
                print(f"[MCP CLIENT] Warning: Could not track subprocess PID: {e}", flush=True)
            
            async with ClientSession(read, write) as session:
                self.session = session
                await self.session.initialize()
                self.session_ready.set()
                # Wait until stop is requested
                while not self._should_stop:
                    await asyncio.sleep(0.1)

    def _find_subprocess_pid(self):
        """Find the PID of our MCP server subprocess for tracking."""
        try:
            # Look for processes running our server script
            for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and len(cmdline) >= 3:
                        # Look for: mcp run server.py
                        if ('mcp' in cmdline[0] and 'run' in cmdline and 
                            any(self.server_script in arg for arg in cmdline)):
                            # Check if this process was created recently (within last 30 seconds)
                            if time.time() - proc.info['create_time'] < 30:
                                self._subprocess_pid = proc.info['pid']
                                print(f"[MCP CLIENT] Tracked subprocess PID: {self._subprocess_pid}", flush=True)
                                break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            print(f"[MCP CLIENT] Error finding subprocess PID: {e}", flush=True)

    async def _close_session(self):
        """
        Clean up the protocol session and subprocess (async).
        """
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
        if hasattr(self, '_client_ctx'):
            await self._client_ctx[0].aclose()
            await self._client_ctx[1].aclose()

    def stop(self):
        """
        Stop the MCP server subprocess and clean up resources.
        """
        with self.lock:
            self._should_stop = True
            if self._session_thread:
                self._session_thread.join(timeout=10)
                
            # Force kill subprocess if it's still running
            self._force_kill_subprocess()
            
            self.session = None
            self._tools_cache = None
            self.session_ready.clear()
            self._subprocess_pid = None

    def _force_kill_subprocess(self):
        """Force kill the subprocess if it's still running."""
        if self._subprocess_pid:
            try:
                proc = psutil.Process(self._subprocess_pid)
                if proc.is_running():
                    print(f"[MCP CLIENT] Force killing subprocess PID: {self._subprocess_pid}", flush=True)
                    proc.terminate()
                    # Wait a bit for graceful termination
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        proc.kill()
                        print(f"[MCP CLIENT] Force killed subprocess PID: {self._subprocess_pid}", flush=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone or no access
                pass
            except Exception as e:
                print(f"[MCP CLIENT] Error killing subprocess {self._subprocess_pid}: {e}", flush=True)

    def get_process_info(self) -> dict:
        """Get process information for tracking purposes."""
        return {
            'pid': self._subprocess_pid,
            'created_at': self._created_at,
            'server_script': self.server_script,
            'is_running': self.is_process_running()
        }

    def is_process_running(self) -> bool:
        """Check if the subprocess is still running."""
        if not self._subprocess_pid:
            return False
        try:
            proc = psutil.Process(self._subprocess_pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def list_tools(self):
        """
        List available tools from the MCP server.
        """
        self.start()
        if self.session is None:
            raise RuntimeError(f"MCP session is not ready: {self._session_error}")
        fut = asyncio.run_coroutine_threadsafe(self._list_tools_async(), self.loop)
        return fut.result(timeout=30)

    async def _list_tools_async(self):
        if self._tools_cache is not None:
            return self._tools_cache
        tools = await self.session.list_tools()
        tool_names = [tool.name for tool in tools.tools]
        self._tools_cache = tool_names
        return tool_names

    def call_tool(self, tool, params):
        """
        Call a tool by name with parameters.
        """
        self.start()
        if self.session is None:
            raise RuntimeError(f"MCP session is not ready: {self._session_error}")
        fut = asyncio.run_coroutine_threadsafe(self._call_tool_async(tool, params), self.loop)
        return fut.result(timeout=310)

    async def _call_tool_async(self, tool, params):
        result_obj = await self.session.call_tool(tool, params)
        try:
            import json
            content = result_obj.content[0].text
            return json.loads(content)
        except Exception:
            return {"result": result_obj.content[0].text}

    def get_tool_schemas(self):
        self.start()
        if self.session is None:
            raise RuntimeError(f"MCP session is not ready: {self._session_error}")
        fut = asyncio.run_coroutine_threadsafe(self._get_tool_schemas_async(), self.loop)
        return fut.result(timeout=30)

    async def _get_tool_schemas_async(self):
        tools = await self.session.list_tools()
        # Return full tool objects as dicts
        return [tool.model_dump() if hasattr(tool, 'model_dump') else tool.__dict__ for tool in tools.tools] 