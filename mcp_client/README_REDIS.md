# MCP Client Redis-Only Session Management

## Overview

The MCP Client now uses a **Redis-only architecture** for session management, designed for production environments with multiple workers and service restarts.

## Architecture

### Redis-Only Design
- **All session data** stored in Redis with idle-based TTL
- **MCP managers** created on-demand per request (not cached)
- **No background cleanup threads** needed
- **Fully stateless** - supports multiple Flask workers
- **Service restart resilient** - sessions survive process restarts

### Key Benefits
- **Scalability**: Multiple Flask workers can share session data
- **Reliability**: No memory leaks or orphaned processes
- **Simplicity**: Redis TTL handles all cleanup automatically
- **Performance**: On-demand MCP manager creation optimizes resource usage

## Session Lifecycle

### Session Creation (`/init`)
1. Validate credentials with external API
2. Store session data in Redis with idle TTL
3. Return success

### Session Access (any endpoint)
1. Retrieve session data from Redis
2. **Automatically reset TTL** to full idle timeout
3. Create fresh MCP manager if needed
4. Execute request
5. Clean up MCP manager immediately
6. Update session cache with results

### Session Expiration
- Sessions expire after **24 hours of inactivity** (configurable)
- Redis handles expiration automatically
- No manual cleanup required

## Configuration

### Environment Variables

```bash
# Redis Configuration (Required)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=optional_password

# Session Settings
MCP_SESSION_IDLE_TTL=86400  # 24 hours
MCP_SESSION_KEY_PREFIX=mcp_session

# API Timeouts
MCP_API_DEFAULT_TIMEOUT=60
MCP_API_LONG_TIMEOUT=300
MCP_API_VALIDATION_TIMEOUT=5

# Server Settings
MCP_CLIENT_PORT=33000
MCP_CLIENT_HOST=0.0.0.0
```

### Configuration Class
All settings are centralized in `MCPConfig` class:

```python
from mcp_client.config import MCPConfig

# Access configuration
redis_params = MCPConfig.get_redis_connection_params()
idle_ttl = MCPConfig.Session.IDLE_TTL
api_url = MCPConfig.API.BASE_URL
```

## Installation & Setup

### 1. Install Redis
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install redis-server

# macOS
brew install redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### 2. Install Python Dependencies
```bash
pip install redis>=4.0.0
```

### 3. Configure Environment
```bash
cp mcp_client/config.example.env .env
# Edit .env with your Redis settings
```

### 4. Start Service
```bash
python -m mcp_client.server
```

## Multi-Worker Deployment

### Nginx + Gunicorn Example
```bash
# Install Gunicorn
pip install gunicorn

# Start multiple workers
gunicorn -w 4 -b 0.0.0.0:33000 mcp_client.server:app

# Nginx configuration
upstream mcp_backend {
    server 127.0.0.1:33000;
}

server {
    location / {
        proxy_pass http://mcp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Use environment variables for configuration
ENV REDIS_HOST=redis
ENV MCP_CLIENT_PORT=33000

EXPOSE 33000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:33000", "mcp_client.server:app"]
```

## Monitoring & Debugging

### Session Statistics
```bash
curl -X GET http://localhost:33000/health
```

### Redis Monitoring
```bash
# Connect to Redis CLI
redis-cli

# Check active sessions
KEYS mcp_session:*

# Check session TTL
TTL mcp_session:your_session_id

# Monitor Redis operations
MONITOR
```

### Logging
- MCP Server logs: `/tmp/mcp_server.log` (configurable)
- Flask logs: stdout/stderr
- Redis logs: Redis server logs

## Performance Characteristics

### Resource Usage
- **Memory**: Only Redis storage + temporary MCP managers
- **CPU**: On-demand process creation optimized for typical usage
- **Network**: Direct Redis connections, no polling

### Scalability
- **Horizontal**: Add more Flask workers behind load balancer
- **Vertical**: Redis can handle thousands of concurrent sessions
- **Geographic**: Redis clustering for multi-region deployments

## Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Check Redis is running
redis-cli ping

# Check configuration
grep REDIS_ .env
```

**Session Not Found**
- Sessions expire after idle timeout
- Check TTL: `redis-cli TTL mcp_session:session_id`
- Verify session creation in logs

**MCP Manager Creation Failed**
- Check MCP server script path
- Verify virtual environment activation
- Review MCP server logs

### Health Checks
```bash
# Basic health check
curl http://localhost:33000/health

# Redis connectivity
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
```

## Migration from Dual-Layer Architecture

The new Redis-only architecture is **backward compatible** with existing HTTP endpoints. No client changes required.

### Key Changes
- ✅ Sessions survive service restarts
- ✅ Multiple workers supported
- ✅ No background cleanup threads
- ✅ Immediate resource cleanup
- ✅ Simplified monitoring

### Breaking Changes
- None - all HTTP endpoints unchanged
- Configuration keys remain the same
- Session behavior identical from client perspective 