# Troubleshooting Guide

Common issues and solutions for the Insight Digger MCP system. This guide covers problems across all components and deployment scenarios.

## Quick Diagnostic Commands

Before diving into specific issues, run these commands to gather system information:

```bash
# Check service status
curl -s http://localhost:33000/health | jq

# Check Redis connection
redis-cli ping

# Check Python environment
python --version
pip list | grep -E "(flask|redis|httpx|fastmcp)"

# Check Node.js environment
node --version
npm list -g | grep insight

# Check system resources
df -h
free -h
ps aux | grep -E "(python|node|redis)"
```

## Component-Specific Issues

### Flask API Issues

#### ❌ "Connection refused" or "Port already in use"

**Symptoms:**
- Cannot reach http://localhost:33000
- Error: "Address already in use"
- Flask fails to start

**Diagnosis:**
```bash
# Check what's using the port
lsof -i :33000
netstat -tulpn | grep :33000

# Check for running Flask processes
ps aux | grep flask
ps aux | grep start_flask_api
```

**Solutions:**
```bash
# Kill existing processes
pkill -f "start_flask_api"
pkill -f "flask"

# Or kill specific process by PID
kill -9 <PID>

# Start Flask API
python src/python/scripts/start_flask_api.py
```

#### ❌ "ModuleNotFoundError: No module named 'config'"

**Symptoms:**
- Flask fails to start with import errors
- "No module named 'config'" or similar

**Diagnosis:**
```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Check if config module is accessible
python -c "from config import MCPConfig; print('Config OK')"
```

**Solutions:**
```bash
# Ensure you're in the project root
cd /path/to/insight_digger_mcp

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify config location
ls -la config/settings.py
```

#### ❌ "Session not found" errors

**Symptoms:**
- API returns 409 errors
- "Session session-123 not found or expired"

**Diagnosis:**
```bash
# Check Redis connection
redis-cli ping

# Check if sessions exist in Redis
redis-cli keys "mcp_session:*"

# Check session data
redis-cli get "mcp_session:your-session-id"
```

**Solutions:**
```bash
# Restart Redis if needed
sudo systemctl restart redis-server

# Clear all sessions (development only)
redis-cli flushdb

# Re-initialize session
curl -X POST http://localhost:33000/init \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","apiUrl":"https://api.example.com","jwtToken":"token"}'
```

### Redis Issues

#### ❌ "Redis connection failed"

**Symptoms:**
- "Connection refused" to Redis
- Session operations fail
- Flask API can't store sessions

**Diagnosis:**
```bash
# Check Redis service status
systemctl status redis-server
# or
service redis-server status

# Check Redis configuration
redis-cli config get "*"

# Test Redis connection
redis-cli ping
```

**Solutions:**
```bash
# Install Redis (Ubuntu/Debian)
sudo apt update
sudo apt install redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Or use Docker
docker run -d -p 6379:6379 --name redis redis:alpine

# Check Redis logs
sudo journalctl -u redis-server -f
```

#### ❌ "Redis authentication failed"

**Symptoms:**
- "NOAUTH Authentication required"
- Authentication errors in logs

**Diagnosis:**
```bash
# Check Redis auth configuration
redis-cli config get requirepass

# Check environment variables
echo $REDIS_PASSWORD
```

**Solutions:**
```bash
# Set Redis password in config
redis-cli config set requirepass "your-password"

# Update environment variables
export REDIS_PASSWORD="your-password"

# Or disable auth for development
redis-cli config set requirepass ""
```

### MCP Server Issues

#### ❌ "MCP server subprocess failed to start"

**Symptoms:**
- Tool execution fails
- "Subprocess creation failed" errors
- No tool schemas returned

**Diagnosis:**
```bash
# Try running MCP server directly
python src/python/insight_digger_mcp/mcp_server/server.py --help

# Check MCP server logs
tail -f logs/mcp_server.log

# Check subprocess creation
ps aux | grep mcp_server
```

**Solutions:**
```bash
# Verify MCP server can start
cd /path/to/insight_digger_mcp
source venv/bin/activate
python src/python/insight_digger_mcp/mcp_server/server.py

# Check Python path in MCP server
python -c "import sys; print(sys.path)"

# Reinstall FastMCP
pip install --upgrade fastmcp
```

#### ❌ "External API connection timeout"

**Symptoms:**
- Tool execution times out
- "Connection timeout" errors
- API calls fail

**Diagnosis:**
```bash
# Test external API directly
curl -H "Authorization: Bearer your-jwt-token" \
  https://api.sandsiv.com/api/sources

# Check network connectivity
ping api.sandsiv.com
nslookup api.sandsiv.com

# Check firewall rules
sudo ufw status
```

