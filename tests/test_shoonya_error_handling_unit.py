"""
Unit tests for Shoonya API error handling and retry logic.

Tests cover:
- Exponential backoff retry
- Network error handling
- Authentication error handling
- Rate limiting
- Auto re-authentication

Requirements: 4.9, 4.10
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import requests
from src.api_integrations import ShoonyaClient


class TestShoonyaErrorHandling(unittest.TestCase):
    """Test suite for Shoonya error handling functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials_json = json.dumps({
            'userid': 'TEST123',
            'password': 'TestPass123',
            'totp_secret': 'JBSWY3DPEHPK3PXP',
            'vendor_code': 'TEST123_U',
            'api_secret': 'test_secret_key',
            'imei': 'test_imei_123'
        })
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_retry_on_network_error(self, mock_sleep, mock_post, mock_file):
        """Test retry logic on network errors."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # First two calls fail, third succeeds
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            requests.exceptions.ConnectionError("Network error"),
            MagicMock(json=lambda: {'stat': 'Ok', 'lp': '50000'}, raise_for_status=lambda: None)
        ]
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed after retries
        self.assertEqual(result['stat'], 'Ok')
        
        # Should have made 3 attempts
        self.assertEqual(mock_post.call_count, 3)
        
        # Should have slept twice (exponential backoff: 1s, 2s)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_fails_after_max_retries(self, mock_sleep, mock_post, mock_file):
        """Test that request fails after max retries."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # All calls fail
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        with self.assertRaises(Exception) as context:
            client.get_quotes('NSE', 'RELIANCE-EQ')
        
        self.assertIn('Network error after 3 attempts', str(context.exception))
        
        # Should have made 3 attempts
        self.assertEqual(mock_post.call_count, 3)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_no_retry_on_auth_error(self, mock_post, mock_file):
        """Test that authentication errors are not retried."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock 401 authentication error
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        with self.assertRaises(Exception) as context:
            client.get_quotes('NSE', 'RELIANCE-EQ')
        
        self.assertIn('Authentication error', str(context.exception))
        
        # Should only make 1 attempt (no retries)
        self.assertEqual(mock_post.call_count, 1)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_rate_limit_handling(self, mock_sleep, mock_post, mock_file):
        """Test rate limit handling with Retry-After header."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # First call hits rate limit, second succeeds
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '10'}
        mock_response_429.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_429)
        
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = {'stat': 'Ok', 'lp': '50000'}
        mock_response_ok.raise_for_status = lambda: None
        
        mock_post.side_effect = [mock_response_429, mock_response_ok]
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed after retry
        self.assertEqual(result['stat'], 'Ok')
        
        # Should have slept for Retry-After duration
        mock_sleep.assert_called_once_with(10)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_rate_limit_without_retry_after_header(self, mock_sleep, mock_post, mock_file):
        """Test rate limit handling without Retry-After header."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # First call hits rate limit, second succeeds
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}  # No Retry-After header
        mock_response_429.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_429)
        
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = {'stat': 'Ok', 'lp': '50000'}
        mock_response_ok.raise_for_status = lambda: None
        
        mock_post.side_effect = [mock_response_429, mock_response_ok]
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed after retry
        self.assertEqual(result['stat'], 'Ok')
        
        # Should have used default delay (5 seconds)
        mock_sleep.assert_called_once_with(5)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_retry_on_timeout(self, mock_sleep, mock_post, mock_file):
        """Test retry on timeout errors."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # First call times out, second succeeds
        mock_post.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            MagicMock(json=lambda: {'stat': 'Ok', 'lp': '50000'}, raise_for_status=lambda: None)
        ]
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed after retry
        self.assertEqual(result['stat'], 'Ok')
        
        # Should have made 2 attempts
        self.assertEqual(mock_post.call_count, 2)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_exponential_backoff_delays(self, mock_sleep, mock_post, mock_file):
        """Test exponential backoff delay progression."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # All calls fail to test all retry delays
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        try:
            client.get_quotes('NSE', 'RELIANCE-EQ')
        except:
            pass
        
        # Verify exponential backoff: 1s, 2s
        self.assertEqual(mock_sleep.call_count, 2)
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(calls, [1, 2])
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    @patch('time.sleep')
    def test_retry_on_500_error(self, mock_sleep, mock_post, mock_file):
        """Test retry on server errors (500+)."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # First call returns 500, second succeeds
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_500)
        
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = {'stat': 'Ok', 'lp': '50000'}
        mock_response_ok.raise_for_status = lambda: None
        
        mock_post.side_effect = [mock_response_500, mock_response_ok]
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed after retry
        self.assertEqual(result['stat'], 'Ok')
        
        # Should have made 2 attempts
        self.assertEqual(mock_post.call_count, 2)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_no_retry_on_403_forbidden(self, mock_post, mock_file):
        """Test that 403 errors are not retried."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock 403 forbidden error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        with self.assertRaises(Exception) as context:
            client.get_quotes('NSE', 'RELIANCE-EQ')
        
        self.assertIn('Authentication error', str(context.exception))
        
        # Should only make 1 attempt (no retries)
        self.assertEqual(mock_post.call_count, 1)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_successful_call_no_retry_overhead(self, mock_post, mock_file):
        """Test that successful calls don't have retry overhead."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok', 'lp': '50000'}
        mock_response.raise_for_status = lambda: None
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_quotes('NSE', 'RELIANCE-EQ')
        
        # Should succeed on first attempt
        self.assertEqual(result['stat'], 'Ok')
        self.assertEqual(mock_post.call_count, 1)


if __name__ == '__main__':
    unittest.main()
