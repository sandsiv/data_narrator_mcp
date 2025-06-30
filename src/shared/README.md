# Shared Resources Directory

This directory contains resources shared between the Python and Node.js components of the Insight Digger MCP system.

## Contents

### schemas/
JSON schemas for:
- API request/response validation
- Configuration file validation
- Tool parameter validation
- MCP protocol message validation

### docs/
Language-agnostic documentation:
- OpenAPI specifications
- Protocol documentation
- Integration guides
- API reference materials

## Usage

These resources are used by both:
- **Python components**: Flask API and MCP Server
- **Node.js components**: MCP Bridge
- **External integrations**: Third-party clients and tools

## Adding New Resources

When adding new shared resources:
1. Place them in the appropriate subdirectory
2. Update relevant documentation
3. Ensure both Python and Node.js components can access them
4. Add validation schemas where appropriate

## Examples

```bash
# JSON schema for tool parameters
src/shared/schemas/tool_parameters.schema.json

# OpenAPI specification
src/shared/docs/api.openapi.yaml

# Protocol documentation
src/shared/docs/mcp_protocol.md
``` 