# System Architecture

## Overview

The Insight Digger MCP system employs a sophisticated multi-layered architecture designed for enterprise scalability, security, and maintainability. The system bridges AI assistants with data analysis capabilities through a translation layer that preserves enterprise features while providing standard MCP compatibility.

## Architectural Principles

### 1. **Separation of Concerns**
Each component has a single, well-defined responsibility:
- **MCP Bridge**: Protocol translation and client management
- **Flask API**: Session management and enterprise logic
- **MCP Server**: Tool execution and data processing
- **Redis**: State management and caching

### 2. **Stateless Design**
- Workers can handle any request without affinity
- All state stored in Redis with automatic TTL
- Horizontal scaling without coordination
- Graceful handling of worker failures

### 3. **Security-First**
- JWT-based authentication at every layer
- Sensitive parameter filtering throughout
- Session isolation between users
- Secure credential management

### 4. **Performance Optimization**
- Intelligent parameter caching and injection
- Connection pooling for external APIs
- Asynchronous processing where possible
- Resource cleanup and management

## System Components

### Component Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        CD[Claude Desktop]
        CA[Custom Applications]
        WB[Web Browsers]
    end
    
    subgraph "Translation Layer"
        NB[Node.js MCP Bridge<br/>src/nodejs/src/index.js]
    end
    
    subgraph "API Gateway Layer"
        LB[Load Balancer<br/>Nginx/HAProxy]
    end
    
    subgraph "Application Layer"
        FA1[Flask Worker 1<br/>flask_api/app.py]
        FA2[Flask Worker 2<br/>flask_api/app.py]
        FA3[Flask Worker N<br/>flask_api/app.py]
    end
    
    subgraph "Session Layer"
        SM[Session Manager<br/>session_manager.py]
        RD[(Redis Cluster<br/>Sessions & Cache)]
    end
    
    subgraph "Processing Layer"
        MM1[MCP Manager 1<br/>mcp_manager.py]
        MM2[MCP Manager 2<br/>mcp_manager.py]
        MM3[MCP Manager N<br/>mcp_manager.py]
        
        MS1[MCP Server 1<br/>mcp_server/server.py]
        MS2[MCP Server 2<br/>mcp_server/server.py]
        MS3[MCP Server N<br/>mcp_server/server.py]
    end
    
    subgraph "External APIs"
        SAPI[Sandsiv+ API<br/>Data Analysis Platform]
        EAPI[External APIs<br/>Third-party Services]
    end
    
    subgraph "Configuration"
        CFG[Configuration System<br/>config/settings.py]
    end
    
    CD -.->|Standard MCP| NB
    CA -.->|HTTP API| LB
    WB -.->|HTTP API| LB
    
    NB -.->|HTTP API| LB
    LB --> FA1
    LB --> FA2
    LB --> FA3
    
    FA1 <-.-> SM
    FA2 <-.-> SM
    FA3 <-.-> SM
    SM <-.-> RD
    
    FA1 -.->|Create/Manage| MM1
    FA2 -.->|Create/Manage| MM2
    FA3 -.->|Create/Manage| MM3
    
    MM1 -.->|Subprocess| MS1
    MM2 -.->|Subprocess| MS2
    MM3 -.->|Subprocess| MS3
    
    MS1 -.->|HTTP| SAPI
    MS2 -.->|HTTP| SAPI
    MS3 -.->|HTTP| SAPI
    
    MS1 -.->|HTTP| EAPI
    MS2 -.->|HTTP| EAPI
    MS3 -.->|HTTP| EAPI
    
    FA1 -.-> CFG
    FA2 -.-> CFG
    FA3 -.-> CFG
    MS1 -.-> CFG
    MS2 -.-> CFG
    MS3 -.-> CFG
    
    classDef client fill:#e3f2fd,stroke:#1976d2
    classDef bridge fill:#f3e5f5,stroke:#7b1fa2
    classDef gateway fill:#e8f5e8,stroke:#388e3c
    classDef app fill:#fff3e0,stroke:#f57c00
    classDef session fill:#fce4ec,stroke:#c2185b
    classDef process fill:#e0f2f1,stroke:#00796b
    classDef external fill:#f1f8e9,stroke:#689f38
    classDef config fill:#e8eaf6,stroke:#3f51b5
    
    class CD,CA,WB client
    class NB bridge
    class LB gateway
    class FA1,FA2,FA3 app
    class SM,RD session
    class MM1,MM2,MM3,MS1,MS2,MS3 process
    class SAPI,EAPI external
    class CFG config