**Solutions:**
```bash
# Increase timeout in configuration
# Edit config/settings.py
DEFAULT_TIMEOUT = 120  # Increase from 60

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY

# Test with different timeout
curl --connect-timeout 30 --max-time 60 \
  https://api.sandsiv.com/api/sources
```

### Node.js Bridge Issues

#### ❌ "Bridge connection failed"

**Symptoms:**
- Claude Desktop can't connect to MCP server
- "Connection refused" in Claude Desktop logs
- Bridge doesn't start

**Diagnosis:**
```bash
# Test bridge directly
cd src/nodejs
node src/index.js

# Check Node.js version
node --version
npm --version

# Check dependencies
npm list
```

**Solutions:**
```bash
# Reinstall Node.js dependencies
cd src/nodejs
rm -rf node_modules package-lock.json
npm install

# Update Node.js if needed
nvm install node
nvm use node

# Check bridge configuration
echo $MCP_CLIENT_URL
```

#### ❌ "Claude Desktop doesn't see MCP server"

**Symptoms:**
- No MCP tools available in Claude Desktop
- Configuration appears correct
- No error messages

**Diagnosis:**
```bash
# Check Claude Desktop configuration
# macOS:
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows:
type %APPDATA%\Claude\claude_desktop_config.json

# Check Claude Desktop logs
# macOS:
tail -f ~/Library/Logs/Claude/mcp*.log

# Windows:
type %LOCALAPPDATA%\Claude\logs\mcp*.log
```

**Solutions:**
```bash
# Verify MCP server configuration
{
  "mcpServers": {
    "insight-digger": {
      "command": "npx",
      "args": ["-y", "@sandsiv/insight-digger-mcp"],
      "env": {
        "MCP_CLIENT_URL": "http://localhost:33000"
      }
    }
  }
}

# Restart Claude Desktop completely
# Kill all Claude Desktop processes and restart

# Test MCP bridge manually
npx @sandsiv/insight-digger-mcp
```

## Authentication Issues

#### ❌ "Invalid JWT token" or "Authentication failed"

**Symptoms:**
- API returns 401 errors
- "JWT token validation failed"
- Cannot initialize session

**Diagnosis:**
```bash
# Test JWT token manually
curl -H "Authorization: Bearer your-jwt-token" \
  https://api.sandsiv.com/api/validate

# Check token format
echo "your-jwt-token" | base64 -d

# Check token expiration
python -c "
import jwt
token = 'your-jwt-token'
print(jwt.decode(token, options={'verify_signature': False}))
"
```

**Solutions:**
```bash
# Get new JWT token from your authentication provider
# Update session with new token
curl -X POST http://localhost:33000/init \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","apiUrl":"https://api.example.com","jwtToken":"new-token"}'

# Check API URL format
# Should be: https://api.sandsiv.com (no trailing slash)
```

## Performance Issues

#### ❌ "Slow response times"

**Symptoms:**
- API calls take longer than expected
- Timeouts on large datasets
- High memory usage

**Diagnosis:**
```bash
# Check system resources
top
htop
iostat 1

# Check Redis performance
redis-cli --stat

# Check network latency
ping api.sandsiv.com
traceroute api.sandsiv.com
```

**Solutions:**
```bash
# Increase timeouts
# In config/settings.py:
DEFAULT_TIMEOUT = 180

# Optimize Redis
redis-cli config set maxmemory 256mb
redis-cli config set maxmemory-policy allkeys-lru

# Scale horizontally
# Run multiple Flask workers
python src/python/scripts/start_flask_api.py --port 33001 &
python src/python/scripts/start_flask_api.py --port 33002 &
```

#### ❌ "Memory leaks" or "High memory usage"

**Symptoms:**
- Memory usage grows over time
- System becomes slow
- Out of memory errors

**Diagnosis:**
```bash
# Monitor memory usage
ps aux --sort=-%mem | head -10

# Check Python memory usage
python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"

# Check Redis memory
redis-cli info memory
```

**Solutions:**
```bash
# Restart services periodically
pkill -f start_flask_api
python src/python/scripts/start_flask_api.py &

# Configure Redis memory limits
redis-cli config set maxmemory 512mb

# Monitor and restart if needed
# Add to crontab:
# 0 */6 * * * /path/to/restart_services.sh
```

## Development Issues

#### ❌ "Import errors during development"

**Symptoms:**
- Cannot import modules
- "ModuleNotFoundError" in development
- Tests fail with import errors

**Diagnosis:**
```bash
# Check virtual environment
which python
pip list

# Check PYTHONPATH
echo $PYTHONPATH

# Check current directory
pwd
ls -la
```

