# Quick Start Guide

Get Insight Digger MCP running in under 10 minutes with this streamlined setup guide.

## Prerequisites

- **Python 3.8+** with pip
- **Node.js 18+** with npm
- **Redis server** (local or remote)
- **Git** for cloning the repository

## 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/insight_digger_mcp.git
cd insight_digger_mcp

# Run the automated setup script
./scripts/setup/install_dependencies.sh --dev

# Activate the virtual environment
source venv/bin/activate
```

## 2. Configure Environment

```bash
# Copy the example environment file
cp config/.env.example config/.env

# Edit configuration (use your preferred editor)
nano config/.env
```

**Minimum required configuration:**
```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# API Configuration
INSIGHT_DIGGER_API_URL=https://your-sandsiv-api.com/api

# Server Configuration
MCP_CLIENT_PORT=33000
MCP_CLIENT_HOST=0.0.0.0
```

## 3. Start the Services

### Option A: Development Mode (Recommended for testing)
```bash
# Terminal 1: Start Flask API
npm run dev:flask

# Terminal 2: Test the API
curl http://localhost:33000/health
# Should return: {"status":"ok"}
```

### Option B: Production Mode
```bash
# Start as background service
python src/python/scripts/start_flask_api.py &

# Verify it's running
curl http://localhost:33000/health
```

## 4. Test with Claude Desktop

### Install the MCP Bridge
```bash
# Install globally via npm
npm install -g .

# Or use npx directly (no installation needed)
npx @sandsiv/insight-digger-mcp
```

### Configure Claude Desktop
Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
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
```

### Restart Claude Desktop
Close and reopen Claude Desktop to load the new MCP server.

## 5. First Analysis

In Claude Desktop, try this workflow:

1. **Authenticate**: 
   ```
   I need to analyze some data. Please help me set up authentication.
   ```

2. **Provide credentials** when prompted:
   - **API URL**: Your Sandsiv+ API endpoint
   - **JWT Token**: Your authentication token

3. **Start analysis**:
   ```
   Please list available data sources related to "sales"
   ```

4. **Follow the guided workflow** that Claude presents.

## 6. Verify Installation

Run the test suite to ensure everything is working:

```bash
# Run all tests
npm test

# Or run specific test categories
python -m pytest tests/unit/
cd src/nodejs && npm test
```

## Common Issues & Quick Fixes

### ❌ "Connection refused" error
**Problem**: Flask API not running
**Solution**: 
```bash
# Check if port is in use
lsof -i :33000

# Kill any existing processes
pkill -f "start_flask_api"

# Restart the API
npm run dev:flask
```

### ❌ "Redis connection failed"
**Problem**: Redis not running or misconfigured
**Solution**:
```bash
# Install and start Redis (Ubuntu/Debian)
sudo apt install redis-server
sudo systemctl start redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:alpine

# Test Redis connection
redis-cli ping
```

### ❌ "Module not found" errors
**Problem**: Dependencies not installed correctly
**Solution**:
```bash
# Reinstall dependencies
rm -rf venv node_modules
./scripts/setup/install_dependencies.sh --dev
source venv/bin/activate
```

### ❌ Claude Desktop doesn't see the MCP server
**Problem**: Configuration or bridge issues
**Solution**:
```bash
# Test the bridge directly
npx @sandsiv/insight-digger-mcp

# Check Claude Desktop logs
# macOS: ~/Library/Logs/Claude/
# Windows: %LOCALAPPDATA%/Claude/logs/
```

## Next Steps

### For End Users
- **Learn workflows**: Check [Workflow Examples](../integration/workflow-examples.md)
- **Troubleshooting**: See [Troubleshooting Guide](../deployment/troubleshooting.md)

### For Developers
- **API Integration**: Study [API Integration Guide](../integration/api-integration.md)
- **Development Setup**: Follow [Development Setup](../development/development-setup.md)

### For Administrators
- **Production Deployment**: Follow [Production Deployment](../deployment/production-deployment.md)
- **Security Setup**: Review [Security Guide](../deployment/security.md)

## Support

- **Documentation**: Browse the full [Documentation Index](../index.md)
- **API Reference**: Check [HTTP API Reference](../api/http-api.md)
- **Issues**: Report problems via GitHub issues
- **Community**: Join our development community

---

**🎉 Congratulations!** You now have Insight Digger MCP running and ready for data analysis workflows. 