#!/bin/bash
# Installation script for Insight Digger MCP dependencies

set -e

echo "Installing Insight Digger MCP dependencies..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "This script should not be run as root" 
   exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "Error: Python 3.8 or higher is required. Found: $python_version"
    exit 1
fi

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi

node_version=$(node --version | cut -d. -f1 | sed 's/v//')
if [ "$node_version" -lt 18 ]; then
    echo "Error: Node.js 18 or higher is required. Found: $(node --version)"
    exit 1
fi

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install development dependencies if requested
if [[ "$1" == "--dev" ]]; then
    echo "Installing development dependencies..."
    pip install -e ".[dev]"
fi

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install

# Install Node.js dependencies in the nodejs subdirectory
echo "Installing Node.js bridge dependencies..."
cd src/nodejs
npm install
cd ../..

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p logs
mkdir -p config

# Set up configuration if it doesn't exist
if [ ! -f config/.env ]; then
    echo "Creating configuration from template..."
    cp config/.env.example config/.env
    echo "Please edit config/.env with your settings"
fi

echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/.env with your settings"
echo "2. Start Redis server"
echo "3. Run 'source venv/bin/activate' to activate the virtual environment"
echo "4. Run 'npm run dev:flask' to start the Flask API"
echo "5. Run 'npm run dev:bridge' to start the MCP bridge" 