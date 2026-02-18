"""
Unit tests for Delta Exchange API error handling and retry logic.

Tests error handling with simulated failures including authentication errors,
rate limits, network errors, and successful retries.

Requirements: 3.1-3.12
"""

import pytest
import json
from unittest.mock import patch, Mock
from src.api_integrations import DeltaExchangeClient
import requests


class TestDeltaExchangeErrorHandling:
    """Unit tests for Delta Exchange error handling."""
    
    @pytest.fixture
    def client(self, tmp_path):
        """Create a DeltaExchangeClient instance for testing."""
        cred_file = tmp_path / "test_delta_cred.json"
        credentials = {
            "api_key": "test_api_key",
            "api_secret": "test_api_secret"
        }
        cred_file.write_text(json.dumps(credentials))
        return DeltaExchangeClient(credentials_path=str(cred_file))
    
    @patch('requests.get')
    def test_get_ticker_retry_on_network_error(self, mock_get, client):
        """Test that get_ticker retries on network errors."""
        # First call fails with network error, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'symbol': 'BTCUSD', 'mark_price': '50000.00'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.get_ticker('BTCUSD')
        
        # Should succeed after retry
        assert result['result']['symbol'] == 'BTCUSD'
        # Should have been called twice
        assert mock_get.call_count == 2
    
    @patch('requests.get')
    def test_get_ticker_fails_after_max_retries(self, mock_get, client):
        """Test that get_ticker fails after max retries."""
        # All calls fail
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            with pytest.raises(requests.exceptions.ConnectionError):
                client.get_ticker('BTCUSD')
        
        # Should have been called 3 times (max retries)
        assert mock_get.call_count == 3
    
    @patch('requests.get')
    def test_get_ticker_no_retry_on_auth_error(self, mock_get, client):
        """Test that get_ticker does not retry on authentication errors."""
        # Create 401 authentication error
        mock_response = Mock()
        mock_response.status_code = 401
        
        def raise_auth_error():
            error = requests.exceptions.HTTPError()
            error.response = mock_response
            raise error
        
        mock_response.raise_for_status = raise_auth_error
        mock_get.return_value = mock_response
        
        # Should not retry authentication errors
        with pytest.raises(requests.exceptions.HTTPError):
            client.get_ticker('BTCUSD')
        
        # Should only be called once (no retries)
        assert mock_get.call_count == 1
    
    @patch('requests.get')
    def test_get_ticker_handles_rate_limit(self, mock_get, client):
        """Test that get_ticker handles rate limit errors with Retry-After."""
        # First call returns 429 rate limit, second succeeds
        mock_response_rate_limit = Mock()
        mock_response_rate_limit.status_code = 429
        mock_response_rate_limit.headers = {'Retry-After': '2'}
        
        def raise_rate_limit():
            error = requests.exceptions.HTTPError()
            error.response = mock_response_rate_limit
            raise error
        
        mock_response_rate_limit.raise_for_status = raise_rate_limit
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'symbol': 'BTCUSD', 'mark_price': '50000.00'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_rate_limit, mock_response_success]
        
        # Mock time.sleep to verify delay
        with patch('time.sleep') as mock_sleep:
            result = client.get_ticker('BTCUSD')
            
            # Should succeed after retry
            assert result['result']['symbol'] == 'BTCUSD'
            # Should have slept for 2 seconds (Retry-After value)
            assert mock_sleep.call_count == 1
            assert mock_sleep.call_args[0][0] == 2.0
    
    @patch('requests.post')
    def test_place_order_retry_on_timeout(self, mock_post, client):
        """Test that place_order retries on timeout errors."""
        # First call times out, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'id': 'order_123', 'state': 'open'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_post.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.place_order('BTCUSD', 'buy', 1.0, 'market_order')
        
        # Should succeed after retry
        assert result['result']['id'] == 'order_123'
        # Should have been called twice
        assert mock_post.call_count == 2
    
    @patch('requests.post')
    def test_place_order_exponential_backoff(self, mock_post, client):
        """Test that place_order uses exponential backoff for retries."""
        # Fail twice, then succeed
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'id': 'order_123', 'state': 'open'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            requests.exceptions.ConnectionError("Network error"),
            mock_response_success
        ]
        
        # Mock time.sleep to verify exponential backoff
        with patch('time.sleep') as mock_sleep:
            result = client.place_order('BTCUSD', 'buy', 1.0, 'market_order')
            
            # Should succeed after 2 retries
            assert result['result']['id'] == 'order_123'
            
            # Should have slept twice with exponential backoff
            assert mock_sleep.call_count == 2
            # First retry: 1 second
            assert mock_sleep.call_args_list[0][0][0] == 1.0
            # Second retry: 2 seconds
            assert mock_sleep.call_args_list[1][0][0] == 2.0
    
    @patch('requests.get')
    def test_get_candle_close_retry_on_500_error(self, mock_get, client):
        """Test that get_candle_close retries on 500 server errors."""
        # First call returns 500 error, second succeeds
        mock_response_error = Mock()
        mock_response_error.status_code = 500
        
        def raise_server_error():
            error = requests.exceptions.HTTPError()
            error.response = mock_response_error
            raise error
        
        mock_response_error.raise_for_status = raise_server_error
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': [{'time': 1234567800, 'close': '50000.00'}]
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_error, mock_response_success]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.get_candle_close('BTCUSD', '1m', 1234567800, 1234567900)
        
        # Should succeed after retry
        assert result['result'][0]['close'] == '50000.00'
        # Should have been called twice
        assert mock_get.call_count == 2
    
    @patch('requests.get')
    def test_get_products_retry_on_connection_reset(self, mock_get, client):
        """Test that get_products retries on connection reset errors."""
        # First call fails with connection reset, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': [{'symbol': 'BTCUSD', 'contract_type': 'perpetual_futures'}]
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.get_products()
        
        # Should succeed after retry
        assert result['result'][0]['symbol'] == 'BTCUSD'
        # Should have been called twice
        assert mock_get.call_count == 2
    
    @patch('requests.get')
    def test_get_positions_retry_on_request_exception(self, mock_get, client):
        """Test that get_positions retries on generic request exceptions."""
        # First call fails with generic exception, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': [{'product_symbol': 'BTCUSD', 'size': 1.0}]
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [
            requests.exceptions.RequestException("Generic error"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.get_positions()
        
        # Should succeed after retry
        assert result['result'][0]['product_symbol'] == 'BTCUSD'
        # Should have been called twice
        assert mock_get.call_count == 2
    
    @patch('requests.delete')
    def test_cancel_order_retry_on_network_error(self, mock_delete, client):
        """Test that cancel_order retries on network errors."""
        # First call fails, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'id': 'order_123', 'state': 'cancelled'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_delete.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.cancel_order('order_123')
        
        # Should succeed after retry
        assert result['result']['state'] == 'cancelled'
        # Should have been called twice
        assert mock_delete.call_count == 2
    
    @patch('requests.put')
    def test_modify_order_retry_on_timeout(self, mock_put, client):
        """Test that modify_order retries on timeout errors."""
        # First call times out, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'id': 'order_123', 'limit_price': '51000.00'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_put.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            mock_response_success
        ]
        
        # Mock time.sleep to speed up test
        with patch('time.sleep'):
            result = client.modify_order('order_123', 51000.00)
        
        # Should succeed after retry
        assert result['result']['limit_price'] == '51000.00'
        # Should have been called twice
        assert mock_put.call_count == 2
    
    @patch('requests.get')
    def test_get_ticker_no_retry_on_403_forbidden(self, mock_get, client):
        """Test that get_ticker does not retry on 403 Forbidden errors."""
        # Create 403 forbidden error
        mock_response = Mock()
        mock_response.status_code = 403
        
        def raise_forbidden_error():
            error = requests.exceptions.HTTPError()
            error.response = mock_response
            raise error
        
        mock_response.raise_for_status = raise_forbidden_error
        mock_get.return_value = mock_response
        
        # Should not retry forbidden errors
        with pytest.raises(requests.exceptions.HTTPError):
            client.get_ticker('BTCUSD')
        
        # Should only be called once (no retries)
        assert mock_get.call_count == 1
    
    @patch('requests.post')
    def test_place_order_validates_before_retry(self, mock_post, client):
        """Test that place_order validates inputs before attempting retries."""
        # Should fail validation before making any API calls
        with pytest.raises(ValueError) as exc_info:
            client.place_order('BTCUSD', 'buy', 1.0, 'limit_order')
        
        assert "Price is required for limit orders" in str(exc_info.value)
        # Should not have made any API calls
        assert mock_post.call_count == 0
    
    @patch('requests.get')
    def test_rate_limit_without_retry_after_header(self, mock_get, client):
        """Test rate limit handling when Retry-After header is missing."""
        # First call returns 429 without Retry-After, second succeeds
        mock_response_rate_limit = Mock()
        mock_response_rate_limit.status_code = 429
        mock_response_rate_limit.headers = {}  # No Retry-After header
        
        def raise_rate_limit():
            error = requests.exceptions.HTTPError()
            error.response = mock_response_rate_limit
            raise error
        
        mock_response_rate_limit.raise_for_status = raise_rate_limit
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'result': {'symbol': 'BTCUSD', 'mark_price': '50000.00'}
        }
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_rate_limit, mock_response_success]
        
        # Mock time.sleep to verify exponential backoff is used
        with patch('time.sleep') as mock_sleep:
            result = client.get_ticker('BTCUSD')
            
            # Should succeed after retry
            assert result['result']['symbol'] == 'BTCUSD'
            # Should have slept with exponential backoff (1 second for first retry)
            assert mock_sleep.call_count == 1
            assert mock_sleep.call_args[0][0] == 1.0
    
    @patch('requests.get')
    def test_successful_call_no_retry_overhead(self, mock_get, client):
        """Test that successful calls don't incur retry overhead."""
        # Successful call on first attempt
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {'symbol': 'BTCUSD', 'mark_price': '50000.00'}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock time.sleep to verify it's not called
        with patch('time.sleep') as mock_sleep:
            result = client.get_ticker('BTCUSD')
            
            # Should succeed
            assert result['result']['symbol'] == 'BTCUSD'
            # Should only be called once
            assert mock_get.call_count == 1
            # Should not sleep (no retries)
            assert mock_sleep.call_count == 0
