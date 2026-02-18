"""
Property-based tests for Delta Exchange API retry logic.

Tests universal properties for error handling and exponential backoff retry.
"""

import pytest
import json
import tempfile
import os
import time
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings, assume
from src.api_integrations import DeltaExchangeClient
import requests


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


class TestDeltaRetryProperties:
    """Property-based tests for Delta Exchange retry logic."""
    
    @given(
        attempt_count=st.integers(min_value=1, max_value=3),
        initial_delay=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=50)
    def test_property_exponential_backoff_delays(self, attempt_count, initial_delay):
        """
        **Validates: Requirements 3.11, 30.2**
        **Property 24: Order Retry with Exponential Backoff**
        
        For any number of retry attempts, the delay should follow exponential
        backoff pattern: delay = initial_delay * (2 ** attempt_number).
        
        Attempt 0: initial_delay * 1 = initial_delay
        Attempt 1: initial_delay * 2
        Attempt 2: initial_delay * 4
        """
        test_client, path = create_test_client()
        
        try:
            # Track delays between retries
            delays = []
            call_count = [0]
            
            def failing_func():
                call_count[0] += 1
                if call_count[0] <= attempt_count:
                    # Record time and raise error
                    raise requests.exceptions.RequestException("Network error")
                return {"success": True}
            
            # Mock time.sleep to capture delays
            with patch('time.sleep') as mock_sleep:
                try:
                    test_client._api_call_with_retry(
                        failing_func,
                        max_retries=attempt_count + 1,
                        initial_delay=initial_delay
                    )
                except:
                    pass
                
                # Verify exponential backoff pattern
                if mock_sleep.call_count > 0:
                    for i, call in enumerate(mock_sleep.call_args_list):
                        expected_delay = initial_delay * (2 ** i)
                        actual_delay = call[0][0]
                        
                        # Allow small floating point tolerance
                        assert abs(actual_delay - expected_delay) < 0.01, \
                            f"Attempt {i}: expected delay {expected_delay}, got {actual_delay}"
        finally:
            os.unlink(path)
    
    @given(max_retries=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_property_retry_count_respected(self, max_retries):
        """
        **Validates: Requirements 3.11, 30.2**
        **Property 24: Order Retry with Exponential Backoff**
        
        For any max_retries value, the function should be called exactly
        max_retries times before giving up (if all attempts fail).
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def always_failing_func():
                call_count[0] += 1
                raise requests.exceptions.RequestException("Always fails")
            
            # Mock time.sleep to speed up test
            with patch('time.sleep'):
                with pytest.raises(requests.exceptions.RequestException):
                    test_client._api_call_with_retry(
                        always_failing_func,
                        max_retries=max_retries
                    )
            
            # Should be called exactly max_retries times
            assert call_count[0] == max_retries
        finally:
            os.unlink(path)
    
    @given(success_on_attempt=st.integers(min_value=1, max_value=3))
    @settings(max_examples=50)
    def test_property_succeeds_on_retry(self, success_on_attempt):
        """
        **Validates: Requirements 3.11, 30.2**
        **Property 24: Order Retry with Exponential Backoff**
        
        For any retry attempt number, if the function succeeds on that attempt,
        it should return the result without further retries.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            expected_result = {"success": True, "data": "test"}
            
            def succeeds_on_nth_attempt():
                call_count[0] += 1
                if call_count[0] < success_on_attempt:
                    raise requests.exceptions.RequestException("Temporary failure")
                return expected_result
            
            # Mock time.sleep to speed up test
            with patch('time.sleep'):
                result = test_client._api_call_with_retry(
                    succeeds_on_nth_attempt,
                    max_retries=5
                )
            
            # Should succeed and return result
            assert result == expected_result
            # Should be called exactly success_on_attempt times
            assert call_count[0] == success_on_attempt
        finally:
            os.unlink(path)
    
    def test_property_authentication_errors_not_retried(self):
        """
        **Validates: Requirements 3.11, 3.12**
        
        For authentication errors (401, 403), the system should NOT retry
        as these indicate credential problems that won't be fixed by retrying.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def auth_error_func():
                call_count[0] += 1
                response = Mock()
                response.status_code = 401
                error = requests.exceptions.HTTPError()
                error.response = response
                raise error
            
            # Should not retry authentication errors
            with pytest.raises(requests.exceptions.HTTPError):
                test_client._api_call_with_retry(auth_error_func, max_retries=3)
            
            # Should only be called once (no retries)
            assert call_count[0] == 1
        finally:
            os.unlink(path)
    
    @given(retry_after=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50)
    def test_property_rate_limit_respects_retry_after(self, retry_after):
        """
        **Validates: Requirements 3.12**
        
        For rate limit errors (429) with Retry-After header, the system
        should wait for the specified time before retrying.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def rate_limit_func():
                call_count[0] += 1
                if call_count[0] == 1:
                    response = Mock()
                    response.status_code = 429
                    response.headers = {'Retry-After': str(retry_after)}
                    error = requests.exceptions.HTTPError()
                    error.response = response
                    raise error
                return {"success": True}
            
            # Mock time.sleep to capture delay
            with patch('time.sleep') as mock_sleep:
                result = test_client._api_call_with_retry(rate_limit_func, max_retries=3)
                
                # Should succeed after retry
                assert result == {"success": True}
                
                # Should have slept for retry_after seconds
                assert mock_sleep.call_count == 1
                actual_delay = mock_sleep.call_args[0][0]
                assert actual_delay == float(retry_after)
        finally:
            os.unlink(path)
    
    @given(
        error_types=st.lists(
            st.sampled_from([
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException
            ]),
            min_size=1,
            max_size=3
        )
    )
    @settings(max_examples=50)
    def test_property_network_errors_retried(self, error_types):
        """
        **Validates: Requirements 3.11, 30.2**
        **Property 24: Order Retry with Exponential Backoff**
        
        For any network-related error (ConnectionError, Timeout, RequestException),
        the system should retry with exponential backoff.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def network_error_func():
                call_count[0] += 1
                if call_count[0] <= len(error_types):
                    # Raise different error types
                    error_class = error_types[call_count[0] - 1]
                    raise error_class("Network error")
                return {"success": True}
            
            # Mock time.sleep to speed up test
            with patch('time.sleep'):
                result = test_client._api_call_with_retry(
                    network_error_func,
                    max_retries=len(error_types) + 1
                )
            
            # Should eventually succeed
            assert result == {"success": True}
            # Should have retried for each error
            assert call_count[0] == len(error_types) + 1
        finally:
            os.unlink(path)
    
    def test_property_successful_first_attempt_no_retry(self):
        """
        **Validates: Requirements 3.11, 30.2**
        
        For any function that succeeds on the first attempt, no retries
        should be performed.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def immediate_success():
                call_count[0] += 1
                return {"success": True}
            
            # Mock time.sleep to verify it's not called
            with patch('time.sleep') as mock_sleep:
                result = test_client._api_call_with_retry(immediate_success, max_retries=3)
                
                # Should succeed
                assert result == {"success": True}
                # Should only be called once
                assert call_count[0] == 1
                # Should not sleep (no retries)
                assert mock_sleep.call_count == 0
        finally:
            os.unlink(path)
    
    @given(
        http_status=st.integers(min_value=400, max_value=599).filter(
            lambda x: x not in [401, 403, 429]
        )
    )
    @settings(max_examples=50)
    def test_property_http_errors_retried(self, http_status):
        """
        **Validates: Requirements 3.11, 30.2**
        
        For HTTP errors (except 401, 403, 429), the system should retry
        with exponential backoff.
        """
        test_client, path = create_test_client()
        
        try:
            call_count = [0]
            
            def http_error_func():
                call_count[0] += 1
                if call_count[0] == 1:
                    response = Mock()
                    response.status_code = http_status
                    error = requests.exceptions.HTTPError()
                    error.response = response
                    raise error
                return {"success": True}
            
            # Mock time.sleep to speed up test
            with patch('time.sleep'):
                result = test_client._api_call_with_retry(http_error_func, max_retries=3)
                
                # Should succeed after retry
                assert result == {"success": True}
                # Should have been called twice (initial + 1 retry)
                assert call_count[0] == 2
        finally:
            os.unlink(path)
