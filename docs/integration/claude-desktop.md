# Claude Desktop Integration

Complete guide for integrating Insight Digger MCP with Claude Desktop for AI-powered data analysis workflows.

## Overview

Claude Desktop integration enables natural language data analysis through the Model Context Protocol (MCP). Users can ask analytical questions in plain English and receive guided workflows with interactive dashboards and insights.

## Prerequisites

- **Claude Desktop** installed and running
- **Insight Digger MCP** system deployed and accessible
- **Sandsiv+ API credentials** (API URL and JWT token)
- **Node.js 18+** for the MCP bridge

## Installation Steps

### 1. Install the MCP Bridge

Choose one of these installation methods:

#### Option A: Global NPM Installation
```bash
# Install globally
npm install -g @sandsiv/data-narrator-mcp

# Verify installation
data-narrator-mcp --version
```

#### Option B: Direct NPX Usage (Recommended)
```bash
# No installation needed - NPX will download on demand
npx -y @sandsiv/data-narrator-mcp --version
```

### 2. Configure Claude Desktop

Locate your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

Add the MCP server configuration:

```json
{
  "mcpServers": {
    "data-narrator": {
      "command": "npx",
      "args": ["-y", "@sandsiv/data-narrator-mcp"],
      "env": {
        "MCP_CLIENT_URL": "http://localhost:33000"
      }
    }
  }
}
```

**Configuration Options:**
- `MCP_CLIENT_URL`: URL of your Flask API server
- `MCP_LOG_LEVEL`: Set to "DEBUG" for troubleshooting
- `MCP_TIMEOUT`: Request timeout in seconds (default: 60)

### 3. Restart Claude Desktop

**Important**: Completely close and restart Claude Desktop to load the new MCP server.

1. Quit Claude Desktop entirely (not just minimize)
2. Wait 5 seconds
3. Restart Claude Desktop
4. Look for the MCP connection indicator

## First-Time Setup

### 1. Verify Connection

In a new Claude Desktop conversation, type:
```
Hello! Can you help me with data analysis?
```

You should see a response indicating that data analysis tools are available and authentication is required.

### 2. Authentication Flow

Claude will guide you through authentication:

1. **API URL**: Your Sandsiv+ platform URL (e.g., `https://platform.sandsiv.com`)
2. **JWT Token**: Your authentication token from Sandsiv+

**Example Authentication:**
```
I need to analyze sales data. Please help me set up access.
```

Claude will respond with authentication prompts and guide you through the setup.

### 3. Test Basic Functionality

Try this simple workflow:
```
Please list available data sources that contain "sales" data
```

If successful, you'll see a list of available data sources.

## Usage Patterns

### Basic Analysis Workflow

1. **Start with a Question**:
   ```
   What factors are driving our Q4 sales performance?
   ```

2. **Source Selection**:
   Claude will help you find and select relevant data sources.

3. **Guided Analysis**:
   Follow Claude's step-by-step guidance through:
   - Data source analysis
   - Strategy generation
   - Dashboard creation
   - Insight generation

4. **Interactive Results**:
   Receive dashboard links, charts, and AI-generated insights.

### Advanced Workflows

#### Multi-Source Analysis
```
I want to compare customer satisfaction scores with sales performance across different regions. Can you help me create a comprehensive analysis?
```

#### Trend Analysis
```
Show me the trends in our key metrics over the last 12 months and identify any seasonal patterns or anomalies.
```

#### Predictive Analysis
```
Based on our historical data, what can we expect for next quarter's performance?
```

## Workflow Examples

### Example 1: Sales Performance Analysis

**User**: "I need to understand what's driving our sales performance this quarter"

**Claude Response**: 
- Authenticates if needed
- Lists available sales-related data sources
- Guides through source selection
- Analyzes data structure
- Generates analysis strategy
- Creates interactive dashboard
- Provides AI insights and recommendations

### Example 2: Customer Segmentation

**User**: "Help me segment our customers based on their behavior and value"

**Claude Response**:
- Identifies customer data sources
- Analyzes customer attributes and behaviors
- Suggests segmentation strategies
- Creates visualization dashboards
- Provides actionable insights for each segment

### Example 3: Operational Efficiency

**User**: "I want to identify bottlenecks in our operations"

**Claude Response**:
- Discovers operational data sources
- Maps process flow and metrics
- Identifies performance indicators
- Creates operational dashboards
- Highlights efficiency opportunities

## Authentication Management

### Initial Setup
Claude will prompt for credentials when first using data analysis tools:
```
To access your data, I need:
1. API URL: Your Sandsiv+ platform URL
2. JWT Token: Your authentication token
```

### Token Refresh
If your session expires, Claude will guide you through re-authentication:
```
Your session has expired. Please provide a new JWT token to continue.
```

### Multiple Environments
You can switch between different environments by providing different API URLs:
- Development: `https://dev.platform.sandsiv.com`
- Staging: `https://staging.platform.sandsiv.com`
- Production: `https://platform.sandsiv.com`

## Troubleshooting

### MCP Server Not Available

**Symptoms**: Claude doesn't offer data analysis tools

