"""
Smoke test verifying that the Forms test setup, fixtures, and assertion helpers work properly.
"""

def test_harness_client_initialization(client):
    assert client is not None
    assert hasattr(client, "call_tool")
    assert hasattr(client, "offline")

def test_validator_and_seat_refusal(client, assert_seat_refusal):
    # Tests that unauthorized tools outside Seat 25 boundary trigger 403 refusal
    response = client.call_tool("SalarySlip.list", {"party_id": "test_123"})
    err = assert_seat_refusal(response)
    assert err["code"] == 403

def test_sample_data_builder(sample_data, validator):
    payload = sample_data.dynamic_form_payload("IN")
    is_valid, err = validator.validate_input("Form.create", payload)
    assert is_valid is True, f"Validation failed: {err}"
