"""
Unit tests for Delta Exchange order management.

Tests the DeltaExchangeClient order management methods including order placement,
position fetching, order cancellation, and order modification.

Requirements: 3.9, 3.10
"""

import pytest
import json
from unittest.mock import patch, Mock
from src.api_integrations import DeltaExchangeClient


class TestDeltaExchangeOrderManagement:
    """Unit tests for Delta Exchange order management."""
    
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
    
    @patch('requests.post')
    def test_place_market_order_success(self, mock_post, client):
        """Test successful market order placement."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'id': 'order_123',
                'symbol': 'BTCUSD',
                'side': 'buy',
                'size': 1.0,
                'order_type': 'market_order',
                'state': 'open',
                'created_at': 1234567890
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Place market order
        result = client.place_order(
            symbol='BTCUSD',
            side='buy',
            quantity=1.0,
            order_type='market_order'
        )
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert '/v2/orders' in call_args[0][0]
        
        # Verify headers
        headers = call_args[1]['headers']
        assert 'api-key' in headers
        assert 'timestamp' in headers
        assert 'signature' in headers
        
        # Verify body
        body = json.loads(call_args[1]['data'])
        assert body['product_symbol'] == 'BTCUSD'
        assert body['side'] == 'buy'
        assert body['size'] == 1.0
        assert body['order_type'] == 'market_order'
        
        # Verify result
        assert result['result']['id'] == 'order_123'
        assert result['result']['order_type'] == 'market_order'
    
    @patch('requests.post')
    def test_place_limit_order_success(self, mock_post, client):
        """Test successful limit order placement."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'id': 'order_456',
                'symbol': 'BTCUSD',
                'side': 'sell',
                'size': 0.5,
                'order_type': 'limit_order',
                'limit_price': '51000.00',
                'state': 'open',
                'created_at': 1234567890
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Place limit order
        result = client.place_order(
            symbol='BTCUSD',
            side='sell',
            quantity=0.5,
            order_type='limit_order',
            price=51000.00
        )
        
        # Verify body includes limit price
        call_args = mock_post.call_args
        body = json.loads(call_args[1]['data'])
        assert body['limit_price'] == '51000.0'
        
        # Verify result
        assert result['result']['limit_price'] == '51000.00'
    
    def test_place_limit_order_without_price_raises_error(self, client):
        """Test that limit order without price raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            client.place_order(
                symbol='BTCUSD',
                side='buy',
                quantity=1.0,
                order_type='limit_order'
            )
        
        assert "Price is required for limit orders" in str(exc_info.value)
    
    @patch('requests.post')
    def test_place_order_buy_side(self, mock_post, client):
        """Test placing buy order."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {'side': 'buy'}}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client.place_order('BTCUSD', 'buy', 1.0, 'market_order')
        
        call_args = mock_post.call_args
        body = json.loads(call_args[1]['data'])
        assert body['side'] == 'buy'
    
    @patch('requests.post')
    def test_place_order_sell_side(self, mock_post, client):
        """Test placing sell order."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {'side': 'sell'}}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client.place_order('BTCUSD', 'sell', 1.0, 'market_order')
        
        call_args = mock_post.call_args
        body = json.loads(call_args[1]['data'])
        assert body['side'] == 'sell'
    
    @patch('requests.post')
    def test_place_order_with_authentication(self, mock_post, client):
        """Test that place_order includes proper authentication."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {}}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client.place_order('BTCUSD', 'buy', 1.0, 'market_order')
        
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        assert headers['api-key'] == 'test_api_key'
        assert 'signature' in headers
        assert 'timestamp' in headers
    
    @patch('requests.get')
    def test_get_positions_success(self, mock_get, client):
        """Test successful position fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'product_symbol': 'BTCUSD',
                    'size': 2.5,
                    'entry_price': '50000.00',
                    'margin': '1000.00',
                    'liquidation_price': '45000.00',
                    'unrealized_pnl': '500.00',
                    'realized_pnl': '100.00'
                },
                {
                    'product_symbol': 'ETHUSD',
                    'size': -1.0,
                    'entry_price': '3000.00',
                    'margin': '300.00',
                    'liquidation_price': '3500.00',
                    'unrealized_pnl': '-50.00',
                    'realized_pnl': '25.00'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Get positions
        result = client.get_positions()
        
        # Verify request
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert '/v2/positions' in call_args[0][0]
        
        # Verify headers
        headers = call_args[1]['headers']
        assert 'api-key' in headers
        
        # Verify result
        assert len(result['result']) == 2
        assert result['result'][0]['product_symbol'] == 'BTCUSD'
        assert result['result'][0]['size'] == 2.5
        assert result['result'][1]['product_symbol'] == 'ETHUSD'
        assert result['result'][1]['size'] == -1.0
    
    @patch('requests.get')
    def test_get_positions_empty(self, mock_get, client):
        """Test get_positions when no positions exist."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_positions()
        
        assert result['result'] == []
    
    @patch('requests.get')
    def test_get_positions_long_position(self, mock_get, client):
        """Test get_positions with long position (positive size)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'product_symbol': 'BTCUSD',
                    'size': 1.5,
                    'entry_price': '50000.00'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_positions()
        
        assert result['result'][0]['size'] > 0  # Long position
    
    @patch('requests.get')
    def test_get_positions_short_position(self, mock_get, client):
        """Test get_positions with short position (negative size)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': [
                {
                    'product_symbol': 'BTCUSD',
                    'size': -2.0,
                    'entry_price': '50000.00'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client.get_positions()
        
        assert result['result'][0]['size'] < 0  # Short position
    
    @patch('requests.delete')
    def test_cancel_order_success(self, mock_delete, client):
        """Test successful order cancellation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'id': 'order_123',
                'state': 'cancelled',
                'cancelled_at': 1234567890
            }
        }
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response
        
        # Cancel order
        result = client.cancel_order('order_123')
        
        # Verify request
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        assert '/v2/orders/order_123' in call_args[0][0]
        
        # Verify headers
        headers = call_args[1]['headers']
        assert 'api-key' in headers
        assert 'signature' in headers
        
        # Verify result
        assert result['result']['id'] == 'order_123'
        assert result['result']['state'] == 'cancelled'
    
    @patch('requests.delete')
    def test_cancel_order_with_different_order_ids(self, mock_delete, client):
        """Test cancelling orders with different order IDs."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {'state': 'cancelled'}}
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response
        
        order_ids = ['order_1', 'order_2', 'order_3']
        
        for order_id in order_ids:
            client.cancel_order(order_id)
            
            call_args = mock_delete.call_args
            assert f'/v2/orders/{order_id}' in call_args[0][0]
    
    @patch('requests.delete')
    def test_cancel_order_api_error(self, mock_delete, client):
        """Test error handling when cancel order fails."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Order not found")
        mock_delete.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            client.cancel_order('invalid_order')
        
        assert "Order not found" in str(exc_info.value)
    
    @patch('requests.put')
    def test_modify_order_success(self, mock_put, client):
        """Test successful order modification."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'id': 'order_456',
                'limit_price': '52000.00',
                'state': 'open',
                'updated_at': 1234567890
            }
        }
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response
        
        # Modify order
        result = client.modify_order('order_456', 52000.00)
        
        # Verify request
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        assert '/v2/orders/order_456' in call_args[0][0]
        
        # Verify headers
        headers = call_args[1]['headers']
        assert 'api-key' in headers
        assert 'signature' in headers
        
        # Verify body
        body = json.loads(call_args[1]['data'])
        assert body['limit_price'] == '52000.0'
        
        # Verify result
        assert result['result']['limit_price'] == '52000.00'
    
    @patch('requests.put')
    def test_modify_order_different_prices(self, mock_put, client):
        """Test modifying order with different prices."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {}}
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response
        
        prices = [50000.00, 51000.00, 49500.50]
        
        for price in prices:
            client.modify_order('order_123', price)
            
            call_args = mock_put.call_args
            body = json.loads(call_args[1]['data'])
            assert body['limit_price'] == str(price)
    
    @patch('requests.put')
    def test_modify_order_with_authentication(self, mock_put, client):
        """Test that modify_order includes proper authentication."""
        mock_response = Mock()
        mock_response.json.return_value = {'result': {}}
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response
        
        client.modify_order('order_123', 51000.00)
        
        call_args = mock_put.call_args
        headers = call_args[1]['headers']
        assert headers['api-key'] == 'test_api_key'
        assert 'signature' in headers
        assert 'timestamp' in headers
    
    @patch('requests.put')
    def test_modify_order_api_error(self, mock_put, client):
        """Test error handling when modify order fails."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Cannot modify filled order")
        mock_put.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            client.modify_order('order_123', 51000.00)
        
        assert "Cannot modify filled order" in str(exc_info.value)
    
    @patch('requests.post')
    def test_place_order_api_error(self, mock_post, client):
        """Test error handling when place order fails."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Insufficient funds")
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            client.place_order('BTCUSD', 'buy', 100.0, 'market_order')
        
        assert "Insufficient funds" in str(exc_info.value)
    
    @patch('requests.get')
    def test_get_positions_api_error(self, mock_get, client):
        """Test error handling when get positions fails."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            client.get_positions()
        
        assert "API Error" in str(exc_info.value)
