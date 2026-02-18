"""
Unit tests for Shoonya API authentication.

Tests cover:
- Credential loading
- TOTP generation
- Login flow
- Session token management
- Error handling

Requirements: 4.1, 4.2
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import hashlib
from src.api_integrations import ShoonyaClient


class TestShoonyaAuthentication(unittest.TestCase):
    """Test suite for Shoonya authentication functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.valid_credentials = {
            'userid': 'TEST123',
            'password': 'TestPass123',
            'totp_secret': 'JBSWY3DPEHPK3PXP',
            'vendor_code': 'TEST123_U',
            'api_secret': 'test_secret_key',
            'imei': 'test_imei_123'
        }
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    def test_load_credentials_success(self, mock_file):
        """Test successful credential loading from JSON file."""
        client = ShoonyaClient('test_cred.json')
        
        self.assertEqual(client.userid, 'TEST123')
        self.assertEqual(client.password, 'TestPass123')
        self.assertEqual(client.totp_secret, 'JBSWY3DPEHPK3PXP')
        self.assertEqual(client.vendor_code, 'TEST123_U')
        self.assertEqual(client.api_secret, 'test_secret_key')
        self.assertEqual(client.imei, 'test_imei_123')
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_credentials_file_not_found(self, mock_file):
        """Test error handling when credentials file doesn't exist."""
        with self.assertRaises(FileNotFoundError) as context:
            ShoonyaClient('nonexistent.json')
        
        self.assertIn('Credentials file not found', str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123"}')
    def test_load_credentials_missing_fields(self, mock_file):
        """Test error handling when required fields are missing."""
        with self.assertRaises(ValueError) as context:
            ShoonyaClient('incomplete_cred.json')
        
        self.assertIn('Missing required fields', str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_credentials_invalid_json(self, mock_file):
        """Test error handling for invalid JSON format."""
        with self.assertRaises(ValueError) as context:
            ShoonyaClient('invalid.json')
        
        self.assertIn('Invalid JSON', str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    @patch('pyotp.TOTP')
    def test_generate_totp(self, mock_totp_class, mock_file):
        """Test TOTP token generation."""
        # Mock TOTP instance
        mock_totp_instance = MagicMock()
        mock_totp_instance.now.return_value = '123456'
        mock_totp_class.return_value = mock_totp_instance
        
        client = ShoonyaClient('test_cred.json')
        totp_token = client._generate_totp()
        
        # Verify TOTP was created with correct secret
        mock_totp_class.assert_called_once_with('JBSWY3DPEHPK3PXP')
        
        # Verify token is 6 digits
        self.assertEqual(totp_token, '123456')
        self.assertEqual(len(totp_token), 6)
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    @patch('pyotp.TOTP')
    @patch('requests.post')
    def test_login_success(self, mock_post, mock_totp_class, mock_file):
        """Test successful login flow."""
        # Mock TOTP
        mock_totp_instance = MagicMock()
        mock_totp_instance.now.return_value = '123456'
        mock_totp_class.return_value = mock_totp_instance
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'susertoken': 'test_session_token_abc123'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        result = client.login()
        
        # Verify session token was stored
        self.assertEqual(client.session_token, 'test_session_token_abc123')
        self.assertEqual(result['stat'], 'Ok')
        self.assertEqual(result['susertoken'], 'test_session_token_abc123')
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    @patch('pyotp.TOTP')
    @patch('requests.post')
    def test_login_failure(self, mock_post, mock_totp_class, mock_file):
        """Test login failure handling."""
        # Mock TOTP
        mock_totp_instance = MagicMock()
        mock_totp_instance.now.return_value = '123456'
        mock_totp_class.return_value = mock_totp_instance
        
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Not_Ok',
            'emsg': 'Invalid credentials'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        
        with self.assertRaises(Exception) as context:
            client.login()
        
        self.assertIn('Shoonya login failed', str(context.exception))
        self.assertIn('Invalid credentials', str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    @patch('pyotp.TOTP')
    @patch('requests.post')
    def test_login_password_hashing(self, mock_post, mock_totp_class, mock_file):
        """Test that password is properly hashed with SHA256."""
        # Mock TOTP
        mock_totp_instance = MagicMock()
        mock_totp_instance.now.return_value = '123456'
        mock_totp_class.return_value = mock_totp_instance
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'susertoken': 'test_token'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.login()
        
        # Verify password was hashed
        expected_hash = hashlib.sha256('TestPass123'.encode()).hexdigest()
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        
        self.assertEqual(payload['pwd'], expected_hash)
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"userid": "TEST123", "password": "TestPass123", "totp_secret": "JBSWY3DPEHPK3PXP", "vendor_code": "TEST123_U", "api_secret": "test_secret_key", "imei": "test_imei_123"}')
    @patch('pyotp.TOTP')
    @patch('requests.post')
    def test_login_appkey_generation(self, mock_post, mock_totp_class, mock_file):
        """Test that appkey is properly generated."""
        # Mock TOTP
        mock_totp_instance = MagicMock()
        mock_totp_instance.now.return_value = '123456'
        mock_totp_class.return_value = mock_totp_instance
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'susertoken': 'test_token'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.login()
        
        # Verify appkey was generated correctly
        expected_appkey = hashlib.sha256(('TEST123' + 'test_secret_key').encode()).hexdigest()
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        
        self.assertEqual(payload['appkey'], expected_appkey)


if __name__ == '__main__':
    unittest.main()
