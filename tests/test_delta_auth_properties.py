"""
Property-based tests for Delta Exchange authentication.

Tests universal properties that should hold for all valid inputs
to the authentication system.
"""

import pytest
import json
import hmac
import hashlib
import tempfile
import os
from hypothesis import given, strategies as st, assume, settings
from pathlib import Path
from src.api_integrations import DeltaExchangeClient


# Strategy for generating valid HTTP methods
http_methods = st.sampled_from(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])

# Strategy for generating API endpoints
endpoints = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='/_-'),
    min_size=1,
    max_size=100
).map(lambda s: '/' + s if not s.startswith('/') else s)

# Strategy for generating timestamps (Unix time in seconds)
timestamps = st.integers(min_value=1000000000, max_value=2000000000).map(str)

# Strategy for generating request bodies
bodies = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='{}":,[]'),
    max_size=500
)


def create_test_client():
    """Create a test client with temporary credentials."""
    fd, path = tempfile.mkstemp(suffix='.json')
    try:
        credentials = {
            "api_key": "test_api_key_12345",
            "api_secret": "test_api_secret_67890"
        }
        os.write(fd, json.dumps(credentials).encode())
        os.close(fd)
        client = DeltaExchangeClient(credentials_path=path)
        return client, path
    except:
        os.close(fd)
        if os.path.exists(path):
            os.unlink(path)
        raise


