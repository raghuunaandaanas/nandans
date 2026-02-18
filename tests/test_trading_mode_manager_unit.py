"""
Unit tests for Trading Mode Manager

Tests cover:
- Mode switching (soft, smooth, aggressive)
- Entry confirmation requirements
- Trade frequency limits
- Stop loss and position size multipliers
- Daily trade counting
"""

import pytest
from src.main import TradingModeManager
from datetime import datetime, timedelta


class TestModeSwitch:
    """Test trading mode switching."""
    
    def test_initial_mode_soft(self):
        """Test initialization with soft mode."""
        manager = TradingModeManager(initial_mode='soft')
        assert manager.current_mode == 'soft'
        
    def test_initial_mode_smooth(self):
        """Test initialization with smooth mode."""
        manager = TradingModeManager(initial_mode='smooth')
        assert manager.current_mode == 'smooth'
        
    def test_initial_mode_aggressive(self):
        """Test initialization with aggressive mode."""
        manager = TradingModeManager(initial_mode='aggressive')
        assert manager.current_mode == 'aggressive'
        
    def test_invalid_initial_mode_raises_error(self):
        """Test that invalid initial mode raises ValueError."""
        with pytest.raises(ValueError, match="must be one of"):
            TradingModeManager(initial_mode='invalid')
            
    def test_set_mode_from_soft_to_aggressive(self):
        """Test switching from soft to aggressive mode."""
        manager = TradingModeManager(initial_mode='soft')
        result = manager.set_mode('aggressive')
        
        assert result['success'] is True
        assert result['old_mode'] == 'soft'
        assert result['new_mode'] == 'aggressive'
        assert manager.current_mode == 'aggressive'
        
    def test_set_mode_same_mode(self):
        """Test setting the same mode."""
        manager = TradingModeManager(initial_mode='smooth')
        result = manager.set_mode('smooth')
        
        assert result['success'] is True
        assert 'Already in smooth mode' in result['message']
        
    def test_set_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        manager = TradingModeManager()
        
        with pytest.raises(ValueError, match="must be one of"):
            manager.set_mode('turbo')
            
    def test_mode_history_tracking(self):
        """Test that mode changes are tracked in history."""
        manager = TradingModeManager(initial_mode='soft')
        manager.set_mode('smooth')
        manager.set_mode('aggressive')
        
        assert len(manager.mode_history) == 3
        assert manager.mode_history[0][0] == 'soft'
        assert manager.mode_history[1][0] == 'smooth'
        assert manager.mode_history[2][0] == 'aggressive'


class TestEntryConfirmation:
    """Test entry confirmation requirements."""
    
    def test_soft_mode_requires_confirmation(self):
        """Test that soft mode always requires confirmation."""
        manager = TradingModeManager(initial_mode='soft')
        assert manager.get_entry_confirmation_required() is True
        
    def test_smooth_mode_conditional_confirmation(self):
        """Test that smooth mode has conditional confirmation."""
        manager = TradingModeManager(initial_mode='smooth')
        assert manager.get_entry_confirmation_required() is None
        
    def test_aggressive_mode_no_confirmation(self):
        """Test that aggressive mode doesn't require confirmation."""
        manager = TradingModeManager(initial_mode='aggressive')
        assert manager.get_entry_confirmation_required() is False


class TestTradeLimits:
    """Test trade frequency limits."""
    
    def test_soft_mode_trade_limits(self):
        """Test soft mode trade limits (5-10 trades/day)."""
        manager = TradingModeManager(initial_mode='soft')
        limits = manager.get_trade_limit()
        
        assert limits['min'] == 5
        assert limits['max'] == 10
        
    def test_smooth_mode_trade_limits(self):
        """Test smooth mode trade limits (10-30 trades/day)."""
        manager = TradingModeManager(initial_mode='smooth')
        limits = manager.get_trade_limit()
        
        assert limits['min'] == 10
        assert limits['max'] == 30
        
    def test_aggressive_mode_unlimited_trades(self):
        """Test aggressive mode has unlimited trades."""
        manager = TradingModeManager(initial_mode='aggressive')
        limits = manager.get_trade_limit()
        
        assert limits['min'] == 0
        assert limits['max'] == float('inf')


