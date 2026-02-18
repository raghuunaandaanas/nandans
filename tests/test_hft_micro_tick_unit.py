"""
Unit tests for HFT Micro Tick Trader.
Tests micro tick extraction, micro points calculation, and HFT trade decisions.
"""

import pytest
from src.main import HFTMicroTickTrader


class TestHFTMicroTickTrader:
    """Test HFT Micro Tick Trader functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hft_trader = HFTMicroTickTrader(
            profit_target=0.003,
            stop_loss=0.0005,
            max_hold_seconds=60
        )
    
    def test_extract_micro_levels_basic(self):
        """Test basic micro level extraction."""
        result = self.hft_trader.extract_micro_levels(123456.78)
        
        assert result['last_digit'] == 8
        assert result['last_2_digits'] == 78
        assert result['last_3_digits'] == 678
        assert result['price'] == 123456.78
    
    def test_extract_micro_levels_small_price(self):
        """Test micro level extraction for small prices."""
        result = self.hft_trader.extract_micro_levels(45.67)
        
        assert result['last_digit'] == 7
        assert result['last_2_digits'] == 67
        assert result['last_3_digits'] == 567
    
    def test_extract_micro_levels_zero_cents(self):
        """Test micro level extraction with zero cents."""
        result = self.hft_trader.extract_micro_levels(1000.00)
        
        assert result['last_digit'] == 0
        assert result['last_2_digits'] == 0
        assert result['last_3_digits'] == 0
    
    def test_calculate_micro_points(self):
        """Test micro points calculation."""
        digits = {
            'last_digit': 6,
            'last_2_digits': 56,
            'last_3_digits': 456
        }
        
        result = self.hft_trader.calculate_micro_points(digits)
        
        assert result['micro_points'] == pytest.approx(6 * 0.002611, rel=1e-6)
        assert result['mini_points'] == pytest.approx(56 * 0.002611, rel=1e-6)
        assert result['standard_points'] == pytest.approx(456 * 0.002611, rel=1e-6)
    
    def test_should_hft_trade_no_previous_price(self):
        """Test HFT trade decision without previous price."""
        result = self.hft_trader.should_hft_trade(
            current_price=50000.00,
            micro_levels={},
            previous_price=None
        )
        
        assert result['should_trade'] is False
        assert 'No previous price' in result['reason']
    
    def test_should_hft_trade_bullish_cross(self):
        """Test HFT trade on bullish micro level cross."""
        result = self.hft_trader.should_hft_trade(
            current_price=50000.07,
            micro_levels={},
            previous_price=50000.03
        )
        
        assert result['should_trade'] is True
        assert result['direction'] == 'long'
        assert result['entry_price'] == 50000.07
        assert result['target_price'] > result['entry_price']
        assert result['stop_loss_price'] < result['entry_price']
    
    def test_should_hft_trade_bearish_cross(self):
        """Test HFT trade on bearish micro level cross."""
        result = self.hft_trader.should_hft_trade(
            current_price=50000.03,
            micro_levels={},
            previous_price=50000.07
        )
        
        assert result['should_trade'] is True
        assert result['direction'] == 'short'
        assert result['entry_price'] == 50000.03
        assert result['target_price'] < result['entry_price']
        assert result['stop_loss_price'] > result['entry_price']
    
    def test_should_hft_trade_no_cross(self):
        """Test HFT trade when no micro level cross."""
        result = self.hft_trader.should_hft_trade(
            current_price=50000.05,
            micro_levels={},
            previous_price=50000.05  # Same last digit, no cross
        )
        
        assert result['should_trade'] is False
        assert 'No micro level cross' in result['reason']
    
    def test_check_hft_exit_profit_target_long(self):
        """Test HFT exit on profit target for long position."""
        trade = {
            'direction': 'long',
            'entry_price': 50000.00,
            'target_price': 50150.00,
            'stop_loss_price': 49975.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=50150.00,
            elapsed_seconds=10
        )
        
        assert result['should_exit'] is True
        assert result['reason'] == 'Profit target reached'
        assert result['pnl_pct'] > 0
    
    def test_check_hft_exit_profit_target_short(self):
        """Test HFT exit on profit target for short position."""
        trade = {
            'direction': 'short',
            'entry_price': 50000.00,
            'target_price': 49850.00,
            'stop_loss_price': 50025.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=49850.00,
            elapsed_seconds=10
        )
        
        assert result['should_exit'] is True
        assert result['reason'] == 'Profit target reached'
        assert result['pnl_pct'] > 0
    
    def test_check_hft_exit_stop_loss_long(self):
        """Test HFT exit on stop loss for long position."""
        trade = {
            'direction': 'long',
            'entry_price': 50000.00,
            'target_price': 50150.00,
            'stop_loss_price': 49975.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=49970.00,
            elapsed_seconds=10
        )
        
        assert result['should_exit'] is True
        assert result['reason'] == 'Stop loss triggered'
        assert result['pnl_pct'] < 0
    
    def test_check_hft_exit_stop_loss_short(self):
        """Test HFT exit on stop loss for short position."""
        trade = {
            'direction': 'short',
            'entry_price': 50000.00,
            'target_price': 49850.00,
            'stop_loss_price': 50025.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=50030.00,
            elapsed_seconds=10
        )
        
        assert result['should_exit'] is True
        assert result['reason'] == 'Stop loss triggered'
        assert result['pnl_pct'] < 0
    
    def test_check_hft_exit_max_hold_time(self):
        """Test HFT exit on max hold time."""
        trade = {
            'direction': 'long',
            'entry_price': 50000.00,
            'target_price': 50150.00,
            'stop_loss_price': 49975.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=50050.00,
            elapsed_seconds=65
        )
        
        assert result['should_exit'] is True
        assert result['reason'] == 'Max hold time reached'
    
    def test_check_hft_exit_still_active(self):
        """Test HFT trade still active."""
        trade = {
            'direction': 'long',
            'entry_price': 50000.00,
            'target_price': 50150.00,
            'stop_loss_price': 49975.00
        }
        
        result = self.hft_trader.check_hft_exit(
            trade=trade,
            current_price=50050.00,
            elapsed_seconds=10
        )
        
        assert result['should_exit'] is False
        assert result['reason'] == 'Trade still active'
    
    def test_hft_trader_initialization(self):
        """Test HFT trader initialization with custom parameters."""
        trader = HFTMicroTickTrader(
            profit_target=0.005,
            stop_loss=0.001,
            max_hold_seconds=30
        )
        
        assert trader.profit_target == 0.005
        assert trader.stop_loss == 0.001
        assert trader.max_hold_seconds == 30
        assert trader.B5_FACTOR == 0.002611
