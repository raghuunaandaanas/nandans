"""
Unit tests for Paper Trading Engine

Tests cover:
- Order simulation
- Slippage calculation
- Position tracking
- P&L calculation
- Trade history
"""

import pytest
from src.main import PaperTradingEngine
from unittest.mock import Mock


class TestPaperTradingInitialization:
    """Test paper trading initialization."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        db = Mock()
        engine = PaperTradingEngine(db)
        
        assert engine.initial_capital == 10000.0
        assert engine.current_capital == 10000.0
        assert engine.slippage_percent == 0.1
        assert len(engine.positions) == 0
        assert engine.is_active is True
        
    def test_custom_initialization(self):
        """Test custom initialization."""
        db = Mock()
        engine = PaperTradingEngine(db, initial_capital=50000.0, slippage_percent=0.2)
        
        assert engine.initial_capital == 50000.0
        assert engine.slippage_percent == 0.2
        
    def test_invalid_capital_raises_error(self):
        """Test that invalid capital raises ValueError."""
        db = Mock()
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            PaperTradingEngine(db, initial_capital=0)
            
    def test_invalid_slippage_raises_error(self):
        """Test that invalid slippage raises ValueError."""
        db = Mock()
        with pytest.raises(ValueError, match="slippage_percent must be non-negative"):
            PaperTradingEngine(db, slippage_percent=-0.1)


class TestSlippageSimulation:
    """Test slippage simulation."""
    
    def test_buy_order_slippage_increases_price(self):
        """Test that buy orders have positive slippage."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.1)
        
        original_price = 50000.0
        slipped_price = engine.simulate_slippage(original_price, 'buy')
        
        # Should be 0.1% higher
        expected = 50000.0 * 1.001
        assert slipped_price == pytest.approx(expected, abs=0.01)
        
    def test_sell_order_slippage_decreases_price(self):
        """Test that sell orders have negative slippage."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.1)
        
        original_price = 50000.0
        slipped_price = engine.simulate_slippage(original_price, 'sell')
        
        # Should be 0.1% lower
        expected = 50000.0 * 0.999
        assert slipped_price == pytest.approx(expected, abs=0.01)
        
    def test_zero_slippage(self):
        """Test with zero slippage."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        price = 50000.0
        slipped_buy = engine.simulate_slippage(price, 'buy')
        slipped_sell = engine.simulate_slippage(price, 'sell')
        
        assert slipped_buy == price
        assert slipped_sell == price
        
    def test_invalid_price_raises_error(self):
        """Test that invalid price raises ValueError."""
        db = Mock()
        engine = PaperTradingEngine(db)
        
        with pytest.raises(ValueError, match="price must be positive"):
            engine.simulate_slippage(0, 'buy')
            
    def test_invalid_side_raises_error(self):
        """Test that invalid side raises ValueError."""
        db = Mock()
        engine = PaperTradingEngine(db)
        
        with pytest.raises(ValueError, match="side must be 'buy' or 'sell'"):
            engine.simulate_slippage(50000, 'long')


