#!/usr/bin/env python3
"""
Entry point for starting the Flask API server
"""

import sys
import os

# Add the project root directory to the Python path for config access
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, os.path.abspath(project_root))

# Also add the src/python directory for the main modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from insight_digger_mcp.flask_api import run_server

def main():
    """Entry point for the Flask API server"""
    run_server()

if __name__ == '__main__':
    main() 