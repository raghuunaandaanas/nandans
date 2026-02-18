"""
Unit tests for Order Manager

Tests cover:
- Market order placement
- Limit order placement and adjustment
- Order cancellation
- Order throttling
- Order statistics
"""

import pytest
from src.main import OrderManager
from unittest.mock import Mock


class TestMarketOrders:
    """Test market order placement."""
    
    def test_place_market_order_buy(self):
        """Test placing a buy market order."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        order = manager.place_market_order('BTC-USD', 'buy', 0.1)
        
        assert order['instrument'] == 'BTC-USD'
        assert order['side'] == 'buy'
        assert order['quantity'] == 0.1
        assert order['order_type'] == 'market'
        assert order['status'] == 'filled'
        assert 'timestamp' in order
        
    def test_place_market_order_sell(self):
        """Test placing a sell market order."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        order = manager.place_market_order('BTC-USD', 'sell', 0.5)
        
        assert order['side'] == 'sell'
        assert order['quantity'] == 0.5
        
    def test_market_order_recorded_in_history(self):
        """Test that market orders are recorded in history."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        manager.place_market_order('BTC-USD', 'buy', 0.1)
        manager.place_market_order('ETH-USD', 'sell', 1.0)
        
        history = manager.get_order_history()
        assert len(history) == 2
        assert history[0]['instrument'] == 'BTC-USD'
        assert history[1]['instrument'] == 'ETH-USD'
        
    def test_invalid_instrument_raises_error(self):
        """Test that empty instrument raises ValueError."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        with pytest.raises(ValueError, match="instrument cannot be empty"):
            manager.place_market_order('', 'buy', 0.1)
            
    def test_invalid_side_raises_error(self):
        """Test that invalid side raises ValueError."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        with pytest.raises(ValueError, match="side must be 'buy' or 'sell'"):
            manager.place_market_order('BTC-USD', 'long', 0.1)
            
    def test_invalid_quantity_raises_error(self):
        """Test that invalid quantity raises ValueError."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        with pytest.raises(ValueError, match="quantity must be positive"):
            manager.place_market_order('BTC-USD', 'buy', 0)


class TestLimitOrders:
    """Test limit order placement and adjustment."""
    
    def test_place_limit_order_buy(self):
        """Test placing a buy limit order."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=3)
        
        order = manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=False)
        
        assert order['instrument'] == 'BTC-USD'
        assert order['side'] == 'buy'
        assert order['quantity'] == 0.1
        assert order['price'] == 50000
        assert order['order_type'] == 'limit'
        assert order['adjustments'] == 0
        
    def test_limit_order_auto_adjustment(self):
        """Test that limit orders are auto-adjusted if not filled."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=3, tick_size=0.5)
        
        order = manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=True)
        
        # Should be adjusted 3 times and converted to market
        assert order['adjustments'] == 3
        assert order['order_type'] == 'market'
        assert order['status'] == 'filled'
        # Price should be increased by 3 ticks for buy order
        assert order['price'] == 50000 + (3 * 0.5)
        
    def test_limit_order_sell_adjustment_decreases_price(self):
        """Test that sell limit orders decrease price when adjusted."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=2, tick_size=1.0)
        
        order = manager.place_limit_order('BTC-USD', 'sell', 0.1, 50000, auto_adjust=True)
        
        # Price should be decreased by 2 ticks for sell order
        assert order['price'] == 50000 - (2 * 1.0)
        
    def test_limit_order_without_auto_adjust(self):
        """Test limit order without auto-adjustment."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        order = manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=False)
        
        assert order['status'] == 'pending'
        assert order['adjustments'] == 0
        
    def test_invalid_price_raises_error(self):
        """Test that invalid price raises ValueError."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        with pytest.raises(ValueError, match="price must be positive"):
            manager.place_limit_order('BTC-USD', 'buy', 0.1, 0)


class TestOrderCancellation:
    """Test order cancellation."""
    
    def test_cancel_order(self):
        """Test cancelling an order."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        result = manager.cancel_order('order_123')
        
        assert result['order_id'] == 'order_123'
        assert result['status'] == 'cancelled'
        assert 'timestamp' in result
        
    def test_cancel_invalid_order_id_raises_error(self):
        """Test that empty order_id raises ValueError."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        with pytest.raises(ValueError, match="order_id cannot be empty"):
            manager.cancel_order('')


class TestOrderHistory:
    """Test order history tracking."""
    
    def test_get_order_history_all(self):
        """Test getting all order history."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        manager.place_market_order('BTC-USD', 'buy', 0.1)
        manager.place_market_order('ETH-USD', 'sell', 1.0)
        manager.place_limit_order('BTC-USD', 'buy', 0.2, 50000, auto_adjust=False)
        
        history = manager.get_order_history()
        assert len(history) == 3
        
    def test_get_order_history_with_limit(self):
        """Test getting limited order history."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        for i in range(10):
            manager.place_market_order('BTC-USD', 'buy', 0.1)
            
        history = manager.get_order_history(limit=5)
        assert len(history) == 5
        
    def test_order_history_is_copy(self):
        """Test that returned history is a copy."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        manager.place_market_order('BTC-USD', 'buy', 0.1)
        history1 = manager.get_order_history()
        history1.append({'fake': 'order'})
        history2 = manager.get_order_history()
        
        assert len(history2) == 1  # Original not modified


class TestOrderStatistics:
    """Test order execution statistics."""
    
    def test_order_stats_empty(self):
        """Test stats with no orders."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        stats = manager.get_order_stats()
        
        assert stats['total_orders'] == 0
        assert stats['market_orders'] == 0
        assert stats['limit_orders'] == 0
        assert stats['avg_adjustments'] == 0.0
        assert stats['conversion_rate'] == 0.0
        
    def test_order_stats_with_orders(self):
        """Test stats with mixed orders."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=3)
        
        # Place 2 market orders
        manager.place_market_order('BTC-USD', 'buy', 0.1)
        manager.place_market_order('BTC-USD', 'sell', 0.1)
        
        # Place 3 limit orders (will be auto-adjusted)
        manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=True)
        manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=True)
        manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=True)
        
        stats = manager.get_order_stats()
        
        assert stats['total_orders'] == 5
        assert stats['market_orders'] == 2
        assert stats['limit_orders'] == 3
        assert stats['avg_adjustments'] == 3.0  # All limit orders adjusted 3 times
        assert stats['conversion_rate'] == 1.0  # All limit orders converted
        
    def test_order_stats_partial_conversion(self):
        """Test stats with partial conversion."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=3)
        
        # Place limit orders with and without auto-adjust
        manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=True)  # Converted
        manager.place_limit_order('BTC-USD', 'buy', 0.1, 50000, auto_adjust=False)  # Not converted
        
        stats = manager.get_order_stats()
        
        assert stats['limit_orders'] == 2
        assert stats['conversion_rate'] == 0.5  # 1 out of 2 converted


class TestOrderManagerInitialization:
    """Test Order Manager initialization."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        api_client = Mock()
        manager = OrderManager(api_client)
        
        assert manager.max_adjustments == 3
        assert manager.adjustment_delay_ms == 500
        assert manager.tick_size == 0.01
        assert len(manager.order_history) == 0
        
    def test_custom_initialization(self):
        """Test custom initialization."""
        api_client = Mock()
        manager = OrderManager(api_client, max_adjustments=5, 
                             adjustment_delay_ms=1000, tick_size=0.5)
        
        assert manager.max_adjustments == 5
        assert manager.adjustment_delay_ms == 1000
        assert manager.tick_size == 0.5
