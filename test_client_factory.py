# Test client factory - ensures only one TestClient is created across all tests
import os
# Skip Ninja's internal registry to avoid "multiple NinjaAPI registration" error 
# which occurs when api.urls is accessed multiple times (e.g. by Django and TestClient)
os.environ["NINJA_SKIP_REGISTRY"] = "1"

from ninja.testing import TestClient

# Global test client - created once on first access
_test_client = None

def get_test_client():
    """
    Get or create a shared TestClient for all tests.

    This ensures that only one TestClient is created across all test modules,
    avoiding Ninja's "multiple NinjaAPI registration" error.
    """
    global _test_client
    if _test_client is None:
        from finance_backend.api import api
        _test_client = TestClient(api)
    return _test_client
