import subprocess
import threading
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import sys
import concurrent.futures

class MCPServerManager:
    """
    Manages the MCP server subprocess and protocol session.
    Handles starting/stopping the server, and tool communication.
    """
    def __init__(self, server_script='mcp_server.py'):
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
        server_params = StdioServerParameters(
            command="mcp",
            args=["run", self.server_script],
            env=api_env
        )
        async with stdio_client(server_params) as (read, write):
            self._read, self._write = read, write
            async with ClientSession(read, write) as session:
                self.session = session
                await self.session.initialize()
                self.session_ready.set()
                # Wait until stop is requested
                while not self._should_stop:
                    await asyncio.sleep(0.1)

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
            self.session = None
            self._tools_cache = None
            self.session_ready.clear()

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