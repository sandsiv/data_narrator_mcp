import redis
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from mcp_client.manager import MCPServerManager
from mcp_client.config import MCPConfig

class MCPSessionManager:
    """
    Redis-only session manager for MCP bridge.
    
    Architecture:
    - All session data stored in Redis with idle TTL
    - MCP managers created on-demand, not cached
    - No background cleanup threads needed
    - Fully stateless - supports multiple workers and service restarts
    """
    
    def __init__(self):
        """Initialize Redis-only session manager."""
        try:
            # Connect to Redis
            self.redis = redis.Redis(**MCPConfig.get_redis_connection_params())
            
            # Test connection
            self.redis.ping()
            
            # Configuration
            self.idle_ttl = MCPConfig.Session.IDLE_TTL
            self.key_prefix = MCPConfig.Session.KEY_PREFIX
            
            print(f"[MCP SESSION] Redis-only session manager initialized", flush=True)
            print(f"[MCP SESSION] Session idle TTL: {self.idle_ttl}s", flush=True)
            print(f"[MCP SESSION] Redis: {MCPConfig.Redis.HOST}:{MCPConfig.Redis.PORT}", flush=True)
            
        except Exception as e:
            print(f"[MCP SESSION] Failed to connect to Redis: {e}", flush=True)
            raise

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
            print(f"[MCP SESSION] Created fresh MCP manager for session {session_id}", flush=True)
            return manager
        except Exception as e:
            print(f"[MCP SESSION] Failed to create MCP manager for {session_id}: {e}", flush=True)
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Explicitly delete session from Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deletion was successful
        """
        try:
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
        Get statistics about active sessions.
        
        Returns:
            Dict with session statistics
        """
        try:
            redis_sessions = len(self.redis.keys(f"{self.key_prefix}:*"))
            
            return {
                'redis_sessions': redis_sessions,
                'architecture': 'redis_only'
            }
        except Exception as e:
            print(f"[MCP SESSION] Error getting session stats: {e}", flush=True)
            return {'redis_sessions': 0, 'architecture': 'redis_only'}

    def _redis_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.key_prefix}:{session_id}"

    def _delete_redis_key(self, session_id: str) -> bool:
        """Delete session key from Redis."""
        redis_key = self._redis_key(session_id)
        return bool(self.redis.delete(redis_key))

    def shutdown(self):
        """Graceful shutdown of session manager."""
        print("[MCP SESSION] Shutting down Redis-only session manager...", flush=True)
        
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
            if hasattr(self, 'redis'):
                self.redis.close()
        except Exception:
            pass  # Ignore errors during cleanup 