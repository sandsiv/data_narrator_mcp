import redis
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from .mcp_manager import MCPServerManager
from config import MCPConfig
import psutil

class MCPSessionManager:
    """
    Redis-only session manager for MCP bridge with orphaned process cleanup.
    
    Architecture:
    - All session data stored in Redis with idle TTL
    - MCP managers created on-demand, not cached
    - Background cleanup thread monitors orphaned processes
    - Fully stateless - supports multiple workers and service restarts
    """
    
    def __init__(self):
        """Initialize Redis-only session manager with process tracking."""
        try:
            # Connect to Redis
            self.redis = redis.Redis(**MCPConfig.get_redis_connection_params())
            
            # Test connection
            self.redis.ping()
            
            # Configuration
            self.idle_ttl = MCPConfig.Session.IDLE_TTL
            self.key_prefix = MCPConfig.Session.KEY_PREFIX
            
            # Process tracking for orphaned process cleanup
            self.active_processes = {}  # session_id -> process_info
            self.process_lock = threading.Lock()
            
            # Background cleanup thread
            self._cleanup_thread = None
            self._should_stop_cleanup = False
            self._start_cleanup_thread()
            
            print(f"[MCP SESSION] Redis-only session manager initialized with process tracking", flush=True)
            print(f"[MCP SESSION] Session idle TTL: {self.idle_ttl}s", flush=True)
            print(f"[MCP SESSION] Redis: {MCPConfig.Redis.HOST}:{MCPConfig.Redis.PORT}", flush=True)
            
        except Exception as e:
            print(f"[MCP SESSION] Failed to connect to Redis: {e}", flush=True)
            raise

    def _start_cleanup_thread(self):
        """Start the background cleanup thread for orphaned processes."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._should_stop_cleanup = False
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker, 
                daemon=True, 
                name="MCP-Process-Cleanup"
            )
            self._cleanup_thread.start()
            print("[MCP SESSION] Started background process cleanup thread", flush=True)

    def _cleanup_worker(self):
        """Background worker that cleans up orphaned MCP processes."""
        cleanup_interval = MCPConfig.Session.CLEANUP_INTERVAL
        
        while not self._should_stop_cleanup:
            try:
                self._cleanup_orphaned_processes()
            except Exception as e:
                print(f"[MCP CLEANUP] Error in cleanup worker: {e}", flush=True)
            
            # Sleep in small intervals to allow for quick shutdown
            for _ in range(cleanup_interval):
                if self._should_stop_cleanup:
                    break
                time.sleep(1)
        
        print("[MCP CLEANUP] Cleanup worker thread stopped", flush=True)

    def _cleanup_orphaned_processes(self):
        """Clean up processes that no longer have active Redis sessions."""
        try:
            # Get all active Redis session IDs
            active_sessions = set()
            redis_keys = self.redis.keys(f"{self.key_prefix}:*")
            for key in redis_keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                session_id = key.split(":")[-1]
                active_sessions.add(session_id)
            
            # Check tracked processes
            orphaned_sessions = []
            with self.process_lock:
                for session_id, process_info in list(self.active_processes.items()):
                    if session_id not in active_sessions:
                        # Session expired but process still tracked
                        orphaned_sessions.append((session_id, process_info))
            
            # Clean up orphaned processes
            for session_id, process_info in orphaned_sessions:
                self._kill_orphaned_process(session_id, process_info)
            
            if orphaned_sessions:
                print(f"[MCP CLEANUP] Cleaned up {len(orphaned_sessions)} orphaned processes", flush=True)
            
            # Also clean up any stale entries in our tracking dict
            with self.process_lock:
                for session_id in list(self.active_processes.keys()):
                    if session_id not in active_sessions:
                        del self.active_processes[session_id]
            
        except Exception as e:
            print(f"[MCP CLEANUP] Error during cleanup: {e}", flush=True)

    def _kill_orphaned_process(self, session_id: str, process_info: dict):
        """Kill an orphaned MCP process."""
        try:
            pid = process_info.get('pid')
            if not pid:
                return
            
            proc = psutil.Process(pid)
            if proc.is_running():
                # Verify this is actually our MCP process by checking command line
                cmdline = proc.cmdline()
                server_script = process_info.get('server_script', '')
                
                if ('mcp' in ' '.join(cmdline) and 'run' in cmdline and 
                    any(server_script in arg for arg in cmdline)):
                    
                    print(f"[MCP CLEANUP] Killing orphaned process PID {pid} for expired session {session_id}", flush=True)
                    proc.terminate()
                    
                    # Wait for graceful termination
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if needed
                        proc.kill()
                        print(f"[MCP CLEANUP] Force killed orphaned process PID {pid}", flush=True)
                else:
                    print(f"[MCP CLEANUP] Process PID {pid} doesn't match expected MCP command line, skipping", flush=True)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process already gone or no access - that's fine
            pass
        except Exception as e:
            print(f"[MCP CLEANUP] Error killing orphaned process for session {session_id}: {e}", flush=True)

    def register_process(self, session_id: str, manager: MCPServerManager):
        """Register an active MCP process for tracking."""
        try:
            process_info = manager.get_process_info()
            with self.process_lock:
                self.active_processes[session_id] = process_info
            print(f"[MCP SESSION] Registered process for session {session_id}: PID {process_info.get('pid')}", flush=True)
        except Exception as e:
            print(f"[MCP SESSION] Error registering process for session {session_id}: {e}", flush=True)

    def unregister_process(self, session_id: str):
        """Unregister a process when it's properly cleaned up."""
        with self.process_lock:
            if session_id in self.active_processes:
                process_info = self.active_processes.pop(session_id)
                print(f"[MCP SESSION] Unregistered process for session {session_id}: PID {process_info.get('pid')}", flush=True)

    def create_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Create a new session in Redis with idle TTL.
        
        Args:
            session_id: Unique session identifier
            session_data: Session data to store
            
        Returns:
            bool: True if session was created successfully
        """
        try:
            # Add metadata
            session_data.update({
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_accessed': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id
            })
            
            # Serialize and store with TTL
            redis_key = self._redis_key(session_id)
            data = json.dumps(session_data, default=str)
            
            # Use SETEX to set value with TTL in one atomic operation
            result = self.redis.setex(redis_key, self.idle_ttl, data)
            
            if result:
                print(f"[MCP SESSION] Created session {session_id} with idle TTL {self.idle_ttl}s", flush=True)
                return True
            else:
                print(f"[MCP SESSION] Failed to create session {session_id}", flush=True)
                return False
                
        except Exception as e:
            print(f"[MCP SESSION] Error creating session {session_id}: {e}", flush=True)
            return False

    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data and RESET the idle TTL.
        This is the key method that keeps active sessions alive.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with session data or None if session doesn't exist/expired
        """
        try:
            redis_key = self._redis_key(session_id)
            data = self.redis.get(redis_key)
            
            if not data:
                print(f"[MCP SESSION] Session {session_id} not found or expired", flush=True)
                return None
                
            session_data = json.loads(data)
            
            # Update last_accessed timestamp
            session_data['last_accessed'] = datetime.now(timezone.utc).isoformat()
            updated_data = json.dumps(session_data, default=str)
            
            # CRITICAL: Reset TTL back to full idle timeout on every access
            # This keeps the session alive as long as it's being used
            self.redis.setex(redis_key, self.idle_ttl, updated_data)
            
            print(f"[MCP SESSION] Accessed session {session_id}, TTL reset to {self.idle_ttl}s", flush=True)
            return session_data
            
        except json.JSONDecodeError as e:
            print(f"[MCP SESSION] Invalid JSON data for session {session_id}: {e}", flush=True)
            # Clean up corrupted session
            self._delete_redis_key(session_id)
            return None
        except Exception as e:
            print(f"[MCP SESSION] Error getting session {session_id}: {e}", flush=True)
            return None

    def update_session_data(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session data and RESET the idle TTL.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply
            
        Returns:
            bool: True if successful
        """
        try:
            # First get current data (this also resets TTL)
            session_data = self.get_session_data(session_id)
            if not session_data:
                print(f"[MCP SESSION] Cannot update non-existent session {session_id}", flush=True)
                return False
                
            # Merge updates
            session_data.update(updates)
            session_data['last_accessed'] = datetime.now(timezone.utc).isoformat()
            
            # Save back to Redis with fresh TTL
            redis_key = self._redis_key(session_id)
            data = json.dumps(session_data, default=str)
            result = self.redis.setex(redis_key, self.idle_ttl, data)
            
            if result:
                print(f"[MCP SESSION] Updated session {session_id}, TTL reset to {self.idle_ttl}s", flush=True)
                return True
            else:
                print(f"[MCP SESSION] Failed to update session {session_id}", flush=True)
                return False
                
        except Exception as e:
            print(f"[MCP SESSION] Error updating session {session_id}: {e}", flush=True)
            return False

    def touch_session(self, session_id: str) -> bool:
        """
        Touch session to reset its TTL without modifying data.
        Useful for endpoints that access session but don't modify it.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session exists and TTL was reset
        """
        try:
            redis_key = self._redis_key(session_id)
            
            # Check if session exists
            if not self.redis.exists(redis_key):
                return False
                
            # Reset TTL without changing data
            result = self.redis.expire(redis_key, self.idle_ttl)
            
            if result:
                print(f"[MCP SESSION] Touched session {session_id}, TTL reset to {self.idle_ttl}s", flush=True)
                return True
            else:
                print(f"[MCP SESSION] Failed to touch session {session_id}", flush=True)
                return False
                
        except Exception as e:
            print(f"[MCP SESSION] Error touching session {session_id}: {e}", flush=True)
            return False

    def create_mcp_manager(self, session_id: str) -> Optional[MCPServerManager]:
        """
        Create a new MCP manager for session (not cached).
        This is called on-demand for each request that needs MCP access.
        
        Args:
            session_id: Session identifier
            
        Returns:
            MCPServerManager instance or None if session doesn't exist
        """
        # First, touch the session to reset its TTL and verify it exists
        if not self.touch_session(session_id):
            print(f"[MCP SESSION] Session {session_id} not found for MCP manager creation", flush=True)
            return None
            
        # Create new manager (not cached)
        try:
            manager = MCPServerManager(server_script=MCPConfig.MCP.SERVER_SCRIPT)
            manager.start()
            
            # Register the process for tracking
            self.register_process(session_id, manager)
            
            print(f"[MCP SESSION] Created fresh MCP manager for session {session_id}", flush=True)
            return manager
        except Exception as e:
            print(f"[MCP SESSION] Failed to create MCP manager for {session_id}: {e}", flush=True)
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Explicitly delete session from Redis and unregister any tracked processes.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            # Unregister any tracked processes first
            self.unregister_process(session_id)
            
            # Delete from Redis
            result = self._delete_redis_key(session_id)
            print(f"[MCP SESSION] Deleted session {session_id}", flush=True)
            return result
            
        except Exception as e:
            print(f"[MCP SESSION] Error deleting session {session_id}: {e}", flush=True)
            return False

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists in Redis.
        NOTE: This does NOT reset the TTL - use touch_session() for that.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session exists
        """
        redis_key = self._redis_key(session_id)
        return bool(self.redis.exists(redis_key))

    def get_session_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for session (for debugging/monitoring).
        
        Args:
            session_id: Session identifier
            
        Returns:
            int: TTL in seconds, -1 if key doesn't exist, -2 if key has no expiration
        """
        redis_key = self._redis_key(session_id)
        return self.redis.ttl(redis_key)

    def get_active_sessions_count(self) -> Dict[str, int]:
        """
        Get statistics about active sessions and tracked processes.
        
        Returns:
            Dict with session statistics
        """
        try:
            redis_sessions = len(self.redis.keys(f"{self.key_prefix}:*"))
            
            with self.process_lock:
                tracked_processes = len(self.active_processes)
            
            return {
                'redis_sessions': redis_sessions,
                'tracked_processes': tracked_processes,
                'architecture': 'redis_with_process_tracking'
            }
        except Exception as e:
            print(f"[MCP SESSION] Error getting session stats: {e}", flush=True)
            return {
                'redis_sessions': 0, 
                'tracked_processes': 0,
                'architecture': 'redis_with_process_tracking'
            }

    def _redis_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.key_prefix}:{session_id}"

    def _delete_redis_key(self, session_id: str) -> bool:
        """Delete session key from Redis."""
        redis_key = self._redis_key(session_id)
        return bool(self.redis.delete(redis_key))

    def shutdown(self):
        """Graceful shutdown of session manager."""
        print("[MCP SESSION] Shutting down session manager with process tracking...", flush=True)
        
        # Stop cleanup thread
        self._should_stop_cleanup = True
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=10)
            print("[MCP SESSION] Cleanup thread stopped", flush=True)
        
        # Kill any remaining tracked processes
        with self.process_lock:
            for session_id, process_info in list(self.active_processes.items()):
                self._kill_orphaned_process(session_id, process_info)
            self.active_processes.clear()
        
        # Close Redis connection
        try:
            self.redis.close()
            print("[MCP SESSION] Closed Redis connection", flush=True)
        except Exception as e:
            print(f"[MCP SESSION] Error closing Redis connection: {e}", flush=True)
            
        print("[MCP SESSION] Session manager shutdown complete", flush=True)

    def __del__(self):
        """Cleanup on object destruction."""
        try:
            self._should_stop_cleanup = True
            if hasattr(self, 'redis'):
                self.redis.close()
        except Exception:
            pass  # Ignore errors during cleanup 