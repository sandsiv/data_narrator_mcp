# HTTP API Reference

Complete reference for the Insight Digger MCP HTTP API. This API enables direct integration with the system without requiring MCP protocol knowledge.

## Base URL

```
http://localhost:33000  # Development
https://your-domain.com # Production
```

## Authentication

All endpoints except `/health` and `/tools-schema` require session-based authentication:

1. **Initialize session** with `/init` endpoint
2. **Include session_id** in all subsequent requests
3. **Session expires** after 24 hours of inactivity (configurable)

## Common Response Format

All API responses follow this structure:

```json
{
  "status": "success" | "error",
  "data": {...},           // Present on success
  "error": "error message" // Present on error
}
```

## Endpoints

### Health Check

#### `GET /health`

Simple health check endpoint.

**Request:**
```bash
curl http://localhost:33000/health
```

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200` - Service is healthy
- `503` - Service is unhealthy

---

### Tools Schema

#### `GET /tools-schema`

Get tool schemas without authentication. Useful for discovering available tools before authentication.

**Request:**
```bash
curl http://localhost:33000/tools-schema
```

**Response:**
```json
{
  "status": "success",
  "tools": [
    {
      "name": "list_sources",
      "description": "List available data sources...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "search": {
            "type": "string",
            "description": "Search term for filtering sources"
          },
          "page": {
            "type": "integer",
            "description": "Page number for pagination"
          }
        }
      }
    }
  ],
  "system_info": {
    "system_name": "Sandsiv+ Insight Digger",
    "capabilities": [...],
    "authentication_required": true
  }
}
```

---

### Session Management

#### `POST /init`

Initialize a new session with authentication credentials.

**Request:**
```bash
curl -X POST http://localhost:33000/init \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "unique-session-identifier",
    "apiUrl": "https://api.sandsiv.com",
    "jwtToken": "your-jwt-token"
  }'
```

**Parameters:**
- `session_id` (string, required) - Unique identifier for this session
- `apiUrl` (string, required) - Base URL for the Sandsiv+ API
- `jwtToken` (string, required) - JWT authentication token

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200` - Session initialized successfully
- `400` - Missing required parameters
- `401` - Invalid credentials
- `500` - Server error

**Error Examples:**
```json
{
  "status": "error",
  "error": "Missing session_id, apiUrl, or jwtToken"
}
```

#### `POST /shutdown`

Gracefully shutdown a session and clean up resources.

**Request:**
```bash
curl -X POST http://localhost:33000/shutdown \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "unique-session-identifier"
  }'
```

**Response:**
```json
{
  "status": "ok",
  "message": "Session unique-session-identifier shut down."
}
```

---

### Tool Discovery

#### `POST /tools`

List available tools for an authenticated session.

**Request:**
```bash
curl -X POST http://localhost:33000/tools \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "unique-session-identifier"
  }'
```

**Response:**
```json
{
  "tools": [
    {
      "name": "validate_settings",
      "description": "Validate API settings by testing connection...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "apiUrl": {"type": "string"},
          "jwtToken": {"type": "string"}
        },
        "required": ["apiUrl", "jwtToken"]
      }
    },
    {
      "name": "list_sources",
      "description": "List available data sources...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "search": {"type": "string"},
          "page": {"type": "integer"},
          "limit": {"type": "integer"}
        }
      }
    }
  ],
  "workflow_guidance": {
    "workflow": {
      "description": "This is a data analysis workflow...",
      "recommended_workflow": {
        "steps": [...]
      }
    }
  }
}
```

**Status Codes:**
- `200` - Tools retrieved successfully
- `409` - Session not found or expired
- `500` - Server error

---

### Tool Execution

#### `POST /call-tool`

Execute a specific tool with parameters.

**Request:**
```bash
curl -X POST http://localhost:33000/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "unique-session-identifier",
    "tool": "list_sources",
    "params": {
      "search": "sales",
      "limit": 10
    }
  }'
```

**Parameters:**
- `session_id` (string, required) - Session identifier
- `tool` (string, required) - Name of the tool to execute
- `params` (object, optional) - Tool-specific parameters

