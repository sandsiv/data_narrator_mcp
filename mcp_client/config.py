import os
from typing import Optional

class MCPConfig:
    """Shared configuration for both MCP Client and MCP Server"""
    
    class Redis:
        """Redis configuration for session management"""
        HOST = os.getenv("REDIS_HOST", "localhost")
        PORT = int(os.getenv("REDIS_PORT", 6379))
        DB = int(os.getenv("REDIS_DB", 0))
        PASSWORD = os.getenv("REDIS_PASSWORD", None)
        
        # Connection settings
        DECODE_RESPONSES = True
        SOCKET_CONNECT_TIMEOUT = int(os.getenv("REDIS_CONNECT_TIMEOUT", 5))
        SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))
        
    class Session:
        """Session management configuration"""
        # Idle timeout: session expires after this many seconds of inactivity
        IDLE_TTL = int(os.getenv("MCP_SESSION_IDLE_TTL", 24 * 3600))  # 24 hours
        
        # Session key prefix in Redis
        KEY_PREFIX = os.getenv("MCP_SESSION_KEY_PREFIX", "mcp_session")
        
    class Server:
        """Flask server configuration"""
        PORT = int(os.getenv("MCP_CLIENT_PORT", 33000))
        HOST = os.getenv("MCP_CLIENT_HOST", "0.0.0.0")
        
        # Server timeouts
        REQUEST_TIMEOUT = int(os.getenv("MCP_REQUEST_TIMEOUT", 300))  # 5 minutes
        
    class API:
        """External API configuration"""
        BASE_URL = os.getenv("INSIGHT_DIGGER_API_URL", "https://internal.sandsiv.com/data-narrator/api")
        
        # API timeouts
        DEFAULT_TIMEOUT = int(os.getenv("MCP_API_DEFAULT_TIMEOUT", 60))
        LONG_TIMEOUT = int(os.getenv("MCP_API_LONG_TIMEOUT", 300))
        VALIDATION_TIMEOUT = int(os.getenv("MCP_API_VALIDATION_TIMEOUT", 5))
        
    class Security:
        """Security configuration"""
        # Sensitive parameters to filter from tool schemas
        SENSITIVE_PARAMS = os.getenv("MCP_SENSITIVE_PARAMS", "apiUrl,jwtToken").split(",")
        
    class Logging:
        """Logging configuration"""
        LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")
        FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        LOG_FILE = os.getenv("MCP_LOG_FILE", "/tmp/mcp_server.log")
        
    class MCP:
        """MCP server subprocess configuration"""
        SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", "mcp_server.py")
        
        # Timeout for MCP operations
        TOOL_CALL_TIMEOUT = int(os.getenv("MCP_TOOL_CALL_TIMEOUT", 310))  # 5+ minutes
        SESSION_START_TIMEOUT = int(os.getenv("MCP_SESSION_START_TIMEOUT", 30))
        TOOL_LIST_TIMEOUT = int(os.getenv("MCP_TOOL_LIST_TIMEOUT", 30))
        
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration and return True if valid"""
        errors = []
        
        # Validate Redis connection settings
        if not cls.Redis.HOST:
            errors.append("REDIS_HOST is required")
            
        if cls.Redis.PORT <= 0 or cls.Redis.PORT > 65535:
            errors.append("REDIS_PORT must be between 1 and 65535")
            
        # Validate session settings
        if cls.Session.IDLE_TTL <= 0:
            errors.append("MCP_SESSION_IDLE_TTL must be positive")
            
        # Validate server settings
        if cls.Server.PORT <= 0 or cls.Server.PORT > 65535:
            errors.append("MCP_CLIENT_PORT must be between 1 and 65535")
            
        # Validate API settings
        if not cls.API.BASE_URL:
            errors.append("INSIGHT_DIGGER_API_URL is required")
            
        if errors:
            print(f"[MCP CONFIG] Configuration errors: {'; '.join(errors)}", flush=True)
            return False
            
        return True
        
    @classmethod
    def get_redis_connection_params(cls) -> dict:
        """Get Redis connection parameters as dict"""
        params = {
            'host': cls.Redis.HOST,
            'port': cls.Redis.PORT,
            'db': cls.Redis.DB,
            'decode_responses': cls.Redis.DECODE_RESPONSES,
            'socket_connect_timeout': cls.Redis.SOCKET_CONNECT_TIMEOUT,
            'socket_timeout': cls.Redis.SOCKET_TIMEOUT,
        }
        
        if cls.Redis.PASSWORD:
            params['password'] = cls.Redis.PASSWORD
            
        return params

# Backward compatibility alias
MCPClientConfig = MCPConfig
        