# Multi-stage build for data-narrator-mcp service
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app

# Switch to non-root user
USER mcp

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Redis Configuration
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    REDIS_DB=0 \
    REDIS_CONNECT_TIMEOUT=5 \
    REDIS_SOCKET_TIMEOUT=5 \
    # Session Management
    MCP_SESSION_IDLE_TTL=86400 \
    MCP_SESSION_KEY_PREFIX=mcp_session \
    MCP_PROCESS_CLEANUP_INTERVAL=300 \
    # Server Configuration
    MCP_CLIENT_PORT=33000 \
    MCP_CLIENT_HOST=0.0.0.0 \
    MCP_REQUEST_TIMEOUT=300 \
    # API Configuration
    INSIGHT_DIGGER_API_URL=https://internal.sandsiv.com/data-narrator/api \
    MCP_API_DEFAULT_TIMEOUT=60 \
    MCP_API_LONG_TIMEOUT=300 \
    MCP_API_VALIDATION_TIMEOUT=5 \
    # Security
    MCP_SENSITIVE_PARAMS=apiUrl,jwtToken \
    # Logging
    MCP_LOG_LEVEL=INFO \
    MCP_LOG_FILE=/tmp/mcp_server.log \
    # MCP Server Configuration
    MCP_SERVER_SCRIPT=src/python/insight_digger_mcp/mcp_server/server.py \
    MCP_TOOL_CALL_TIMEOUT=310 \
    MCP_SESSION_START_TIMEOUT=30 \
    MCP_TOOL_LIST_TIMEOUT=30

# Expose port
EXPOSE 33000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${MCP_CLIENT_PORT}/health || exit 1

# Run the Flask API server
CMD ["python3", "src/python/scripts/start_flask_api.py"]