**Response:**
```json
{
  "status": "success",
  "count": 1877,
  "data": [
    {
      "id": "96-WEB",
      "title": "Sales Data Q4",
      "type": "survey",
      "updated": "2024-01-01T12:00:00Z",
      "numberOfColumns": 35
    }
  ]
}
```

**Status Codes:**
- `200` - Tool executed successfully
- `400` - Invalid parameters
- `409` - Session not found or expired
- `500` - Tool execution failed

## Tool-Specific API Documentation

### validate_settings

Validate API connection and credentials.

**Parameters:**
- `apiUrl` (string) - Auto-injected from session
- `jwtToken` (string) - Auto-injected from session

**Response:**
```json
{
  "status": "success"
}
```

### list_sources

List available data sources with optional filtering.

**Parameters:**
- `search` (string, optional) - Search term for filtering
- `page` (integer, optional) - Page number (default: 1)
- `limit` (integer, optional) - Results per page (default: 20)

**Response:**
```json
{
  "status": "success",
  "count": 1877,
  "data": [
    {
      "id": "source-123",
      "title": "Sales Data",
      "type": "survey",
      "updated": "2024-01-01T12:00:00Z",
      "numberOfColumns": 35
    }
  ]
}
```

### analyze_source_structure

Analyze the structure of a specific data source.

**Parameters:**
- `sourceId` (string, required) - ID of the source to analyze

**Response:**
```json
{
  "status": "success",
  "message": "Successfully retrieved and analyzed the source structure.",
  "columnAnalysis": [
    {
      "name": "sales_amount",
      "type": "numeric",
      "description": "Total sales amount",
      "stats": {
        "min": 0,
        "max": 10000,
        "mean": 2500
      }
    }
  ]
}
```

### generate_strategy

Generate an analysis strategy for a question.

**Parameters:**
- `question` (string, required) - The analytical question
- `columnAnalysis` (array) - Auto-injected from previous step

**Response:**
```json
{
  "status": "success",
  "strategy": {
    "approach": "correlation_analysis",
    "key_metrics": ["sales_amount", "promotion_rate"],
    "visualization_types": ["scatter_plot", "bar_chart"],
    "analysis_steps": [...]
  }
}
```

### create_configuration

Create dashboard configuration from analysis inputs.

**Parameters:**
- `question` (string) - Auto-injected from session
- `columnAnalysis` (array) - Auto-injected from session
- `strategy` (object) - Auto-injected from session

**Response:**
```json
{
  "status": "success",
  "markdownConfig": "# Dashboard Configuration\n\n## Charts\n...",
  "message": "Configuration created successfully"
}
```

### create_dashboard

Create dashboard from configuration.

**Parameters:**
- `markdownConfig` (string) - Auto-injected from previous step
- `sourceStructure` (object) - Auto-injected from session

**Response:**
```json
{
  "status": "success",
  "dashboardUrl": "https://platform.sandsiv.com/dashboard/123",
  "chartConfigs": [
    {
      "id": "chart-1",
      "type": "bar_chart",
      "title": "Sales by Region"
    }
  ]
}
```

### get_charts_data

Fetch data for dashboard charts.

**Parameters:**
- `chartConfigs` (array) - Auto-injected from previous step

**Response:**
```json
{
  "status": "success",
  "charts_found": ["chart-1", "chart-2"],
  "message": "Data fetched for 2 charts"
}
```

### analyze_charts

Generate AI insights from chart data.

**Parameters:**
- `chartData` (object) - Auto-injected from previous step
- `question` (string) - Auto-injected from session

**Response:**
```json
{
  "status": "success",
  "insights": {
    "summary": "Key finding: Promotion rate strongly correlates with sales...",
    "chart_insights": [
      {
        "chart_id": "chart-1",
        "insight": "Sales increase 40% during promotional periods",
        "confidence": 0.85
      }
    ],
    "recommendations": [
      "Increase promotional frequency during Q4",
      "Focus promotions on high-value products"
    ]
  }
}
```

## Parameter Caching and Injection

The API automatically caches and injects parameters to simplify multi-step workflows:

### Input Parameter Caching
All parameters sent to tools are automatically cached in the session:
```json
{
  "session_id": "session-123",
  "tool": "generate_strategy",
  "params": {
    "question": "What factors improve sales?"
  }
}
```
The `question` parameter is now cached for future tool calls.

