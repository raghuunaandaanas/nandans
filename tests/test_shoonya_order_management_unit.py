"""
Unit tests for Shoonya API order management functionality.

Tests cover:
- Order placement (market and limit)
- Position fetching
- Order cancellation
- Error handling

Requirements: 4.7, 4.8
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
from src.api_integrations import ShoonyaClient


class TestShoonyaOrderManagement(unittest.TestCase):
    """Test suite for Shoonya order management functionality."""
    
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
    def test_place_market_order_success(self, mock_post, mock_file):
        """Test successful market order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'norenordno': 'ORDER123456'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'MKT')
        
        self.assertEqual(result['stat'], 'Ok')
        self.assertIn('norenordno', result)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_place_limit_order_success(self, mock_post, mock_file):
        """Test successful limit order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'norenordno': 'ORDER123456'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'LMT', 2500.50)
        
        self.assertEqual(result['stat'], 'Ok')
        
        # Verify price was included
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['prc'], '2500.5')
    
    @patch('builtins.open', new_callable=mock_open)
    def test_place_limit_order_without_price_raises_error(self, mock_file):
        """Test that limit order without price raises ValueError."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        with self.assertRaises(ValueError) as context:
            client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'LMT')
        
        self.assertIn('Price is required for limit orders', str(context.exception))
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_place_order_buy_side(self, mock_post, mock_file):
        """Test buy order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok', 'norenordno': 'ORDER123'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'MKT')
        
        # Verify trantype is 'B' for buy
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['trantype'], 'B')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_place_order_sell_side(self, mock_post, mock_file):
        """Test sell order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok', 'norenordno': 'ORDER123'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        client.place_order('NSE', 'RELIANCE-EQ', 'sell', 10, 'MKT')
        
        # Verify trantype is 'S' for sell
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['trantype'], 'S')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_place_order_intraday_product(self, mock_post, mock_file):
        """Test intraday order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok', 'norenordno': 'ORDER123'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'MKT', product_type='I')
        
        # Verify product type is 'I'
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['prd'], 'I')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_place_order_delivery_product(self, mock_post, mock_file):
        """Test delivery order placement."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok', 'norenordno': 'ORDER123'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'MKT', product_type='C')
        
        # Verify product type is 'C'
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['prd'], 'C')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_get_positions_success(self, mock_post, mock_file):
        """Test successful position fetching."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'exch': 'NSE', 'tsym': 'RELIANCE-EQ', 'netqty': '10', 'netavgprc': '2500.00'},
            {'exch': 'BSE', 'tsym': 'TCS-EQ', 'netqty': '5', 'netavgprc': '3500.00'}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_positions()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['tsym'], 'RELIANCE-EQ')
        self.assertEqual(result[1]['tsym'], 'TCS-EQ')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_get_positions_empty(self, mock_post, mock_file):
        """Test position fetching when no positions exist."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock empty API response
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_positions()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_get_positions_with_exchange_filter(self, mock_post, mock_file):
        """Test position fetching with exchange filter."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {'exch': 'NSE', 'tsym': 'RELIANCE-EQ', 'netqty': '10'},
            {'exch': 'BSE', 'tsym': 'TCS-EQ', 'netqty': '5'},
            {'exch': 'NSE', 'tsym': 'INFY-EQ', 'netqty': '8'}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.get_positions(exchange='NSE')
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(p['exch'] == 'NSE' for p in result))
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_cancel_order_success(self, mock_post, mock_file):
        """Test successful order cancellation."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'stat': 'Ok',
            'result': 'Order cancelled successfully'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        result = client.cancel_order('ORDER123456')
        
        self.assertEqual(result['stat'], 'Ok')
        
        # Verify order ID was passed correctly
        call_args = mock_post.call_args
        payload = call_args[1]['data']
        self.assertEqual(payload['norenordno'], 'ORDER123456')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('requests.post')
    def test_cancel_order_different_order_ids(self, mock_post, mock_file):
        """Test cancelling different order IDs."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {'stat': 'Ok'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        client = ShoonyaClient('test_cred.json')
        client.session_token = 'test_token'
        
        order_ids = ['ORDER001', 'ORDER002', 'ORDER003']
        
        for order_id in order_ids:
            client.cancel_order(order_id)
            
            # Verify correct order ID was used
            call_args = mock_post.call_args
            payload = call_args[1]['data']
            self.assertEqual(payload['norenordno'], order_id)
    
    @patch('builtins.open', new_callable=mock_open)
    def test_place_order_requires_authentication(self, mock_file):
        """Test that place_order requires authentication."""
        mock_file.return_value.read.return_value = self.credentials_json
        
        client = ShoonyaClient('test_cred.json')
        # Don't set session_token
        
        with self.assertRaises(Exception) as context:
            client.place_order('NSE', 'RELIANCE-EQ', 'buy', 10, 'MKT')
        
        self.assertIn('Not authenticated', str(context.exception))


if __name__ == '__main__':
    unittest.main()
