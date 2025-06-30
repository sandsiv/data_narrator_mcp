"""
Pytest configuration for Insight Digger MCP tests
"""

import pytest
import sys
import os

# Add src/python to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "session_id": "test-session-123",
        "apiUrl": "https://test.example.com",
        "jwtToken": "test.jwt.token"
    }

@pytest.fixture
def mock_redis():
    """Mock Redis instance for testing"""
    try:
        import fakeredis
        return fakeredis.FakeRedis()
    except ImportError:
        pytest.skip("fakeredis not available for testing") 