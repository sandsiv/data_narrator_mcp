# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-XX

### Added
- Complete project reorganization with clear separation of concerns
- Modern Python packaging with pyproject.toml
- Comprehensive configuration system with YAML files
- Professional directory structure following best practices
- Automated installation and setup scripts
- Systemd service files for production deployment
- Comprehensive test suite structure
- Development and production environment configurations
- CLI entry points for all components

### Changed
- **BREAKING**: Reorganized entire project structure
- **BREAKING**: Updated all import paths and module references
- **BREAKING**: Renamed package from `data-narrator-mcp` to `insight-digger-mcp`
- **BREAKING**: Moved Flask API from `mcp_client/server.py` to `src/python/insight_digger_mcp/flask_api/app.py`
- **BREAKING**: Moved MCP Server from `mcp_server.py` to `src/python/insight_digger_mcp/mcp_server/server.py`
- **BREAKING**: Moved Node.js bridge from `src/index.js` to `src/nodejs/src/index.js`
- Updated configuration management to use centralized YAML files
- Improved documentation with new project structure

### Fixed
- Resolved naming confusion between different server components
- Fixed import paths throughout the codebase
- Standardized configuration access patterns

### Removed
- Old scattered configuration files
- Duplicate and confusing file locations

## [0.9.0] - Previous Version

### Added
- Initial MCP bridge implementation
- Flask API for MCP client functionality
- Redis-based session management
- JWT authentication system
- Multi-step workflow optimization
- Claude Desktop integration

### Features
- Enterprise-grade 3-layer MCP architecture
- Dynamic JWT authentication with 14-day tokens
- Intelligent parameter caching and auto-injection
- Workflow guidance for LLM optimization
- Multi-user support with session isolation
- Enterprise security and compliance features 