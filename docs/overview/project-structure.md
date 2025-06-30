# Insight Digger MCP - Project Structure

## Overview

This document provides a comprehensive overview of the Insight Digger MCP project structure after the complete reorganization and cleanup.

## Directory Structure

```
insight_digger_mcp/
├── 📁 config/                          # Configuration files
│   ├── default.yaml                    # Default configuration
│   ├── development.yaml                # Development overrides
│   ├── production.yaml                 # Production overrides
│   ├── .env.example                    # Environment variables template
│   └── schemas/                        # Configuration schemas
├── 📁 docs/                            # Project documentation
│   ├── integration_guide.md
│   ├── mcp_bridge_guide.md
│   ├── mcp_bridge_implementation_guide.md
│   ├── mcp_client_development_plan.md
│   ├── mcp_server_development_plan.md
│   └── redis_architecture.md
├── 📁 logs/                            # Log files directory
│   └── README.md                       # Log management guide
├── 📁 scripts/                         # Deployment and utility scripts
│   ├── deployment/
│   │   └── systemd/                    # Systemd service files
│   ├── setup/
│   │   └── install_dependencies.sh     # Installation script
│   └── maintenance/                    # Maintenance scripts
├── 📁 src/                             # Source code
│   ├── nodejs/                         # Node.js MCP Bridge
│   │   ├── bin/insight-digger-mcp      # CLI executable
│   │   ├── package.json                # Node.js package config
│   │   └── src/index.js                # Main bridge implementation
│   ├── python/                         # Python components
│   │   └── insight_digger_mcp/         # Main Python package
│   │       ├── config/                 # Configuration module
│   │       │   ├── __init__.py
│   │       │   └── settings.py         # Configuration settings
│   │       ├── flask_api/              # Flask HTTP API
│   │       │   ├── __init__.py
│   │       │   ├── app.py              # Main Flask application
│   │       │   ├── mcp_manager.py      # MCP server manager
│   │       │   ├── session_manager.py  # Redis session management
│   │       │   └── routes/             # API routes (future)
│   │       ├── mcp_server/             # Direct MCP server
│   │       │   ├── __init__.py
│   │       │   └── server.py           # MCP protocol server
│   │       └── utils/                  # Shared utilities
│   └── shared/                         # Language-agnostic resources
│       ├── README.md                   # Usage guide
│       ├── schemas/                    # JSON schemas
│       └── docs/                       # API documentation
├── 📁 tests/                           # Test suite
│   ├── conftest.py                     # Pytest configuration
│   ├── unit/                           # Unit tests
│   ├── integration/                    # Integration tests
│   ├── fixtures/                       # Test data
│   └── nodejs/                         # Node.js tests
├── 📄 .gitignore                       # Git ignore rules
├── 📄 CHANGELOG.md                     # Version history
├── 📄 LICENSE                          # MIT license
├── 📄 package.json                     # Root NPM configuration
├── 📄 pyproject.toml                   # Python packaging
├── 📄 README.md                        # Main documentation
├── 📄 requirements.txt                 # Python dependencies
├── 📄 REORGANIZATION_SUMMARY.md        # Reorganization details
└── 📄 SECURITY.md                      # Security guidelines
```

## Component Responsibilities

### 🐍 Python Components (`src/python/`)

#### Flask API (`flask_api/`)
- **Purpose**: HTTP REST API for external clients
- **Entry Point**: `python src/python/scripts/start_flask_api.py`
- **Key Features**: Session management, tool proxying, authentication

#### MCP Server (`mcp_server/`)
- **Purpose**: Direct MCP protocol implementation
- **Entry Point**: `python src/python/scripts/start_mcp_server.py`
- **Key Features**: FastMCP-based tool exposure, async HTTP calls

#### Configuration (`config/`)
- **Purpose**: Centralized configuration management
- **Key Features**: Environment-specific settings, Redis configuration

### 🟨 Node.js Components (`src/nodejs/`)

#### MCP Bridge (`src/`)
- **Purpose**: Standard MCP client for Claude Desktop
- **Entry Point**: `npx @sandsiv/insight-digger-mcp`
- **Key Features**: Authentication flow, tool proxying, session management

### 📊 Configuration System (`config/`)

#### Environment Files
- **default.yaml**: Base configuration for all environments
- **development.yaml**: Development-specific overrides
- **production.yaml**: Production-specific overrides
- **.env.example**: Environment variables template

### 🧪 Testing (`tests/`)

#### Test Organization
- **Unit tests**: Individual component testing
- **Integration tests**: End-to-end workflow testing
- **Fixtures**: Shared test data and mocks
- **Node.js tests**: Bridge-specific testing

### 🚀 Deployment (`scripts/`)

#### Setup Scripts
- **install_dependencies.sh**: Automated dependency installation
- **Environment setup**: Virtual environment and configuration

#### Deployment Scripts
- **Systemd services**: Linux service definitions
- **Docker preparation**: Container-ready structure

## Development Workflow

### 1. Initial Setup
```bash
./scripts/setup/install_dependencies.sh --dev
source venv/bin/activate
```

### 2. Development Commands
```bash
# Start Flask API
npm run dev:flask

# Start MCP Bridge
npm run dev:bridge

# Run tests
npm test
```

### 3. Production Deployment
```bash
# Install production dependencies
./scripts/setup/install_dependencies.sh

# Configure environment
cp config/.env.example config/.env
# Edit config/.env with production settings

# Deploy services
sudo cp scripts/deployment/systemd/*.service /etc/systemd/system/
sudo systemctl enable insight-digger-flask-api
sudo systemctl start insight-digger-flask-api
```

## Key Features

### 🔐 Enterprise Security
- JWT-based authentication
- Session isolation
- Credential validation
- Secure configuration management

### 🧠 Intelligent Caching
- Parameter auto-injection
- Session state preservation
- Workflow optimization
- Redis-based storage

### 📈 Scalability
- Multi-worker compatible
- Stateless architecture
- Horizontal scaling ready
- Load balancer friendly

### 🛠 Developer Experience
- Modern Python packaging
- Comprehensive testing
- Automated setup
- Clear documentation

## Quality Assurance

### ✅ Code Quality
- Professional directory structure
- Consistent naming conventions
- Comprehensive documentation
- Modern packaging standards

### ✅ Security
- Sensitive parameter filtering
- Secure service configuration
- Environment-based secrets
- Production hardening

### ✅ Maintainability
- Clear separation of concerns
- Modular architecture
- Comprehensive logging
- Error handling

### ✅ Deployment Ready
- Systemd service files
- Docker preparation
- Environment configuration
- Health monitoring

## Usage Examples

### Claude Desktop Integration
```json
{
  "mcpServers": {
    "insight-digger": {
      "command": "npx",
      "args": ["-y", "@sandsiv/insight-digger-mcp@1.0.0"],
      "env": {
        "MCP_CLIENT_URL": "https://your-service.com"
      }
    }
  }
}
```

### API Integration
```bash
# Initialize session
curl -X POST https://your-service.com/init \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "apiUrl": "...", "jwtToken": "..."}'

# Call tools
curl -X POST https://your-service.com/call-tool \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "tool": "list_sources", "params": {}}'
```

This structure provides a solid foundation for enterprise-grade data analysis with MCP protocol support, Claude Desktop integration, and professional deployment capabilities. 