```

## Key Design Patterns

### 1. **Request-Response Flow**
Every request follows a consistent pattern:
1. Authentication validation
2. Session retrieval/creation
3. Parameter injection from cache
4. Tool execution
5. Result caching
6. Response delivery

### 2. **Resource Management**
- MCP servers created on-demand per request
- Automatic cleanup after tool execution
- Connection pooling for external APIs
- Memory-efficient session storage

### 3. **Error Handling**
- Graceful degradation on component failures
- Circuit breaker patterns for external APIs
- Comprehensive logging and monitoring
- Automatic retry mechanisms

This architecture ensures enterprise-grade reliability, security, and performance while maintaining compatibility with standard MCP protocols.

## Layer-by-Layer Analysis

### 1. Client Layer

#### Claude Desktop Integration
**Purpose**: Standard MCP client for AI assistants
**Protocol**: MCP over STDIO
**Features**:
- Native AI assistant integration
- Standard MCP tool discovery
- Authentication flow management
- Workflow guidance presentation

#### Custom Application Integration
**Purpose**: Direct HTTP API access for custom clients
**Protocol**: HTTP REST API
**Features**:
- Session-based authentication
- Tool execution and caching
- Custom workflow implementation
- Direct API access

### 2. Translation Layer

#### Node.js MCP Bridge
**Location**: `src/nodejs/src/index.js`
**Purpose**: Translate between MCP protocol and HTTP API

```javascript
// Key components of the bridge
const bridgeSession = {
  sessionId: null,
  authenticated: false,
  availableTools: [],
  workflowGuidance: null
};

// Authentication flow
async function setupAuthentication(args) {
  // 1. Initialize session with Flask API
  // 2. Fetch available tools
  // 3. Update tool presentation
}

// Tool call proxy
async function proxyToolCall(toolName, args) {
  // 1. Validate authentication
  // 2. Proxy to Flask API
  // 3. Return results
}
```

**Key Features**:
- Stateless design with session management
- Dynamic tool presentation based on authentication
- Workflow guidance injection
- Error handling and logging

### 3. API Gateway Layer

#### Load Balancer (Nginx/HAProxy)
**Purpose**: Distribute requests across Flask workers
**Configuration**:
```nginx
upstream flask_backend {
    server 127.0.0.1:33000;
    server 127.0.0.1:33001;
    server 127.0.0.1:33002;
}

