from ninja.testing import TestClient

from finance_backend.api import api

# Shared singleton test client for the global application API.
# Reusing a single TestClient avoids Ninja namespace collisions across test modules.
api_test_client = TestClient(api)