**Solutions**:
1. Check Claude Desktop configuration file syntax
2. Restart Claude Desktop completely
3. Verify MCP bridge installation:
   ```bash
   npx -y @sandsiv/data-narrator-mcp --version
   ```

### Authentication Failures

**Symptoms**: "Invalid credentials" or "Authentication failed"

**Solutions**:
1. Verify API URL format (no trailing slash)
2. Check JWT token validity
3. Test credentials directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-api-url/api/validate
   ```

### Connection Issues

**Symptoms**: "Connection refused" or timeout errors

**Solutions**:
1. Verify Flask API is running:
   ```bash
   curl http://localhost:33000/health
   ```
2. Check firewall settings
3. Verify `MCP_CLIENT_URL` in configuration

### Performance Issues

**Symptoms**: Slow responses or timeouts

**Solutions**:
1. Increase timeout in configuration:
   ```json
   "env": {
     "MCP_CLIENT_URL": "http://localhost:33000",
     "MCP_TIMEOUT": "120"
   }
   ```
2. Check system resources
3. Optimize data source queries

## Advanced Configuration

### Custom Environment Variables

```json
{
  "mcpServers": {
    "data-narrator": {
      "command": "npx",
      "args": ["-y", "@sandsiv/data-narrator-mcp"],
      "env": {
        "MCP_CLIENT_URL": "http://localhost:33000",
        "MCP_LOG_LEVEL": "DEBUG",
        "MCP_TIMEOUT": "120",
        "MCP_RETRY_ATTEMPTS": "3",
        "MCP_SESSION_PREFIX": "claude-desktop"
      }
    }
  }
}
```

**Environment Variables:**
- `MCP_CLIENT_URL`: Flask API endpoint
- `MCP_LOG_LEVEL`: Logging level (DEBUG, INFO, WARN, ERROR)
- `MCP_TIMEOUT`: Request timeout in seconds
- `MCP_RETRY_ATTEMPTS`: Number of retry attempts
- `MCP_SESSION_PREFIX`: Session ID prefix for identification

### Multiple Instances

You can configure multiple MCP servers for different environments:

```json
{
  "mcpServers": {
    "data-narrator-dev": {
      "command": "npx",
      "args": ["-y", "@sandsiv/data-narrator-mcp"],
      "env": {
        "MCP_CLIENT_URL": "http://localhost:33000"
      }
    },
    "data-narrator-prod": {
      "command": "npx",
      "args": ["-y", "@sandsiv/data-narrator-mcp"],
      "env": {
        "MCP_CLIENT_URL": "https://api.yourcompany.com"
      }
    }
  }
}
```

## Best Practices

### 1. Session Management
- Use descriptive questions to maintain context
- Keep analysis sessions focused on related topics
- Re-authenticate when switching between different data environments

### 2. Data Privacy
- Never share JWT tokens in conversation logs
- Use environment-specific credentials
- Regularly rotate authentication tokens

### 3. Performance Optimization
- Start with specific, targeted questions
- Use filters and constraints to limit data scope
- Cache frequently used data sources

### 4. Workflow Efficiency
- Follow Claude's guided workflow recommendations
- Save important dashboard URLs for future reference
- Document successful analysis patterns for reuse

## Integration Examples

### Python Script Integration
```python
# Example: Using insights in custom applications
import requests

def get_analysis_insights(question, api_url, jwt_token):
    session_id = "python-integration"
    
    # Initialize session
    init_response = requests.post(f"{api_url}/init", json={
        "session_id": session_id,
        "apiUrl": "https://platform.sandsiv.com",
        "jwtToken": jwt_token
    })
    
    # Run analysis workflow
    # ... (implement full workflow)
    
    return insights

# Usage
insights = get_analysis_insights(
    "What are our top performing products?",
    "http://localhost:33000",
    "your-jwt-token"
)
```

### Jupyter Notebook Integration
```python
# Example: Using in data science workflows
from insight_digger_client import InsightDiggerClient

client = InsightDiggerClient("http://localhost:33000", "jupyter-session")
client.init_session("https://platform.sandsiv.com", "jwt-token")

# Get data sources
sources = client.call_tool("list_sources", {"search": "customer"})

# Analyze structure
analysis = client.call_tool("analyze_source_structure", {"sourceId": sources['data'][0]['id']})

# Generate insights
insights = client.call_tool("generate_strategy", {"question": "What drives customer retention?"})
```

## Support and Resources

### Getting Help
- **Documentation**: [Full documentation index](../index.md)
- **API Reference**: [HTTP API documentation](../api/http-api.md)
- **Troubleshooting**: [Troubleshooting guide](../deployment/troubleshooting.md)

### Community
- **GitHub Issues**: Report bugs and feature requests
- **Discussions**: Share usage patterns and best practices
- **Examples**: Community-contributed workflow examples

### Updates
- **Release Notes**: Check [changelog](../reference/changelog.md) for updates
- **Migration**: Follow [migration guide](../reference/migration-guide.md) for upgrades

---

**🎉 You're Ready!** Claude Desktop is now equipped with powerful data analysis capabilities. Start asking analytical questions and let Claude guide you through sophisticated data workflows. 