class TestOrderSimulation:
    """Test order fill simulation."""
    
    def test_simulate_market_buy_order(self):
        """Test simulating a market buy order."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.1)
        
        order = {
            'instrument': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'order_type': 'market'
        }
        bid_ask = {'bid': 49900, 'ask': 50000}
        
        filled = engine.simulate_order_fill(order, bid_ask)
        
        assert filled['instrument'] == 'BTC-USD'
        assert filled['side'] == 'buy'
        assert filled['quantity'] == 0.1
        assert filled['status'] == 'filled'
        assert filled['paper_trade'] is True
        # Should fill at ask + slippage
        assert filled['fill_price'] > 50000
        
    def test_simulate_market_sell_order(self):
        """Test simulating a market sell order."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.1)
        
        order = {
            'instrument': 'BTC-USD',
            'side': 'sell',
            'quantity': 0.1,
            'order_type': 'market'
        }
        bid_ask = {'bid': 49900, 'ask': 50000}
        
        filled = engine.simulate_order_fill(order, bid_ask)
        
        # Should fill at bid - slippage
        assert filled['fill_price'] < 49900
        
    def test_simulate_limit_order(self):
        """Test simulating a limit order."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.1)
        
        order = {
            'instrument': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'order_type': 'limit',
            'price': 49500
        }
        bid_ask = {'bid': 49900, 'ask': 50000}
        
        filled = engine.simulate_order_fill(order, bid_ask)
        
        # Should fill at limit price + slippage
        assert filled['fill_price'] > 49500
        
    def test_invalid_order_raises_error(self):
        """Test that invalid order raises ValueError."""
        db = Mock()
        engine = PaperTradingEngine(db)
        
        with pytest.raises(ValueError, match="order cannot be empty"):
            engine.simulate_order_fill(None, {'bid': 100, 'ask': 101})
            
    def test_invalid_bid_ask_raises_error(self):
        """Test that invalid bid/ask raises ValueError."""
        db = Mock()
        engine = PaperTradingEngine(db)
        
        order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        
        with pytest.raises(ValueError, match="must contain 'bid' and 'ask'"):
            engine.simulate_order_fill(order, {'bid': 100})


class TestPositionTracking:
    """Test position tracking."""
    
    def test_new_buy_creates_position(self):
        """Test that buy order creates new position."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        order = {
            'instrument': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'order_type': 'market'
        }
        engine.simulate_order_fill(order, {'bid': 49900, 'ask': 50000})
        
        positions = engine.get_paper_positions()
        assert len(positions) == 1
        assert positions[0]['instrument'] == 'BTC-USD'
        assert positions[0]['quantity'] == 0.1
        assert positions[0]['side'] == 'long'
        
    def test_multiple_buys_average_price(self):
        """Test that multiple buys average the entry price."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        # First buy at 50000
        order1 = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(order1, {'bid': 49900, 'ask': 50000})
        
        # Second buy at 51000
        order2 = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(order2, {'bid': 50900, 'ask': 51000})
        
        positions = engine.get_paper_positions()
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.2
        # Average price should be (50000 + 51000) / 2 = 50500
        assert positions[0]['entry_price'] == pytest.approx(50500, abs=1)
        
    def test_sell_closes_position(self):
        """Test that sell order closes position."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        # Buy
        buy_order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(buy_order, {'bid': 49900, 'ask': 50000})
        
        # Sell
        sell_order = {'instrument': 'BTC-USD', 'side': 'sell', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(sell_order, {'bid': 51000, 'ask': 51100})
        
        positions = engine.get_paper_positions()
        assert len(positions) == 0
        
    def test_partial_sell_reduces_position(self):
        """Test that partial sell reduces position."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        # Buy 0.2
        buy_order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.2, 'order_type': 'market'}
        engine.simulate_order_fill(buy_order, {'bid': 49900, 'ask': 50000})
        
        # Sell 0.1
        sell_order = {'instrument': 'BTC-USD', 'side': 'sell', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(sell_order, {'bid': 51000, 'ask': 51100})
        
        positions = engine.get_paper_positions()
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.1


class TestPnLCalculation:
    """Test P&L calculation."""
    
    def test_realized_pnl_on_close(self):
        """Test realized P&L when position is closed."""
        db = Mock()
        engine = PaperTradingEngine(db, initial_capital=10000.0, slippage_percent=0.0)
        
        # Buy at 50000
        buy_order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(buy_order, {'bid': 49900, 'ask': 50000})
        
        # Sell at 51000 (1000 profit per BTC, 0.1 BTC = 100 profit)
        sell_order = {'instrument': 'BTC-USD', 'side': 'sell', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(sell_order, {'bid': 51000, 'ask': 51100})
        
        pnl = engine.get_paper_pnl()
        assert pnl['realized_pnl'] == pytest.approx(100, abs=0.01)
        assert pnl['current_capital'] == pytest.approx(10100, abs=0.01)
        
    def test_unrealized_pnl_with_open_position(self):
        """Test unrealized P&L with open position."""
        db = Mock()
        engine = PaperTradingEngine(db, initial_capital=10000.0, slippage_percent=0.0)
        
        # Buy at 50000
        buy_order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(buy_order, {'bid': 49900, 'ask': 50000})
        
        # Check unrealized P&L at 51000
        pnl = engine.get_paper_pnl(current_prices={'BTC-USD': 51000})
        
        assert pnl['unrealized_pnl'] == pytest.approx(100, abs=0.01)
        assert pnl['total_pnl'] == pytest.approx(100, abs=0.01)
        
    def test_return_percentage_calculation(self):
        """Test return percentage calculation."""
        db = Mock()
        engine = PaperTradingEngine(db, initial_capital=10000.0, slippage_percent=0.0)
        
        # Make 1000 profit
        engine.current_capital = 11000.0
        
        pnl = engine.get_paper_pnl()
        assert pnl['return_pct'] == pytest.approx(10.0, abs=0.01)
        
    def test_closed_trades_tracking(self):
        """Test that closed trades are tracked."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        # Buy and sell
        buy_order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(buy_order, {'bid': 49900, 'ask': 50000})
        
        sell_order = {'instrument': 'BTC-USD', 'side': 'sell', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(sell_order, {'bid': 51000, 'ask': 51100})
        
        trades = engine.get_paper_trades()
        assert len(trades) == 1
        assert trades[0]['entry_price'] == 50000
        assert trades[0]['exit_price'] == 51000
        assert trades[0]['pnl'] == pytest.approx(100, abs=0.01)


class TestPaperTradingReset:
    """Test paper trading reset."""
    
    def test_reset_clears_positions(self):
        """Test that reset clears all positions."""
        db = Mock()
        engine = PaperTradingEngine(db, slippage_percent=0.0)
        
        # Create position
        order = {'instrument': 'BTC-USD', 'side': 'buy', 'quantity': 0.1, 'order_type': 'market'}
        engine.simulate_order_fill(order, {'bid': 49900, 'ask': 50000})
        
        engine.reset_paper_trading()
        
        assert len(engine.get_paper_positions()) == 0
        assert len(engine.get_paper_trades()) == 0
        assert engine.current_capital == engine.initial_capital