**Solutions:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install in development mode
pip install -e .

# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run from project root
cd /path/to/insight_digger_mcp
python -m src.python.scripts.start_flask_api
```

#### ❌ "Tests fail"

**Symptoms:**
- Unit tests fail
- Integration tests timeout
- Test setup errors

**Diagnosis:**
```bash
# Run tests with verbose output
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/unit/test_flask_api.py -v

# Check test environment
python -m pytest --collect-only
```

**Solutions:**
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Set up test environment
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Run tests with coverage
python -m pytest tests/ --cov=src/python/insight_digger_mcp
```

## Production Issues

#### ❌ "Service crashes in production"

**Symptoms:**
- Services stop unexpectedly
- No response from API
- High error rates

**Diagnosis:**
```bash
# Check service logs
journalctl -u insight-digger-mcp -f

# Check system logs
tail -f /var/log/syslog | grep insight

# Check resource limits
ulimit -a
```

**Solutions:**
```bash
# Set up proper service management
# Create systemd service file
sudo systemctl enable insight-digger-mcp
sudo systemctl start insight-digger-mcp

# Monitor with supervisor
pip install supervisor
# Add supervisord configuration

# Set up log rotation
sudo logrotate -d /etc/logrotate.d/insight-digger-mcp
```

#### ❌ "Database/Redis connection issues in production"

**Symptoms:**
- Intermittent connection failures
- "Connection pool exhausted"
- Redis timeouts

**Diagnosis:**
```bash
# Check Redis connection limits
redis-cli config get maxclients

# Check connection pool settings
redis-cli client list

# Monitor connections
watch "redis-cli client list | wc -l"
```

**Solutions:**
```bash
# Increase Redis connection limits
redis-cli config set maxclients 10000

# Configure connection pooling
# In config/settings.py:
REDIS_CONNECTION_POOL_SIZE = 50

# Set up Redis clustering for high availability
# Configure Redis Sentinel or Cluster mode
```

## Monitoring and Debugging

### Enable Debug Logging

```bash
# Set debug environment variables
export FLASK_DEBUG=1
export MCP_LOG_LEVEL=DEBUG

# Enable verbose logging
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python src/python/scripts/start_flask_api.py --debug
```

### Log Locations

```bash
# Application logs
tail -f logs/flask_api.log
tail -f logs/mcp_server.log

# System logs
sudo journalctl -u insight-digger-mcp -f

# Redis logs
sudo journalctl -u redis-server -f

# Claude Desktop logs (macOS)
tail -f ~/Library/Logs/Claude/mcp*.log
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "=== Insight Digger MCP Health Check ==="

# Check Flask API
echo -n "Flask API: "
if curl -s http://localhost:33000/health | grep -q "ok"; then
    echo "✅ OK"
else
    echo "❌ FAILED"
fi

# Check Redis
echo -n "Redis: "
if redis-cli ping | grep -q "PONG"; then
    echo "✅ OK"
else
    echo "❌ FAILED"
fi

# Check external API
echo -n "External API: "
if curl -s --connect-timeout 5 https://api.sandsiv.com/health | grep -q "ok"; then
    echo "✅ OK"
else
    echo "❌ FAILED"
fi

echo "=== End Health Check ==="
```

## Getting Help

### Log Collection for Support

```bash
# Collect system information
cat > debug_info.txt << EOF
System: $(uname -a)
Python: $(python --version)
Node.js: $(node --version)
Redis: $(redis-cli --version)

Flask API Status:
$(curl -s http://localhost:33000/health || echo "FAILED")

Redis Status:
$(redis-cli ping || echo "FAILED")

Recent Logs:
$(tail -50 logs/flask_api.log)
EOF
```

### Common Support Questions

1. **What's my session ID?** 
   - Check your client code or logs for the session_id used in API calls

2. **How do I reset everything?**
   ```bash
   pkill -f "start_flask_api"
   redis-cli flushdb
   rm -rf logs/*
   python src/python/scripts/start_flask_api.py
   ```

3. **How do I check if it's working?**
   ```bash
   curl http://localhost:33000/health
   curl http://localhost:33000/tools-schema
   ```

4. **Where are the configuration files?**
   - Main config: `config/settings.py`
   - Environment: `config/.env`
   - Claude Desktop: `~/.config/claude/claude_desktop_config.json`

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check the full [documentation index](../index.md)
- **API Reference**: Review [HTTP API documentation](../api/http-api.md)
- **Development**: See [development setup guide](../development/development-setup.md)

---

**Remember**: Most issues can be resolved by restarting services and checking logs. When in doubt, start with the health check commands at the top of this guide. 