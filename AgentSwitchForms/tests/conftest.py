"""
Pytest configuration and shared fixtures for AgentSwitch Forms tests.
"""

import sys
from pathlib import Path
import pytest

# Ensure AgentSwitchForms directory is in python sys.path
FORMS_DIR = Path(__file__).parent.parent
if str(FORMS_DIR) not in sys.path:
    sys.path.insert(0, str(FORMS_DIR))

from testing.client import FormsTestClient
from testing.validator import SchemaValidator
from testing.fixtures import SampleDataBuilder

@pytest.fixture(scope="session")
def validator() -> SchemaValidator:
    """Fixture providing the platform schema validator."""
    return SchemaValidator()

@pytest.fixture(scope="session")
def client() -> FormsTestClient:
    """Fixture providing the Forms test client (auto-detects live vs offline)."""
    return FormsTestClient()

@pytest.fixture(scope="session")
def sample_data() -> SampleDataBuilder:
    """Fixture providing sample data builders."""
    return SampleDataBuilder()

@pytest.fixture
def assert_mcp_success():
    """Assertion helper verifying successful tool response."""
    def _assert(response: dict):
        assert not response.get("is_error"), f"Expected success but got error: {response.get('error')}"
        assert "result" in response, "Expected 'result' key in MCP response"
        return response["result"]
    return _assert

@pytest.fixture
def assert_seat_refusal():
    """Assertion helper verifying 403 refusal on forbidden entities."""
    def _assert(response: dict):
        assert response.get("is_error") is True, "Expected refusal/error but operation succeeded"
        err = response.get("error", {})
        code = err.get("code")
        assert code in [403, "FORBIDDEN"], f"Expected 403 Forbidden refusal, got: {err}"
        return err
    return _assert