### Output Result Caching
Successful tool responses are cached:
```json
{
  "status": "success",
  "strategy": {...},
  "columnAnalysis": [...]
}
```
Both `strategy` and `columnAnalysis` are cached for injection.

### Automatic Parameter Injection
Subsequent tool calls automatically receive cached parameters:
```json
{
  "session_id": "session-123",
  "tool": "create_configuration",
  "params": {}  // Empty - question, columnAnalysis, strategy auto-injected
}
```

### Cache Priority
- **User-provided parameters** always take precedence
- **Cached parameters** are injected only if not provided
- **Session credentials** (apiUrl, jwtToken) are always injected

## Error Handling

### Common Error Responses

#### Session Not Found (409)
```json
{
  "status": "error",
  "error": "Session session-123 not found or expired. Please run /init first."
}
```

#### Invalid Parameters (400)
```json
{
  "status": "error",
  "error": "Missing required parameter: sourceId"
}
```

#### Authentication Failed (401)
```json
{
  "status": "error",
  "error": "API validation failed: Invalid JWT token"
}
```

#### Tool Execution Failed (500)
```json
{
  "status": "error",
  "error": "Tool execution failed: Connection timeout to external API"
}
```

### Error Recovery

1. **Session Expired**: Re-initialize with `/init`
2. **Invalid Parameters**: Check tool schema with `/tools-schema`
3. **API Errors**: Verify credentials and external API status
4. **Server Errors**: Check logs and retry with exponential backoff

## Rate Limiting

- **Default**: 100 requests per minute per session
- **Burst**: Up to 10 concurrent requests per session
- **Headers**: Rate limit info in response headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## SDKs and Examples

### Python SDK Example
```python
import requests

class InsightDiggerClient:
    def __init__(self, base_url, session_id):
        self.base_url = base_url
        self.session_id = session_id
    
    def init_session(self, api_url, jwt_token):
        response = requests.post(f"{self.base_url}/init", json={
            "session_id": self.session_id,
            "apiUrl": api_url,
            "jwtToken": jwt_token
        })
        return response.json()
    
    def call_tool(self, tool_name, params=None):
        response = requests.post(f"{self.base_url}/call-tool", json={
            "session_id": self.session_id,
            "tool": tool_name,
            "params": params or {}
        })
        return response.json()

# Usage
client = InsightDiggerClient("http://localhost:33000", "my-session")
client.init_session("https://api.sandsiv.com", "jwt-token")
sources = client.call_tool("list_sources", {"search": "sales"})
```

### JavaScript SDK Example
```javascript
class InsightDiggerClient {
  constructor(baseUrl, sessionId) {
    this.baseUrl = baseUrl;
    this.sessionId = sessionId;
  }
  
  async initSession(apiUrl, jwtToken) {
    const response = await fetch(`${this.baseUrl}/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: this.sessionId,
        apiUrl,
        jwtToken
      })
    });
    return response.json();
  }
  
  async callTool(toolName, params = {}) {
    const response = await fetch(`${this.baseUrl}/call-tool`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: this.sessionId,
        tool: toolName,
        params
      })
    });
    return response.json();
  }
}

// Usage
const client = new InsightDiggerClient("http://localhost:33000", "my-session");
await client.initSession("https://api.sandsiv.com", "jwt-token");
const sources = await client.callTool("list_sources", { search: "sales" });
```

## Testing the API

### Using curl
```bash
# Initialize session
curl -X POST http://localhost:33000/init \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","apiUrl":"https://api.example.com","jwtToken":"token"}'

# List tools
curl -X POST http://localhost:33000/tools \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test"}'

# Execute tool
curl -X POST http://localhost:33000/call-tool \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","tool":"list_sources","params":{"search":"sales"}}'
```

### Using HTTPie
```bash
# Initialize session
http POST localhost:33000/init session_id=test apiUrl=https://api.example.com jwtToken=token

# List tools
http POST localhost:33000/tools session_id=test

# Execute tool
http POST localhost:33000/call-tool session_id=test tool=list_sources params:='{"search":"sales"}'
```

This API provides a powerful, flexible interface for integrating AI-driven data analysis capabilities into any application. 