server {
    listen 80;
    location / {
        proxy_pass http://flask_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Features**:
- Health check integration
- SSL termination
- Request routing
- Rate limiting

### 4. Application Layer

#### Flask Workers
**Location**: `src/python/insight_digger_mcp/flask_api/app.py`
**Purpose**: Enterprise HTTP API with session management

```python
# Key endpoints
@app.route('/init', methods=['POST'])
def init():
    # Session initialization and credential validation
    
@app.route('/tools', methods=['POST'])
def list_tools():
    # Tool discovery with session context
    
@app.route('/call-tool', methods=['POST'])
def call_tool():
    # Tool execution with parameter injection
```

**Key Features**:
- Multi-session support
- Credential validation
- Parameter caching and injection
- MCP server subprocess management

### 5. Session Layer

#### Session Manager
**Location**: `src/python/insight_digger_mcp/flask_api/session_manager.py`
**Purpose**: Redis-based session management

```python
class MCPSessionManager:
    def __init__(self):
        self.redis = redis.Redis(**MCPConfig.get_redis_connection_params())
        self.idle_ttl = MCPConfig.Session.IDLE_TTL
        
    def create_session(self, session_id, session_data):
        # Create session with TTL
        
    def get_session_data(self, session_id):
        # Retrieve and refresh TTL
        
    def update_session_data(self, session_id, updates):
        # Update and refresh TTL
```

**Key Features**:
- Automatic TTL management
- Session isolation
- Parameter caching
- Multi-worker compatibility

#### Redis Storage
**Purpose**: Distributed session storage and caching
**Configuration**:
```yaml
redis:
  host: localhost
  port: 6379
  db: 0
  ssl: false
  password: ${REDIS_PASSWORD}
```

**Data Structures**:
```json
{
  "mcp_session:session-123": {
    "apiUrl": "https://api.example.com",
    "jwtToken": "encrypted_token",
    "sourceId": "cached_source_id",
    "question": "cached_question",
    "strategy": {...},
    "last_accessed": "2024-01-01T12:00:00Z"
  }
}
```

### 6. Processing Layer

#### MCP Managers
**Location**: `src/python/insight_digger_mcp/flask_api/mcp_manager.py`
**Purpose**: Manage MCP server subprocesses

```python
class MCPServerManager:
    def start(self):
        # Start MCP server subprocess
        
    def call_tool(self, tool_name, params):
        # Execute tool via MCP protocol
        
    def stop(self):
        # Clean shutdown of subprocess
```

**Lifecycle**:
1. Created on-demand for each request
2. Starts MCP server subprocess
3. Executes tool via MCP protocol
4. Returns results and cleans up

#### MCP Servers
**Location**: `src/python/insight_digger_mcp/mcp_server/server.py`
**Purpose**: Tool execution and data processing

```python
# Tool definition example
@mcp.tool(description="List available data sources")
async def list_sources(apiUrl: str, jwtToken: str, search: str = "") -> dict:
    headers = {"X-API-URL": apiUrl, "X-JWT-TOKEN": jwtToken}
    result = await get("/sources", headers=headers, params={"search": search})
    return result
```

**Key Features**:
- FastMCP-based tool definitions
- Async HTTP client for external APIs
- Comprehensive error handling
- Structured logging

### 7. External Integration Layer

#### Sandsiv+ API
**Purpose**: Primary data analysis platform
**Integration**: HTTP REST API with JWT authentication
**Capabilities**:
- Data source discovery
- Schema analysis
- Dashboard creation
- Chart data retrieval

#### Configuration System
**Location**: `config/settings.py`
**Purpose**: Centralized configuration management

```python
class MCPConfig:
    class API:
        BASE_URL = os.getenv("INSIGHT_DIGGER_API_URL", "https://api.sandsiv.com")
        DEFAULT_TIMEOUT = int(os.getenv("MCP_API_DEFAULT_TIMEOUT", 60))
        
    class Redis:
        HOST = os.getenv("REDIS_HOST", "localhost")
        PORT = int(os.getenv("REDIS_PORT", 6379))
        
    class Session:
        IDLE_TTL = int(os.getenv("MCP_SESSION_IDLE_TTL", 24 * 3600))
```

## Data Flow Architecture

### Request Processing Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant B as MCP Bridge
    participant L as Load Balancer
    participant F as Flask Worker
    participant S as Session Manager
    participant R as Redis
    participant M as MCP Manager
    participant MS as MCP Server
    participant A as External API

    Note over C,A: Session Initialization
    C->>B: setup_authentication(apiUrl, jwtToken)
    B->>L: POST /init
    L->>F: Route request
    F->>A: Validate credentials
    A->>F: Validation response
    F->>S: Create session
    S->>R: Store session data
    R->>S: Confirm storage
    S->>F: Session created
    F->>L: Success response
    L->>B: Session initialized
    B->>C: Authentication complete

    Note over C,A: Tool Discovery
    C->>B: List available tools
    B->>L: POST /tools
    L->>F: Route request
    F->>S: Get session data
    S->>R: Retrieve session
    R->>S: Session data
    S->>F: Session validated
    F->>M: Create MCP manager
    M->>MS: Start subprocess
    MS->>M: Tool schemas
    M->>F: Available tools
    F->>L: Tool list
    L->>B: Tools response
    B->>C: Tools + guidance

    Note over C,A: Tool Execution
    C->>B: call_tool(name, params)
    B->>L: POST /call-tool
    L->>F: Route request
    F->>S: Get/update session
    S->>R: Retrieve/store data
    R->>S: Session data
    S->>F: Cached parameters
    F->>M: Execute tool
    M->>MS: Tool call
    MS->>A: API request
    A->>MS: API response
    MS->>M: Tool results
    M->>F: Results
    F->>S: Cache results
    S->>R: Update session
    R->>S: Confirm update
    S->>F: Caching complete
    F->>M: Cleanup manager
    M->>MS: Stop subprocess
    MS->>M: Cleanup complete
    M->>F: Manager stopped
    F->>L: Tool results
    L->>B: Response
    B->>C: Final results
```

### Caching Strategy

#### Parameter Injection Flow
```mermaid
flowchart TD
    A[Tool Call Request] --> B{Session Exists?}
    B -->|No| C[Return Error]
    B -->|Yes| D[Get Tool Schema]
    D --> E[Check Required Parameters]
    E --> F{Parameter Provided?}
    F -->|Yes| G[Use Provided Value]
    F -->|No| H{Cached Value Exists?}
    H -->|Yes| I[Inject Cached Value]
    H -->|No| J[Use Default/Required]
    G --> K[Execute Tool]
    I --> K
    J --> K
    K --> L[Cache Input Parameters]
    L --> M[Cache Output Results]
    M --> N[Return Response]
```

#### Session Data Structure
```json
{
  "session_metadata": {
    "session_id": "bridge-uuid-123",
    "created_at": "2024-01-01T12:00:00Z",
    "last_accessed": "2024-01-01T12:30:00Z",
    "ttl": 86400
  },
  "authentication": {
    "apiUrl": "https://api.sandsiv.com",
    "jwtToken": "encrypted_jwt_token"
  },
  "cached_parameters": {
    "sourceId": "data-source-123",
    "question": "What are the main factors affecting sales?",
    "columnAnalysis": [...],
    "strategy": {...},
    "markdownConfig": "...",
    "chartConfigs": [...]
  },
  "workflow_state": {
    "current_step": "analyze_charts",
    "completed_steps": ["list_sources", "analyze_structure", "generate_strategy"],
    "next_suggested_step": "create_dashboard"
  }
}
```

## Scalability Architecture

### Horizontal Scaling Pattern

```mermaid
graph TB
    subgraph "Load Balancer Tier"
        LB1[Primary LB]
        LB2[Secondary LB]
    end
    
    subgraph "Application Tier"
        subgraph "Node 1"
            F1[Flask Worker 1]
            F2[Flask Worker 2]
        end
        subgraph "Node 2"
            F3[Flask Worker 3]
            F4[Flask Worker 4]
        end
        subgraph "Node N"
            FN1[Flask Worker N1]
            FN2[Flask Worker N2]
        end
    end
    
    subgraph "Session Tier"
        subgraph "Redis Cluster"
            R1[(Redis Master 1)]
            R2[(Redis Master 2)]
            R3[(Redis Master 3)]
            RS1[(Redis Slave 1)]
            RS2[(Redis Slave 2)]
            RS3[(Redis Slave 3)]
        end
    end
    
    subgraph "Processing Tier"
        subgraph "MCP Pool 1"
            M1[MCP Server 1]
            M2[MCP Server 2]
        end
        subgraph "MCP Pool 2"
            M3[MCP Server 3]
            M4[MCP Server 4]
        end
    end
    
    LB1 --> F1
    LB1 --> F2
    LB1 --> F3
    LB1 --> F4
    LB2 --> FN1
    LB2 --> FN2
    
    F1 <-.-> R1
    F2 <-.-> R2
    F3 <-.-> R3
    F4 <-.-> R1
    FN1 <-.-> R2
    FN2 <-.-> R3
    
    R1 -.-> RS1
    R2 -.-> RS2
    R3 -.-> RS3
    
    F1 -.-> M1
    F2 -.-> M2
    F3 -.-> M3
    F4 -.-> M4
    FN1 -.-> M1
    FN2 -.-> M2
```

### Performance Characteristics

| Component | Scaling Method | Bottleneck | Mitigation |
|-----------|----------------|------------|------------|
| MCP Bridge | Process per client | Memory usage | Connection pooling |
| Flask API | Horizontal workers | CPU/Memory | Load balancing |
| Redis | Cluster/Sharding | Memory/Network | Redis Cluster |
| MCP Server | On-demand subprocess | Process creation | Process pooling |
| External API | Connection pooling | Rate limits | Circuit breakers |

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant B as Bridge
    participant F as Flask API
    participant A as Auth Provider
    participant R as Redis

    C->>B: Provide credentials
    B->>F: POST /init with JWT
    F->>A: Validate JWT token
    A->>F: Validation result
    alt Valid credentials
        F->>R: Store encrypted session
        R->>F: Session stored
        F->>B: Session ID + success
        B->>C: Authentication successful
    else Invalid credentials
        F->>B: Authentication failed
        B->>C: Error message
    end
```

### Security Layers

1. **Transport Security**
   - HTTPS/TLS for all HTTP communication
   - Secure WebSocket connections for real-time features
   - Certificate validation and pinning

2. **Authentication Security**
   - JWT token validation at API gateway
   - Session-based authentication for multi-step workflows
   - Credential encryption in Redis storage

3. **Authorization Security**
   - Session-based access control
   - Resource-level permissions
   - API rate limiting per session

4. **Data Security**
   - Sensitive parameter filtering in logs
   - Encrypted storage of credentials
   - Automatic session expiration

## Deployment Architecture

### Production Deployment

```mermaid
graph TB
    subgraph "DMZ"
        WAF[Web Application Firewall]
        LB[Load Balancer + SSL]
    end
    
    subgraph "Application Network"
        subgraph "Web Tier"
            APP1[App Server 1]
            APP2[App Server 2]
            APP3[App Server 3]
        end
        
        subgraph "Cache Tier"
            REDIS1[(Redis Primary)]
            REDIS2[(Redis Replica)]
        end
        
        subgraph "Monitoring"
            MON[Monitoring Stack]
            LOG[Log Aggregation]
        end
    end
    
    subgraph "External"
        API[Sandsiv+ API]
    end
    
    Internet --> WAF
    WAF --> LB
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 <-.-> REDIS1
    APP2 <-.-> REDIS1
    APP3 <-.-> REDIS1
    REDIS1 -.-> REDIS2
    
    APP1 -.-> MON
    APP2 -.-> MON
    APP3 -.-> MON
    
    APP1 -.-> LOG
    APP2 -.-> LOG
    APP3 -.-> LOG
    
    APP1 -.-> API
    APP2 -.-> API
    APP3 -.-> API
    
    classDef dmz fill:#ffebee,stroke:#d32f2f
    classDef app fill:#e8f5e8,stroke:#388e3c
    classDef cache fill:#fff3e0,stroke:#f57c00
    classDef monitor fill:#e3f2fd,stroke:#1976d2
    classDef external fill:#f3e5f5,stroke:#7b1fa2
    
    class WAF,LB dmz
    class APP1,APP2,APP3 app
    class REDIS1,REDIS2 cache
    class MON,LOG monitor
    class API external
```

### Container Architecture

```dockerfile
# Multi-stage build for production
FROM python:3.11-slim as base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM node:18-slim as bridge
WORKDIR /app
COPY src/nodejs/package*.json ./
RUN npm ci --only=production

FROM base as production
COPY src/python/ ./src/python/
COPY config/ ./config/
COPY --from=bridge /app/node_modules ./src/nodejs/node_modules
COPY --from=bridge /app/src ./src/nodejs/src

EXPOSE 33000
CMD ["python", "src/python/scripts/start_flask_api.py"]
```

## Monitoring and Observability

### Metrics Collection

```python
# Example metrics instrumentation
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

# Session metrics
active_sessions = Gauge('active_sessions_total', 'Number of active sessions')
session_duration = Histogram('session_duration_seconds', 'Session duration')

# Tool execution metrics
tool_calls = Counter('tool_calls_total', 'Total tool calls', ['tool_name', 'status'])
tool_duration = Histogram('tool_execution_duration_seconds', 'Tool execution time', ['tool_name'])
```

### Health Checks

```python
@app.route('/health')
def health():
    checks = {
        'redis': check_redis_connection(),
        'external_api': check_external_api(),
        'disk_space': check_disk_space(),
        'memory_usage': check_memory_usage()
    }
    
    if all(checks.values()):
        return jsonify({'status': 'healthy', 'checks': checks}), 200
    else:
        return jsonify({'status': 'unhealthy', 'checks': checks}), 503
```

This architecture provides a robust, scalable, and secure foundation for enterprise data analysis workflows while maintaining compatibility with standard MCP protocols. 