"""
Unit tests for Delta Exchange authentication.

Tests the DeltaExchangeClient authentication functionality including
credential loading, signature creation, and header generation.
"""

import pytest
import json
import hmac
import hashlib
import time
from pathlib import Path
from unittest.mock import patch, mock_open
from src.api_integrations import DeltaExchangeClient


class TestDeltaExchangeAuthentication:
    """Unit tests for Delta Exchange authentication."""
    
    def test_load_credentials_success(self, tmp_path):
        """Test successful credential loading from valid JSON file."""
        # Create temporary credentials file
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_api_key_123",
            "api_secret": "test_api_secret_456"
        }
        cred_file.write_text(json.dumps(credentials))
        
        # Initialize client with test credentials
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        # Verify credentials loaded correctly
        assert client.api_key == "test_api_key_123"
        assert client.api_secret == "test_api_secret_456"
    
    def test_load_credentials_file_not_found(self):
        """Test error handling when credentials file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            DeltaExchangeClient(credentials_path="nonexistent_file.json")
        
        assert "Credentials file not found" in str(exc_info.value)
    
    def test_load_credentials_missing_api_key(self, tmp_path):
        """Test error handling when api_key is missing from credentials."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {"api_secret": "test_secret"}
        cred_file.write_text(json.dumps(credentials))
        
        with pytest.raises(KeyError) as exc_info:
            DeltaExchangeClient(credentials_path=str(cred_file))
        
        assert "Missing 'api_key'" in str(exc_info.value)
    
    def test_load_credentials_missing_api_secret(self, tmp_path):
        """Test error handling when api_secret is missing from credentials."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {"api_key": "test_key"}
        cred_file.write_text(json.dumps(credentials))
        
        with pytest.raises(KeyError) as exc_info:
            DeltaExchangeClient(credentials_path=str(cred_file))
        
        assert "Missing 'api_secret'" in str(exc_info.value)
    
    def test_load_credentials_invalid_json(self, tmp_path):
        """Test error handling when credentials file contains invalid JSON."""
        cred_file = tmp_path / "test_delta_cred.json"
        cred_file.write_text("{ invalid json }")
        
        with pytest.raises(json.JSONDecodeError):
            DeltaExchangeClient(credentials_path=str(cred_file))
    
    def test_create_signature_known_values(self, tmp_path):
        """Test signature creation with known values to verify correctness."""
        # Create client with known credentials
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        # Test signature creation with known values
        method = "GET"
        endpoint = "/v2/tickers"
        timestamp = "1234567890"
        
        # Calculate expected signature manually
        message = method + timestamp + endpoint
        expected_signature = hmac.new(
            "test_secret".encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Generate signature using client
        signature = client.create_signature(method, endpoint, timestamp)
        
        # Verify signature matches expected value
        assert signature == expected_signature
    
    def test_create_signature_with_body(self, tmp_path):
        """Test signature creation with request body (POST/PUT requests)."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        method = "POST"
        endpoint = "/v2/orders"
        timestamp = "1234567890"
        body = '{"symbol":"BTCUSD","side":"buy"}'
        
        # Calculate expected signature with body
        message = method + timestamp + endpoint + body
        expected_signature = hmac.new(
            "test_secret".encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature = client.create_signature(method, endpoint, timestamp, body)
        
        assert signature == expected_signature
    
    def test_create_signature_different_methods(self, tmp_path):
        """Test that different HTTP methods produce different signatures."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        endpoint = "/v2/tickers"
        timestamp = "1234567890"
        
        sig_get = client.create_signature("GET", endpoint, timestamp)
        sig_post = client.create_signature("POST", endpoint, timestamp)
        sig_delete = client.create_signature("DELETE", endpoint, timestamp)
        
        # All signatures should be different
        assert sig_get != sig_post
        assert sig_get != sig_delete
        assert sig_post != sig_delete
    
    def test_get_headers_structure(self, tmp_path):
        """Test that get_headers returns correct header structure."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_api_key_123",
            "api_secret": "test_api_secret_456"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        headers = client.get_headers("/v2/tickers", "GET")
        
        # Verify all required headers are present
        assert 'api-key' in headers
        assert 'timestamp' in headers
        assert 'signature' in headers
        assert 'Content-Type' in headers
        
        # Verify header values
        assert headers['api-key'] == "test_api_key_123"
        assert headers['Content-Type'] == "application/json"
        
        # Verify timestamp is a valid Unix timestamp
        timestamp = int(headers['timestamp'])
        assert timestamp > 0
        assert timestamp <= int(time.time()) + 1  # Allow 1 second tolerance
    
    def test_get_headers_signature_validity(self, tmp_path):
        """Test that get_headers generates valid signature."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        endpoint = "/v2/tickers"
        method = "GET"
        headers = client.get_headers(endpoint, method)
        
        # Manually verify the signature
        message = method + headers['timestamp'] + endpoint
        expected_signature = hmac.new(
            "test_secret".encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        assert headers['signature'] == expected_signature
    
    def test_get_headers_with_body(self, tmp_path):
        """Test get_headers with request body for POST requests."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        endpoint = "/v2/orders"
        method = "POST"
        body = '{"symbol":"BTCUSD"}'
        
        headers = client.get_headers(endpoint, method, body)
        
        # Verify signature includes body
        message = method + headers['timestamp'] + endpoint + body
        expected_signature = hmac.new(
            "test_secret".encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        assert headers['signature'] == expected_signature
    
    def test_signature_determinism(self, tmp_path):
        """Test that same inputs always produce same signature."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        method = "GET"
        endpoint = "/v2/tickers"
        timestamp = "1234567890"
        
        # Generate signature multiple times with same inputs
        sig1 = client.create_signature(method, endpoint, timestamp)
        sig2 = client.create_signature(method, endpoint, timestamp)
        sig3 = client.create_signature(method, endpoint, timestamp)
        
        # All signatures should be identical
        assert sig1 == sig2 == sig3
    
    def test_signature_changes_with_timestamp(self, tmp_path):
        """Test that signature changes when timestamp changes."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        client = DeltaExchangeClient(credentials_path=str(cred_file))
        
        method = "GET"
        endpoint = "/v2/tickers"
        
        sig1 = client.create_signature(method, endpoint, "1234567890")
        sig2 = client.create_signature(method, endpoint, "1234567891")
        
        # Signatures should be different with different timestamps
        assert sig1 != sig2
