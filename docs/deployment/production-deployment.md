# Production Deployment

This guide covers deploying Insight Digger MCP in a production environment with Gunicorn, Nginx, Redis, and systemd.

## Overview

The production deployment uses:
- **Gunicorn**: WSGI server for running the Flask API
- **Nginx**: Reverse proxy and load balancer
- **Redis**: Session storage and caching
- **systemd**: Service management and process supervision

## Architecture

```
Internet → Nginx → Gunicorn Workers → Flask API → Redis
                                   ↓
                              MCP Server Subprocesses
```

## Prerequisites

### System Requirements
- Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- Python 3.8+
- Redis 6.0+
- Nginx 1.18+
- 4GB+ RAM (recommended)
- 2+ CPU cores

### User Setup
```bash
# Create dedicated user
sudo useradd -r -s /bin/false insight-digger
sudo mkdir -p /opt/insight-digger-mcp
sudo chown insight-digger:insight-digger /opt/insight-digger-mcp
```

## Installation

### 1. Clone and Setup Application
```bash
cd /opt/insight-digger-mcp
sudo -u insight-digger git clone <repository-url> .
sudo -u insight-digger python3 -m venv venv
sudo -u insight-digger venv/bin/pip install -r requirements.txt
```

### 2. Create Directories
```bash
sudo -u insight-digger mkdir -p logs
sudo chmod 755 logs
```

### 3. Install Redis
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install redis-server

# CentOS/RHEL
sudo dnf install redis

# Start and enable Redis
sudo systemctl start redis
sudo systemctl enable redis
```

### 4. Install Nginx
```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS/RHEL
sudo dnf install nginx

sudo systemctl start nginx
sudo systemctl enable nginx
```

## Configuration

### 1. Environment Variables
Create `/opt/insight-digger-mcp/.env`:
```bash
# Server Configuration
MCP_CLIENT_PORT=33000
MCP_CLIENT_HOST=127.0.0.1

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Session Management
MCP_SESSION_IDLE_TTL=86400  # 24 hours
MCP_PROCESS_CLEANUP_INTERVAL=300  # 5 minutes

# API Configuration
INSIGHT_DIGGER_API_URL=https://your-backend-api.com/api

# Logging
MCP_LOG_LEVEL=INFO
MCP_LOG_FILE=/opt/insight-digger-mcp/logs/mcp.log

# Security
MCP_SENSITIVE_PARAMS=apiUrl,jwtToken
```

### 2. systemd Service
Copy the service file:
```bash
sudo cp scripts/deployment/systemd/insight-digger-flask-api.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 3. Nginx Configuration
```bash
# Copy configuration
sudo cp scripts/deployment/nginx/insight-digger-mcp.conf /etc/nginx/sites-available/

# Edit domain and paths
sudo nano /etc/nginx/sites-available/insight-digger-mcp.conf

# Enable site
sudo ln -s /etc/nginx/sites-available/insight-digger-mcp.conf /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## Service Management

### Start Services
```bash
# Start Redis (if not already running)
sudo systemctl start redis

# Start the Flask API
sudo systemctl start insight-digger-flask-api

# Enable auto-start on boot
sudo systemctl enable insight-digger-flask-api
```

### Check Status
```bash
# Service status
sudo systemctl status insight-digger-flask-api

# Logs
sudo journalctl -u insight-digger-flask-api -f

# Gunicorn logs
sudo tail -f /opt/insight-digger-mcp/logs/gunicorn-access.log
sudo tail -f /opt/insight-digger-mcp/logs/gunicorn-error.log
```

### Restart/Reload
```bash
# Graceful reload (zero downtime)
sudo systemctl reload insight-digger-flask-api

# Full restart
sudo systemctl restart insight-digger-flask-api
```

## Performance Tuning

### Gunicorn Workers
The default configuration uses 3 workers with 2 threads each. Adjust based on your hardware:

```bash
# Formula: (2 x CPU cores) + 1
workers = (2 x 4) + 1 = 9  # For 4 CPU cores
```

Edit the systemd service file to adjust:
```bash
sudo systemctl edit insight-digger-flask-api
```

### Redis Tuning
Edit `/etc/redis/redis.conf`:
```
# Memory settings
maxmemory 1gb
maxmemory-policy allkeys-lru

