#!/bin/bash
set -e

# Insight Digger MCP Production Deployment Script
# This script automates the deployment process for production environments

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_USER="insight-digger"
APP_DIR="/opt/insight-digger-mcp"
SERVICE_NAME="insight-digger-flask-api"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

check_os() {
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot determine OS version"
    fi
    
    . /etc/os-release
    case $ID in
        ubuntu|debian)
            PKG_MGR="apt"
            ;;
        centos|rhel|fedora)
            PKG_MGR="dnf"
            ;;
        *)
            error "Unsupported OS: $ID"
            ;;
    esac
    
    success "Detected OS: $PRETTY_NAME"
}

install_dependencies() {
    log "Installing system dependencies..."
    
    case $PKG_MGR in
        apt)
            apt update
            apt install -y python3 python3-venv python3-pip redis-server nginx git curl
            ;;
        dnf)
            dnf install -y python3 python3-pip redis nginx git curl
            ;;
    esac
    
    success "System dependencies installed"
}

create_user() {
    log "Creating application user..."
    
    if id "$APP_USER" &>/dev/null; then
        warning "User $APP_USER already exists"
    else
        useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
        success "Created user: $APP_USER"
    fi
}

setup_application() {
    log "Setting up application directory..."
    
    # Create directory
    mkdir -p "$APP_DIR"
    chown "$APP_USER:$APP_USER" "$APP_DIR"
    
    # Create logs directory
    sudo -u "$APP_USER" mkdir -p "$APP_DIR/logs"
    
    success "Application directory ready: $APP_DIR"
}

install_app() {
    log "Installing application..."
    
    # Check if we're in the source directory
    if [[ -f "requirements.txt" && -f "src/python/insight_digger_mcp/flask_api/app.py" ]]; then
        log "Installing from current directory..."
        cp -r . "$APP_DIR/"
        chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    else
        error "Please run this script from the insight_digger_mcp source directory"
    fi
    
    # Create virtual environment and install dependencies
    log "Creating virtual environment..."
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    
    success "Application installed"
}

configure_redis() {
    log "Configuring Redis..."
    
    systemctl start redis
    systemctl enable redis
    
    # Test Redis connection
    if redis-cli ping > /dev/null 2>&1; then
        success "Redis is running"
    else
        error "Redis is not responding"
    fi
}

configure_systemd() {
    log "Configuring systemd service..."
    
    # Copy service file
    cp "$APP_DIR/scripts/deployment/systemd/$SERVICE_NAME.service" "/etc/systemd/system/"
    
    # Reload systemd
    systemctl daemon-reload
    
    success "systemd service configured"
}

configure_nginx() {
    log "Configuring Nginx..."
    
    # Copy configuration
    cp "$APP_DIR/scripts/deployment/nginx/insight-digger-mcp.conf" "/etc/nginx/sites-available/"
    
    # Prompt for domain
    read -p "Enter your domain name (or press Enter for localhost): " DOMAIN
    if [[ -z "$DOMAIN" ]]; then
        DOMAIN="localhost"
    fi
    
    # Update domain in config
    sed -i "s/your-domain.com/$DOMAIN/g" "/etc/nginx/sites-available/insight-digger-mcp.conf"
    
    # Enable site
    ln -sf "/etc/nginx/sites-available/insight-digger-mcp.conf" "/etc/nginx/sites-enabled/"
    
    # Test configuration
    if nginx -t; then
        success "Nginx configuration is valid"
        systemctl reload nginx
    else
        error "Nginx configuration is invalid"
    fi
}

create_env_file() {
    log "Creating environment configuration..."
    
    cat > "$APP_DIR/.env" << EOF
# Server Configuration
MCP_CLIENT_PORT=33000
MCP_CLIENT_HOST=127.0.0.1

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Session Management
MCP_SESSION_IDLE_TTL=86400
MCP_PROCESS_CLEANUP_INTERVAL=300

# API Configuration
INSIGHT_DIGGER_API_URL=https://internal.sandsiv.com/data-narrator/api

# Logging
MCP_LOG_LEVEL=INFO
MCP_LOG_FILE=$APP_DIR/logs/mcp.log

# Security
MCP_SENSITIVE_PARAMS=apiUrl,jwtToken
EOF
    
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    
    success "Environment file created"
}

start_services() {
    log "Starting services..."
    
    # Start and enable the application service
    systemctl start "$SERVICE_NAME"
    systemctl enable "$SERVICE_NAME"
    
    # Check status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "Service $SERVICE_NAME is running"
    else
        error "Service $SERVICE_NAME failed to start"
    fi
    
    # Start Nginx
    systemctl start nginx
    systemctl enable nginx
    
    success "All services started"
}

test_deployment() {
    log "Testing deployment..."
    
    # Wait a moment for services to fully start
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:33000/health > /dev/null 2>&1; then
        success "Application health check passed"
    else
        warning "Application health check failed - check logs"
    fi
    
    # Test through Nginx
    if curl -f http://localhost/insight-digger-mcp/health > /dev/null 2>&1; then
        success "Nginx proxy test passed"
    else
        warning "Nginx proxy test failed - check configuration"
    fi
}

show_status() {
    log "Deployment Status:"
    echo
    echo "Services:"
    systemctl status "$SERVICE_NAME" --no-pager -l
    echo
    systemctl status nginx --no-pager -l
    echo
    systemctl status redis --no-pager -l
    echo
    
    echo "Logs:"
    echo "  Application: journalctl -u $SERVICE_NAME -f"
    echo "  Gunicorn: tail -f $APP_DIR/logs/gunicorn-*.log"
    echo "  Nginx: tail -f /var/log/nginx/insight-digger-mcp-*.log"
    echo
    
    echo "URLs:"
    echo "  Health Check: http://localhost:33000/health"
    echo "  Via Nginx: http://localhost/insight-digger-mcp/health"
    echo
}

# Main deployment process
main() {
    log "Starting Insight Digger MCP deployment..."
    
    check_root
    check_os
    install_dependencies
    create_user
    setup_application
    install_app
    configure_redis
    create_env_file
    configure_systemd
    configure_nginx
    start_services
    test_deployment
    show_status
    
    success "Deployment completed successfully!"
    echo
    warning "Next steps:"
    echo "1. Update $APP_DIR/.env with your specific configuration"
    echo "2. Configure SSL/TLS with: sudo certbot --nginx -d your-domain.com"
    echo "3. Set up monitoring and backups"
    echo "4. Review security settings"
}

# Handle command line arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    status)
        show_status
        ;;
    restart)
        log "Restarting services..."
        systemctl restart "$SERVICE_NAME"
        systemctl reload nginx
        success "Services restarted"
        ;;
    logs)
        journalctl -u "$SERVICE_NAME" -f
        ;;
    *)
        echo "Usage: $0 [deploy|status|restart|logs]"
        echo "  deploy  - Full deployment (default)"
        echo "  status  - Show service status"
        echo "  restart - Restart services"
        echo "  logs    - Follow application logs"
        exit 1
        ;;
esac 