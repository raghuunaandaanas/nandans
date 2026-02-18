"""
Unit tests for ProfitRidingSystem class.
Tests profit riding, trailing stops, and breakeven management.
"""

import pytest
from src.main import ProfitRidingSystem, PositionManager, LevelCalculator


class TestBreakevenManagement:
    """Test moving stop loss to breakeven."""
    
    def test_move_to_breakeven_at_bu2_long(self):
        """Test moving to breakeven at BU2 for long positions."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'long',
            'entry_price': 100.0,
            'stop_loss': 99.0
        }
        
        # At BU2
        should_move = system.should_move_to_breakeven(position, levels['bu2'], levels)
        
        assert should_move == True
    
    def test_move_to_breakeven_at_be2_short(self):
        """Test moving to breakeven at BE2 for short positions."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'short',
            'entry_price': 100.0,
            'stop_loss': 101.0
        }
        
        # At BE2
        should_move = system.should_move_to_breakeven(position, levels['be2'], levels)
        
        assert should_move == True
    
    def test_no_breakeven_before_bu2(self):
        """Test no breakeven move before BU2."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'long',
            'entry_price': 100.0,
            'stop_loss': 99.0
        }
        
        # At BU1 (before BU2)
        should_move = system.should_move_to_breakeven(position, levels['bu1'], levels)
        
        assert should_move == False


class TestTrailingStopCalculation:
    """Test trailing stop loss calculation."""
    
    def test_trailing_stop_at_bu3_long(self):
        """Test trailing stop at BU3 for long positions."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'long',
            'entry_price': 100.0,
            'stop_loss': 99.0
        }
        
        # At BU3
        trailing_stop = system.calculate_trailing_stop(position, levels['bu3'], levels)
        
        # Should be between BU1 and BU2
        assert trailing_stop > levels['bu1']
        assert trailing_stop < levels['bu2']
    
    def test_trailing_stop_at_be3_short(self):
        """Test trailing stop at BE3 for short positions."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'short',
            'entry_price': 100.0,
            'stop_loss': 101.0
        }
        
        # At BE3
        trailing_stop = system.calculate_trailing_stop(position, levels['be3'], levels)
        
        # Should be between BE1 and BE2
        assert trailing_stop < levels['be1']
        assert trailing_stop > levels['be2']
    
    def test_trailing_stop_at_breakeven_at_bu2(self):
        """Test trailing stop at breakeven when at BU2."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        calc = LevelCalculator()
        
        levels = calc.calculate_levels(100.0, '1m')
        
        position = {
            'direction': 'long',
            'entry_price': 100.0,
            'stop_loss': 99.0
        }
        
        # At BU2
        trailing_stop = system.calculate_trailing_stop(position, levels['bu2'], levels)
        
        # Should be at entry price (breakeven)
        assert trailing_stop == position['entry_price']


class TestExitDecision:
    """Test exit decision based on candle close."""
    
    def test_exit_on_close_below_trailing_stop_long(self):
        """Test exit when candle closes below trailing stop for long."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        position = {
            'direction': 'long',
            'entry_price': 100.0
        }
        
        candle = {
            'high': 102.0,
            'low': 98.0,
            'close': 98.5
        }
        
        trailing_stop = 99.0
        
        should_exit = system.should_exit_position(position, candle, trailing_stop)
        
        assert should_exit == True
    
    def test_no_exit_on_wick_below_stop_long(self):
        """Test no exit on wick below stop (only close matters)."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        position = {
            'direction': 'long',
            'entry_price': 100.0
        }
        
        candle = {
            'high': 102.0,
            'low': 98.0,  # Wick below stop
            'close': 101.0  # Close above stop
        }
        
        trailing_stop = 99.0
        
        should_exit = system.should_exit_position(position, candle, trailing_stop)
        
        assert should_exit == False
    
    def test_exit_on_close_above_trailing_stop_short(self):
        """Test exit when candle closes above trailing stop for short."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        position = {
            'direction': 'short',
            'entry_price': 100.0
        }
        
        candle = {
            'high': 102.0,
            'low': 98.0,
            'close': 101.5
        }
        
        trailing_stop = 101.0
        
        should_exit = system.should_exit_position(position, candle, trailing_stop)
        
        assert should_exit == True


class TestProfitRidingStats:
    """Test profit riding statistics tracking."""
    
    def test_update_stats_successful_ride(self):
        """Test updating stats for successful ride."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        position = {'entry_price': 100.0, 'exit_price': 110.0}
        
        system.update_profit_riding_stats(position, 'TARGET_REACHED', 5)
        
        stats = system.get_profit_riding_stats()
        
        assert stats['total_rides'] == 1
        assert stats['successful_rides'] == 1
        assert stats['max_levels_reached'] == 5
    
    def test_update_stats_early_exit(self):
        """Test updating stats for early exit."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        position = {'entry_price': 100.0, 'exit_price': 102.0}
        
        system.update_profit_riding_stats(position, 'STOP_LOSS', 2)
        
        stats = system.get_profit_riding_stats()
        
        assert stats['total_rides'] == 1
        assert stats['early_exits'] == 1
    
    def test_calculate_success_rate(self):
        """Test success rate calculation."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        # 2 successful, 1 early exit
        system.update_profit_riding_stats({}, 'TARGET_REACHED', 5)
        system.update_profit_riding_stats({}, 'TARGET_REACHED', 4)
        system.update_profit_riding_stats({}, 'STOP_LOSS', 2)
        
        stats = system.get_profit_riding_stats()
        
        assert stats['success_rate'] == pytest.approx(2/3, rel=0.01)
    
    def test_track_max_levels_reached(self):
        """Test tracking maximum levels reached."""
        pos_manager = PositionManager()
        system = ProfitRidingSystem(pos_manager)
        
        system.update_profit_riding_stats({}, 'TARGET_REACHED', 3)
        system.update_profit_riding_stats({}, 'TARGET_REACHED', 5)
        system.update_profit_riding_stats({}, 'TARGET_REACHED', 4)
        
        stats = system.get_profit_riding_stats()
        
        assert stats['max_levels_reached'] == 5