class TestDeltaAuthenticationProperties:
    """Property-based tests for Delta Exchange authentication."""
    
    @given(method=http_methods, endpoint=endpoints, timestamp=timestamps)
    @settings(max_examples=100)
    def test_property_signature_determinism(self, method, endpoint, timestamp):
        """
        **Validates: Requirements 3.1, 3.2**
        **Property 26: Authentication Signature Correctness**
        
        For any method, endpoint, and timestamp, creating the signature
        multiple times should always produce the same result.
        """
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method, endpoint, timestamp)
            sig2 = test_client.create_signature(method, endpoint, timestamp)
            sig3 = test_client.create_signature(method, endpoint, timestamp)
            
            assert sig1 == sig2 == sig3
            assert isinstance(sig1, str)
            assert len(sig1) == 64  # SHA256 hex digest is 64 characters
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints, timestamp=timestamps, body=bodies)
    @settings(max_examples=100)
    def test_property_signature_with_body_determinism(self, method, endpoint, timestamp, body):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any method, endpoint, timestamp, and body, creating the signature
        multiple times should always produce the same result.
        """
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method, endpoint, timestamp, body)
            sig2 = test_client.create_signature(method, endpoint, timestamp, body)
            
            assert sig1 == sig2
            assert isinstance(sig1, str)
            assert len(sig1) == 64
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints, timestamp=timestamps)
    @settings(max_examples=100)
    def test_property_signature_matches_hmac(self, method, endpoint, timestamp):
        """
        **Validates: Requirements 3.1, 3.2**
        **Property 26: Authentication Signature Correctness**
        
        For any inputs, the signature should match the HMAC-SHA256 calculation
        using method + timestamp + endpoint.
        """
        test_client, path = create_test_client()
        try:
            signature = test_client.create_signature(method, endpoint, timestamp)
            
            # Manually calculate expected signature
            message = method + timestamp + endpoint
            expected = hmac.new(
                test_client.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            assert signature == expected
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints, timestamp=timestamps, body=bodies)
    @settings(max_examples=100)
    def test_property_signature_with_body_matches_hmac(self, method, endpoint, timestamp, body):
        """
        **Validates: Requirements 3.1, 3.2**
        **Property 26: Authentication Signature Correctness**
        
        For any inputs including body, the signature should match HMAC-SHA256
        calculation using method + timestamp + endpoint + body.
        """
        test_client, path = create_test_client()
        try:
            signature = test_client.create_signature(method, endpoint, timestamp, body)
            
            # Manually calculate expected signature
            message = method + timestamp + endpoint + body
            expected = hmac.new(
                test_client.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            assert signature == expected
        finally:
            os.unlink(path)
    
    @given(
        method1=http_methods,
        method2=http_methods,
        endpoint=endpoints,
        timestamp=timestamps
    )
    @settings(max_examples=100)
    def test_property_different_methods_different_signatures(
        self, method1, method2, endpoint, timestamp
    ):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any two different HTTP methods with same endpoint and timestamp,
        the signatures should be different.
        """
        assume(method1 != method2)  # Only test when methods are different
        
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method1, endpoint, timestamp)
            sig2 = test_client.create_signature(method2, endpoint, timestamp)
            
            assert sig1 != sig2
        finally:
            os.unlink(path)
    
    @given(
        method=http_methods,
        endpoint1=endpoints,
        endpoint2=endpoints,
        timestamp=timestamps
    )
    @settings(max_examples=100)
    def test_property_different_endpoints_different_signatures(
        self, method, endpoint1, endpoint2, timestamp
    ):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any two different endpoints with same method and timestamp,
        the signatures should be different.
        """
        assume(endpoint1 != endpoint2)  # Only test when endpoints are different
        
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method, endpoint1, timestamp)
            sig2 = test_client.create_signature(method, endpoint2, timestamp)
            
            assert sig1 != sig2
        finally:
            os.unlink(path)
    
    @given(
        method=http_methods,
        endpoint=endpoints,
        timestamp1=timestamps,
        timestamp2=timestamps
    )
    @settings(max_examples=100)
    def test_property_different_timestamps_different_signatures(
        self, method, endpoint, timestamp1, timestamp2
    ):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any two different timestamps with same method and endpoint,
        the signatures should be different.
        """
        assume(timestamp1 != timestamp2)  # Only test when timestamps are different
        
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method, endpoint, timestamp1)
            sig2 = test_client.create_signature(method, endpoint, timestamp2)
            
            assert sig1 != sig2
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints)
    @settings(max_examples=100)
    def test_property_headers_contain_required_fields(self, method, endpoint):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any method and endpoint, get_headers should always return
        all required authentication headers.
        """
        test_client, path = create_test_client()
        try:
            headers = test_client.get_headers(endpoint, method)
            
            # All required headers must be present
            assert 'api-key' in headers
            assert 'timestamp' in headers
            assert 'signature' in headers
            assert 'Content-Type' in headers
            
            # Verify header types and values
            assert isinstance(headers['api-key'], str)
            assert isinstance(headers['timestamp'], str)
            assert isinstance(headers['signature'], str)
            assert headers['Content-Type'] == 'application/json'
            
            # Verify api-key matches client's key
            assert headers['api-key'] == test_client.api_key
            
            # Verify timestamp is numeric
            assert headers['timestamp'].isdigit()
            
            # Verify signature is valid hex string of correct length
            assert len(headers['signature']) == 64
            assert all(c in '0123456789abcdef' for c in headers['signature'])
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints, body=bodies)
    @settings(max_examples=100)
    def test_property_headers_signature_validity(self, method, endpoint, body):
        """
        **Validates: Requirements 3.1, 3.2**
        **Property 26: Authentication Signature Correctness**
        
        For any method, endpoint, and body, the signature in headers
        should be valid and verifiable.
        """
        test_client, path = create_test_client()
        try:
            headers = test_client.get_headers(endpoint, method, body)
            
            # Manually verify the signature
            message = method + headers['timestamp'] + endpoint + body
            expected_signature = hmac.new(
                test_client.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            assert headers['signature'] == expected_signature
        finally:
            os.unlink(path)
    
    @given(method=http_methods, endpoint=endpoints, timestamp=timestamps)
    @settings(max_examples=100)
    def test_property_signature_is_hexadecimal(self, method, endpoint, timestamp):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any inputs, the signature should always be a valid hexadecimal string.
        """
        test_client, path = create_test_client()
        try:
            signature = test_client.create_signature(method, endpoint, timestamp)
            
            # Verify it's a valid hex string
            assert isinstance(signature, str)
            assert len(signature) == 64
            
            # Should be convertible to bytes from hex
            try:
                bytes.fromhex(signature)
            except ValueError:
                pytest.fail("Signature is not a valid hexadecimal string")
        finally:
            os.unlink(path)
    
    @given(
        method=http_methods,
        endpoint=endpoints,
        body1=bodies,
        body2=bodies,
        timestamp=timestamps
    )
    @settings(max_examples=100)
    def test_property_different_bodies_different_signatures(
        self, method, endpoint, body1, body2, timestamp
    ):
        """
        **Validates: Requirements 3.1, 3.2**
        
        For any two different request bodies with same method, endpoint, and timestamp,
        the signatures should be different.
        """
        assume(body1 != body2)  # Only test when bodies are different
        
        test_client, path = create_test_client()
        try:
            sig1 = test_client.create_signature(method, endpoint, timestamp, body1)
            sig2 = test_client.create_signature(method, endpoint, timestamp, body2)
            
            assert sig1 != sig2
        finally:
            os.unlink(path)
