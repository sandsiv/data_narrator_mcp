# Insight Digger MCP

Enterprise-grade Model Context Protocol (MCP) system for data analysis with Claude Desktop integration.

## Architecture Overview

This project provides a sophisticated **3-layer MCP architecture** designed for enterprise environments:

1. **MCP Bridge** ↔ **MCP Client Flask API** (Custom HTTP REST endpoints)  
2. **MCP Client Flask API** ↔ **MCP Server subprocess** (Standard MCP protocol)  
3. **MCP Server** ↔ **Backend Data API** (HTTP calls to enterprise backend)

### Key Enterprise Features

- **🔐 Dynamic JWT Authentication**: 14-day JWT tokens with session management
- **🧠 Intelligent Caching**: Parameter caching and auto-injection for efficient workflows  
- **📋 Workflow Guidance**: LLM-optimized tool orchestration with conversation management
- **👥 Multi-User Support**: Centralized service with session isolation
- **🏢 Enterprise Integration**: Compatible with existing authentication and monitoring systems

## Setup Options

### Option 1: Claude Desktop Integration (Recommended)

**For end users who want to use Claude Desktop with Insight Digger:**

#### 1. Install the NPX Bridge
```bash
npx @yourcompany/insight-digger-mcp
```

#### 2. Configure Claude Desktop
Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "insight-digger": {
      "command": "npx",
      "args": ["-y", "@sandsiv/data-narrator-mcp@1.0.0"],
      "env": {
        "MCP_CLIENT_URL": "https://your-mcp-service.com"
      }
    }
  }
}
```

#### 3. Usage in Claude Desktop
1. **Authenticate first:** Use the `setup_authentication` tool with your API URL and JWT token
2. **Start analysis:** Begin with `list_sources` to see available data
3. **Follow the workflow:** The system guides you through multi-step analysis processes

### Option 2: Direct API Integration (For developers)

**For custom integrations or testing:**

#### 1. Start the MCP Client Service
```bash
# Install dependencies
pip install -r requirements.txt

# Start the Flask API service  
cd mcp_client
python -m flask run --host=0.0.0.0 --port=5000
```

#### 2. Use the REST API
```bash
# Initialize session
curl -X POST http://localhost:5000/init \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session", "apiUrl": "https://your-api.com", "jwtToken": "your-jwt"}'

# Get available tools
curl -X POST http://localhost:5000/tools \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session"}'

# Call a tool
curl -X POST http://localhost:5000/call-tool \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session", "tool": "list_sources", "params": {}}'
```

## Development Setup

### Prerequisites
- Python 3.8+
- Node.js 18+ (for NPX bridge)
- Access to Insight Digger backend API

### Local Development
```bash
# Clone the repository
git clone <repository-url>
cd insight_digger_mcp

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies (for bridge)
npm install

# Run tests
python test_mcp_tools.py
python mcp_client/test_client.py
```

### Testing the NPX Bridge Locally
```bash
# Start your MCP client service
cd mcp_client && python server.py

# In another terminal, test the bridge
cd src && node index.js
# Use the MCP Inspector or Claude Desktop to test
```

## Authentication Flow

### JWT Token Management
- **Lifetime**: 14 days
- **Refresh**: Through the main platform web UI (outside MCP scope)
- **Validation**: Bridge handles expired tokens by requesting re-authentication

### Session Management
- **Single Session**: One active session per bridge instance
- **Session ID**: UUID generated for each bridge startup
- **Isolation**: Multiple Claude Desktop instances use separate sessions

## Tools & Workflow

### Available Analysis Tools
The system provides LLM-optimized tools for:
- 📊 **Data Source Discovery**: `list_sources`, `get_source_structure`
- ⚙️ **Analysis Configuration**: `prepare_analysis_configuration` 
- 🚀 **Execution**: `execute_analysis_from_config`
- 📈 **Results**: Interactive dashboards and summaries

### Intelligent Caching
- **Parameter Injection**: Previously fetched data automatically included in subsequent calls
- **Workflow Memory**: System remembers source selections, configurations, and analysis state
- **Efficiency**: LLM doesn't need to repeat large data structures between steps

### Error Handling
- **Authentication Errors**: Clear guidance for JWT/URL validation failures
- **Tool Errors**: Contextual error messages from backend systems
- **Session Errors**: Automatic cleanup and re-authentication prompts

## Configuration

### Environment Variables
- `MCP_CLIENT_URL`: URL of the MCP Client Flask API service
- `INSIGHT_DIGGER_API_URL`: Backend API URL (configured in MCP server layer)

### Service Configuration
The MCP Server (`mcp_server.py`) connects to your backend API using configuration provided during the `/init` call.

## Documentation

- [`docs/mcp_bridge_implementation_guide.md`](docs/mcp_bridge_implementation_guide.md) - Detailed bridge architecture
- [`docs/integration_guide.md`](docs/integration_guide.md) - Integration patterns
- [`docs/mcp_client_development_plan.md`](docs/mcp_client_development_plan.md) - Client development guide
- [`docs/mcp_server_development_plan.md`](docs/mcp_server_development_plan.md) - Server development guide

## Production Deployment

### Service Deployment
```bash
# Install as systemd service (Linux)
sudo cp insight-digger-mcp.service /etc/systemd/system/
sudo systemctl enable insight-digger-mcp
sudo systemctl start insight-digger-mcp
```

### NPX Package Publishing
```bash
# Build and publish the bridge package
npm version patch
npm publish --access public
```

### Monitoring
- Service logs: `journalctl -u insight-digger-mcp -f`
- Bridge logs: Console output in Claude Desktop
- Session tracking: All sessions logged with UUIDs

## Security & Production Readiness

✅ **Status**: Ready for external publication  
🔐 **Security**: Comprehensive credential validation implemented  
📊 **Performance**: Optimized with session reuse and direct validation  

### Security Features
- **Immediate credential validation** during `/init` endpoint
- **Session reuse optimization** - no redundant validation calls
- **Proper HTTP status codes** (401 for auth failures, 500 for server errors)  
- **Input validation** for API URLs and JWT tokens
- **Resource efficiency** - MCP servers created only for valid credentials
- **5-second timeout** for validation requests

### Security Considerations
- **JWT Tokens**: Never logged or stored permanently
- **Session Isolation**: Proper cleanup prevents cross-session data leakage  
- **HTTPS Required**: All production communications must use HTTPS
- **Enterprise Auth**: Integrates with existing authentication systems
- **Immediate Auth Feedback**: Invalid credentials rejected in <5 seconds
- **Resource Protection**: No MCP instances created for invalid credentials

See [SECURITY.md](SECURITY.md) for detailed security documentation.

## Support

For issues or questions:
1. Check the documentation in the `docs/` folder
2. Review the service logs for error details
3. Verify JWT token validity and API connectivity
4. Ensure MCP Client service is running and accessible

## License

MIT License - See LICENSE file for details. 