class TestTradeFrequencyControl:
    """Test trade frequency control and counting."""
    
    def test_can_take_trade_initially(self):
        """Test that trades can be taken initially."""
        manager = TradingModeManager(initial_mode='soft')
        result = manager.can_take_trade()
        
        assert result['can_trade'] is True
        assert result['trades_today'] == 0
        
    def test_trade_counting(self):
        """Test that trades are counted."""
        manager = TradingModeManager(initial_mode='soft')
        
        manager.record_trade()
        manager.record_trade()
        manager.record_trade()
        
        result = manager.can_take_trade()
        assert result['trades_today'] == 3
        
    def test_soft_mode_limit_reached(self):
        """Test that soft mode blocks trades after limit."""
        manager = TradingModeManager(initial_mode='soft')
        
        # Take 10 trades (soft mode limit)
        for i in range(10):
            manager.record_trade()
            
        result = manager.can_take_trade()
        
        assert result['can_trade'] is False
        assert 'Daily trade limit reached' in result['reason']
        assert result['trades_today'] == 10
        
    def test_smooth_mode_limit_reached(self):
        """Test that smooth mode blocks trades after limit."""
        manager = TradingModeManager(initial_mode='smooth')
        
        # Take 30 trades (smooth mode limit)
        for i in range(30):
            manager.record_trade()
            
        result = manager.can_take_trade()
        
        assert result['can_trade'] is False
        assert result['trades_today'] == 30
        
    def test_aggressive_mode_no_limit(self):
        """Test that aggressive mode has no trade limit."""
        manager = TradingModeManager(initial_mode='aggressive')
        
        # Take 100 trades
        for i in range(100):
            manager.record_trade()
            
        result = manager.can_take_trade()
        
        assert result['can_trade'] is True
        assert result['remaining'] == 'unlimited'
        
    def test_remaining_trades_calculation(self):
        """Test remaining trades calculation."""
        manager = TradingModeManager(initial_mode='soft')
        
        manager.record_trade()
        manager.record_trade()
        manager.record_trade()
        
        result = manager.can_take_trade()
        
        assert result['remaining'] == 7  # 10 - 3
        
    def test_daily_reset(self):
        """Test that trade count resets on new day."""
        manager = TradingModeManager(initial_mode='soft')
        
        # Take some trades
        for i in range(5):
            manager.record_trade()
            
        # Simulate new day by changing last_reset_date
        manager.last_reset_date = (datetime.now() - timedelta(days=1)).date()
        
        result = manager.can_take_trade()
        
        # Should be reset to 0
        assert result['trades_today'] == 0
        
    def test_manual_reset(self):
        """Test manual reset of daily count."""
        manager = TradingModeManager(initial_mode='soft')
        
        for i in range(5):
            manager.record_trade()
            
        manager.reset_daily_count()
        
        result = manager.can_take_trade()
        assert result['trades_today'] == 0


class TestStopLossMultiplier:
    """Test stop loss size multipliers."""
    
    def test_soft_mode_larger_stop_loss(self):
        """Test that soft mode uses larger stop loss."""
        manager = TradingModeManager(initial_mode='soft')
        multiplier = manager.get_stop_loss_multiplier()
        
        assert multiplier == 1.5
        
    def test_smooth_mode_normal_stop_loss(self):
        """Test that smooth mode uses normal stop loss."""
        manager = TradingModeManager(initial_mode='smooth')
        multiplier = manager.get_stop_loss_multiplier()
        
        assert multiplier == 1.0
        
    def test_aggressive_mode_tighter_stop_loss(self):
        """Test that aggressive mode uses tighter stop loss."""
        manager = TradingModeManager(initial_mode='aggressive')
        multiplier = manager.get_stop_loss_multiplier()
        
        assert multiplier == 0.75


class TestPositionSizeMultiplier:
    """Test position size multipliers."""
    
    def test_soft_mode_smaller_positions(self):
        """Test that soft mode uses smaller positions."""
        manager = TradingModeManager(initial_mode='soft')
        multiplier = manager.get_position_size_multiplier()
        
        assert multiplier == 0.75
        
    def test_smooth_mode_normal_positions(self):
        """Test that smooth mode uses normal positions."""
        manager = TradingModeManager(initial_mode='smooth')
        multiplier = manager.get_position_size_multiplier()
        
        assert multiplier == 1.0
        
    def test_aggressive_mode_larger_positions(self):
        """Test that aggressive mode uses larger positions."""
        manager = TradingModeManager(initial_mode='aggressive')
        multiplier = manager.get_position_size_multiplier()
        
        assert multiplier == 1.25


class TestModeStatistics:
    """Test mode statistics and tracking."""
    
    def test_get_mode_stats(self):
        """Test getting mode statistics."""
        manager = TradingModeManager(initial_mode='soft')
        manager.record_trade()
        manager.record_trade()
        manager.set_mode('smooth')
        
        stats = manager.get_mode_stats()
        
        assert stats['current_mode'] == 'smooth'
        assert stats['trades_today'] == 2
        assert stats['mode_changes'] == 1
        assert len(stats['mode_history']) == 2
        assert 'trade_limits' in stats
        
    def test_mode_stats_includes_limits(self):
        """Test that stats include current mode limits."""
        manager = TradingModeManager(initial_mode='aggressive')
        stats = manager.get_mode_stats()
        
        assert stats['trade_limits']['max'] == float('inf')


class TestModeManagerInitialization:
    """Test Trading Mode Manager initialization."""
    
    def test_default_initialization(self):
        """Test default initialization (smooth mode)."""
        manager = TradingModeManager()
        
        assert manager.current_mode == 'smooth'
        assert manager.daily_trade_count == 0
        assert len(manager.mode_history) == 1
        
    def test_initialization_creates_history_entry(self):
        """Test that initialization creates first history entry."""
        manager = TradingModeManager(initial_mode='aggressive')
        
        assert len(manager.mode_history) == 1
        assert manager.mode_history[0][0] == 'aggressive'