# Persistence (optional for sessions)
save ""  # Disable RDB snapshots for pure cache usage

# Network
tcp-keepalive 300
timeout 0
```

### System Limits
Edit `/etc/security/limits.conf`:
```
insight-digger soft nofile 65536
insight-digger hard nofile 65536
insight-digger soft nproc 4096
insight-digger hard nproc 4096
```

## Monitoring

### Health Checks
```bash
# Application health
curl http://localhost:33000/health

# Through Nginx
curl http://your-domain.com/insight-digger-mcp/health
```

### Process Monitoring
```bash
# Check Gunicorn processes
ps aux | grep gunicorn

# Check MCP server processes
ps aux | grep "mcp run"

# Redis status
redis-cli ping
```

### Log Monitoring
```bash
# Application logs
tail -f /opt/insight-digger-mcp/logs/mcp.log

# Gunicorn logs
tail -f /opt/insight-digger-mcp/logs/gunicorn-*.log

# Nginx logs
tail -f /var/log/nginx/insight-digger-mcp-*.log

# System logs
journalctl -u insight-digger-flask-api -f
```

## Security

### Firewall
```bash
# Allow only necessary ports
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 22/tcp   # SSH

# Block direct access to application port
sudo ufw deny 33000/tcp
```

### SSL/TLS (Recommended)
Use Let's Encrypt for free SSL certificates:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### File Permissions
```bash
# Secure application files
sudo chown -R insight-digger:insight-digger /opt/insight-digger-mcp
sudo chmod -R 755 /opt/insight-digger-mcp
sudo chmod -R 644 /opt/insight-digger-mcp/logs
```

## Scaling

### Horizontal Scaling
To scale across multiple servers:

1. **Shared Redis**: Use a dedicated Redis server
2. **Load Balancer**: Add multiple backend servers to Nginx upstream
3. **Session Affinity**: Not required due to Redis session storage

Example Nginx upstream for multiple servers:
```nginx
upstream insight_digger_mcp {
    server 10.0.1.10:33000 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:33000 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:33000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

### Vertical Scaling
- Increase Gunicorn workers based on CPU cores
- Allocate more memory to Redis
- Tune system limits and kernel parameters

## Backup and Recovery

### Redis Backup
```bash
# Manual backup
redis-cli BGSAVE

# Automated backup script
cat > /opt/backup-redis.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis_$DATE.rdb
find /backup -name "redis_*.rdb" -mtime +7 -delete
EOF

chmod +x /opt/backup-redis.sh
```

### Application Backup
```bash
# Backup configuration and logs
tar -czf insight-digger-backup-$(date +%Y%m%d).tar.gz \
    /opt/insight-digger-mcp/.env \
    /opt/insight-digger-mcp/logs/ \
    /etc/systemd/system/insight-digger-flask-api.service \
    /etc/nginx/sites-available/insight-digger-mcp.conf
```

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
sudo journalctl -u insight-digger-flask-api -n 50

# Check Redis connection
redis-cli ping

# Verify file permissions
ls -la /opt/insight-digger-mcp/
```

**High memory usage:**
```bash
# Check worker count
ps aux | grep gunicorn | wc -l

# Monitor Redis memory
redis-cli info memory

# Check for orphaned MCP processes
ps aux | grep "mcp run"
```

**Connection timeouts:**
```bash
# Check Nginx timeouts
sudo nginx -T | grep timeout

# Check Gunicorn timeout
ps aux | grep gunicorn | grep timeout

# Monitor active sessions
redis-cli keys "mcp_session:*" | wc -l
```

For more troubleshooting information, see [Troubleshooting Guide](troubleshooting.md).

## Updates and Maintenance

### Application Updates
```bash
# Stop service
sudo systemctl stop insight-digger-flask-api

# Update code
cd /opt/insight-digger-mcp
sudo -u insight-digger git pull

# Update dependencies
sudo -u insight-digger venv/bin/pip install -r requirements.txt

# Start service
sudo systemctl start insight-digger-flask-api
```

### System Maintenance
```bash
# Log rotation (automatic with systemd)
sudo journalctl --vacuum-time=30d

# Clean old Redis data (if needed)
redis-cli FLUSHDB

# Update system packages
sudo apt update && sudo apt upgrade
```

This production deployment provides a robust, scalable foundation for running Insight Digger MCP in enterprise environments. 