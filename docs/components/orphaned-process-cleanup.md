# Orphaned Process Cleanup

## Overview

The MCP system includes lightweight orphaned process cleanup to handle edge cases where MCP server subprocesses might not be properly terminated when their Redis sessions expire.

## Problem Addressed

Previously, if an HTTP request crashed, timed out, or was interrupted before reaching the `finally` block, the MCP server subprocess would never be stopped, leading to potential resource leaks.

## Solution

### Architecture

1. **Process Tracking**: Each MCP manager tracks its subprocess PID and metadata
2. **Background Cleanup Thread**: Runs every 5 minutes to check for orphaned processes  
3. **Session Correlation**: Compares tracked processes with active Redis sessions
4. **Safe Termination**: Only kills processes that match expected MCP command patterns

### Key Components

#### MCPServerManager Enhancements
- `_subprocess_pid`: Tracks the PID of the spawned MCP server process
- `_find_subprocess_pid()`: Identifies the subprocess by command line pattern
- `get_process_info()`: Returns process metadata for tracking
- `_force_kill_subprocess()`: Safely terminates orphaned processes

#### MCPSessionManager Enhancements  
- `active_processes`: Dictionary tracking session_id → process_info
- `register_process()` / `unregister_process()`: Process lifecycle management
- `_cleanup_worker()`: Background thread that runs cleanup every 5 minutes
- `_cleanup_orphaned_processes()`: Core cleanup logic

#### Flask App Integration
- `cleanup_mcp_manager()`: Helper function for proper cleanup
- Updated `finally` blocks to unregister processes from tracking

### Configuration

```bash
# Cleanup interval (default: 300 seconds = 5 minutes)
MCP_PROCESS_CLEANUP_INTERVAL=300
```

### Safety Features

1. **Command Line Verification**: Only kills processes matching MCP server patterns
2. **Graceful Termination**: Uses `SIGTERM` first, then `SIGKILL` if needed
3. **Error Handling**: Comprehensive exception handling for all cleanup operations
4. **Logging**: Detailed logging for monitoring and debugging

### Normal Operation

- HTTP requests create MCP managers → processes are registered
- HTTP requests complete → processes are unregistered and stopped normally
- Background cleanup remains idle (no orphaned processes found)

### Orphaned Process Cleanup

- HTTP request crashes/times out → process remains registered but session expires
- Background thread detects session_id not in Redis → marks process as orphaned
- Process is safely terminated and removed from tracking

### Monitoring

The system provides detailed logging:

```
[MCP SESSION] Registered process for session abc123: PID 12345
[MCP SESSION] Unregistered process for session abc123: PID 12345
[MCP CLEANUP] Cleaned up 1 orphaned processes
[MCP CLEANUP] Killing orphaned process PID 12345 for expired session abc123
```

### Performance Impact

- **Minimal overhead**: Only activates for actual orphaned processes
- **Low frequency**: Cleanup runs every 5 minutes by default
- **Efficient**: Uses Redis key scanning and process list iteration
- **Thread-safe**: All operations are properly synchronized

### Dependencies

- `psutil>=5.8.0`: For process monitoring and termination

## Edge Cases Handled

1. **Process already terminated**: Gracefully handles `NoSuchProcess` exceptions
2. **Permission denied**: Handles `AccessDenied` for system processes  
3. **Wrong process**: Verifies command line before termination
4. **Redis connection issues**: Cleanup continues even if Redis is temporarily unavailable
5. **Multiple workers**: Thread-safe design supports multi-worker deployments

## Testing

The system can be monitored by checking:

1. **Process count**: `ps aux | grep "mcp run"` 
2. **Session stats**: Available via the session manager's `get_active_sessions_count()`
3. **Logs**: Look for `[MCP CLEANUP]` log entries

## Configuration Options

All configuration is handled via environment variables in `MCPConfig`:

- `MCP_PROCESS_CLEANUP_INTERVAL`: Cleanup frequency in seconds (default: 300)
- `MCP_SESSION_IDLE_TTL`: Session expiration time (default: 86400)
- `REDIS_HOST`, `REDIS_PORT`: Redis connection settings

This lightweight solution addresses the orphaned process concern while maintaining the system's performance and reliability characteristics. 