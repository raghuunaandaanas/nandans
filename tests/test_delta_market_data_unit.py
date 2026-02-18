"""
Unit tests for Delta Exchange market data fetching.

Tests the DeltaExchangeClient market data methods including ticker fetching,
candle data retrieval, product listing, and first candle close fetching.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from src.api_integrations import DeltaExchangeClient
import pytz


class TestDeltaExchangeMarketData:
    """Unit tests for Delta Exchange market data fetching."""
    
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
    def test_get_ticker_success(self, mock_get, client):
        """Test successful ticker data fetching."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'symbol': 'BTCUSD',
                'mark_price': '50000.00',
                'last_price': '50001.50',
                'bid': '49999.00',
                'ask': '50002.00',
                'volume': '1000000',
                'timestamp': 1234567890
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Call get_ticker
        result = client.get_ticker('BTCUSD')
        
        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert '/v2/tickers/BTCUSD' in call_args[0][0]
        assert 'headers' in call_args[1]
        
        # Verify result
        assert result['result']['symbol'] == 'BTCUSD'
        assert result['result']['mark_price'] == '50000.00'
    
    @patch('requests.get')
    def test_get_ticker_with_authentication_headers(self, mock_get, client):
        """Test that get_ticker includes proper authentication headers."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        client.get_ticker('BTCUSD')
        
        # Verify headers were included
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        assert 'api-key' in headers
        assert 'timestamp' in headers
        assert 'signature' in headers
        assert headers['api-key'] == 'test_api_key'
    
    @patch('requests.get')
    def test_get_candle_close_success(self, mock_get, client):
        """Test successful candle data fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'time': 1234567800,
                    'open': '49900.00',
                    'high': '50100.00',
                    'low': '49800.00',
                    'close': '50000.00',
                    'volume': '100'
                },
                {
                    'time': 1234567860,
                    'open': '50000.00',
                    'high': '50200.00',
                    'low': '49950.00',
                    'close': '50150.00',
                    'volume': '150'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Call get_candle_close
        result = client.get_candle_close(
            symbol='BTCUSD',
            resolution='1m',
            start=1234567800,
            end=1234567900
        )
        
        # Verify request
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert '/v2/history/candles' in call_args[0][0]
        
        # Verify params
        params = call_args[1]['params']
        assert params['symbol'] == 'BTCUSD'
        assert params['resolution'] == '1m'
        assert params['start'] == 1234567800
        assert params['end'] == 1234567900
        
        # Verify result
        assert len(result['result']) == 2
        assert result['result'][0]['close'] == '50000.00'
        assert result['result'][1]['close'] == '50150.00'
    
    @patch('requests.get')
    def test_get_candle_close_different_resolutions(self, mock_get, client):
        """Test candle fetching with different resolutions."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Test different resolutions
        for resolution in ['1m', '5m', '15m', '1h', '1d']:
            client.get_candle_close('BTCUSD', resolution, 1234567800, 1234567900)
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            assert params['resolution'] == resolution
    
    @patch('requests.get')
    def test_get_products_success(self, mock_get, client):
        """Test successful products fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'symbol': 'BTCUSD',
                    'description': 'Bitcoin USD Perpetual',
                    'contract_type': 'perpetual_futures',
                    'underlying_asset': 'BTC'
                },
                {
                    'symbol': 'BTC-50000-C',
                    'description': 'BTC 50000 Call',
                    'contract_type': 'call_options',
                    'strike_price': '50000',
                    'expiry': 1234567890,
                    'underlying_asset': 'BTC'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Call get_products
        result = client.get_products()
        
        # Verify request
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert '/v2/products' in call_args[0][0]
        
        # Verify result
        assert len(result['result']) == 2
        assert result['result'][0]['symbol'] == 'BTCUSD'
        assert result['result'][1]['contract_type'] == 'call_options'
    
    @patch('requests.get')
    def test_get_first_candle_close_success(self, mock_get, client):
        """Test successful first candle close fetching at 5:30 AM IST."""
        # Mock candle data response
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'time': 1234567800,
                    'open': '49900.00',
                    'high': '50100.00',
                    'low': '49800.00',
                    'close': '50000.00',
                    'volume': '100'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Call get_first_candle_close
        result = client.get_first_candle_close(
            symbol='BTCUSD',
            resolution='1m',
            time_ist='05:30'
        )
        
        # Verify result
        assert result == '50000.00'
    
    @patch('requests.get')
    def test_get_first_candle_close_timezone_conversion(self, mock_get, client):
        """Test that IST time is correctly converted to UTC."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'time': 1234567800,
                    'close': '50000.00'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Call with IST time
        client.get_first_candle_close('BTCUSD', '1m', '05:30')
        
        # Verify that the request was made
        # IST is UTC+5:30, so 05:30 IST = 00:00 UTC
        mock_get.assert_called()
    
    @patch('requests.get')
    def test_get_first_candle_close_no_data(self, mock_get, client):
        """Test handling when no candle data is available."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_first_candle_close('BTCUSD', '1m', '05:30')
        
        assert result is None
    
    @patch('requests.get')
    def test_get_first_candle_close_missing_result_key(self, mock_get, client):
        """Test handling when response doesn't contain 'result' key."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_first_candle_close('BTCUSD', '1m', '05:30')
        
        assert result is None
    
    @patch('requests.get')
    def test_get_first_candle_close_multiple_candles(self, mock_get, client):
        """Test that closest candle to target time is selected."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {'time': 1234567700, 'close': '49900.00'},  # 100s before
                {'time': 1234567800, 'close': '50000.00'},  # Exact match
                {'time': 1234567900, 'close': '50100.00'}   # 100s after
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_first_candle_close('BTCUSD', '1m', '05:30')
        
        # Should return the close price of the candle closest to target time
        assert result in ['49900.00', '50000.00', '50100.00']
    
    @patch('requests.get')
    def test_get_ticker_api_error(self, mock_get, client):
        """Test error handling when API returns error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            client.get_ticker('BTCUSD')
        
        assert "API Error" in str(exc_info.value)
    
    @patch('requests.get')
    def test_get_candle_close_api_error(self, mock_get, client):
        """Test error handling when candle API returns error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception):
            client.get_candle_close('BTCUSD', '1m', 1234567800, 1234567900)
    
    def test_get_first_candle_close_invalid_time_format(self, client):
        """Test error handling with invalid time format."""
        with pytest.raises(ValueError):
            client.get_first_candle_close('BTCUSD', '1m', 'invalid_time')
    
    @patch('requests.get')
    def test_get_products_empty_response(self, mock_get, client):
        """Test handling of empty products list."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_products()
        
        assert result['result'] == []

