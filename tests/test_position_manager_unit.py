"""
Unit tests for PositionManager class.

Tests position sizing, stop loss calculation, pyramiding, and trailing stops.
"""

import pytest
from src.main import PositionManager, LevelCalculator


class TestPositionSizing:
    """Test position size calculation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pm = PositionManager()
    
    def test_position_size_calculation(self):
        """Test basic position size calculation."""
        # Risk 1% of $10,000 with $50 stop loss distance at price $50,000
        size = self.pm.calculate_position_size(10000, 0.01, 50, 50000)
        
        # Risk amount = $100
        # Position value = $100 / (50/50000) = $100,000
        # Quantity = $100,000 / $50,000 = 2
        assert size == 2
    
    def test_position_size_with_different_risk(self):
        """Test position sizing with different risk percentages."""
        # 2% risk
        size1 = self.pm.calculate_position_size(10000, 0.02, 50, 50000)
        
        # 1% risk
        size2 = self.pm.calculate_position_size(10000, 0.01, 50, 50000)
        
        # Higher risk should give larger position
        assert size1 > size2
    
    def test_position_size_minimum_one(self):
        """Test that position size is at least 1."""
        # Very small capital or large stop loss
        size = self.pm.calculate_position_size(100, 0.01, 100, 50000)
        
        assert size >= 1
    
    def test_invalid_capital_raises_error(self):
        """Test that invalid capital raises ValueError."""
        with pytest.raises(ValueError, match="Capital must be positive"):
            self.pm.calculate_position_size(0, 0.01, 50, 50000)
        
        with pytest.raises(ValueError, match="Capital must be positive"):
            self.pm.calculate_position_size(-1000, 0.01, 50, 50000)
    
    def test_invalid_risk_percent_raises_error(self):
        """Test that invalid risk percent raises ValueError."""
        with pytest.raises(ValueError, match="Risk percent must be between 0 and 1"):
            self.pm.calculate_position_size(10000, 0, 50, 50000)
        
        with pytest.raises(ValueError, match="Risk percent must be between 0 and 1"):
            self.pm.calculate_position_size(10000, 1.5, 50, 50000)
    
    def test_invalid_stop_loss_distance_raises_error(self):
        """Test that invalid stop loss distance raises ValueError."""
        with pytest.raises(ValueError, match="Stop loss distance must be positive"):
            self.pm.calculate_position_size(10000, 0.01, 0, 50000)
        
        with pytest.raises(ValueError, match="Stop loss distance must be positive"):
            self.pm.calculate_position_size(10000, 0.01, -50, 50000)
    
    def test_invalid_price_raises_error(self):
        """Test that invalid price raises ValueError."""
        with pytest.raises(ValueError, match="Price must be positive"):
            self.pm.calculate_position_size(10000, 0.01, 50, 0)


class TestStopLossCalculation:
    """Test stop loss calculation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pm = PositionManager()
        self.calculator = LevelCalculator()
        self.levels = self.calculator.calculate_levels(50000.00, '1m')
    
    def test_long_stop_loss_below_base(self):
        """Test that long stop loss is below base price."""
        stop_loss = self.pm.calculate_stop_loss(50130, self.levels, 'long')
        
        # Stop loss should be base - (points × 0.5)
        expected = self.levels['base'] - (self.levels['points'] * 0.5)
        
        assert abs(stop_loss - expected) < 0.01
        assert stop_loss < self.levels['base']
    
    def test_short_stop_loss_above_base(self):
        """Test that short stop loss is above base price."""
        stop_loss = self.pm.calculate_stop_loss(49870, self.levels, 'short')
        
        # Stop loss should be base + (points × 0.5)
        expected = self.levels['base'] + (self.levels['points'] * 0.5)
        
        assert abs(stop_loss - expected) < 0.01
        assert stop_loss > self.levels['base']
    
    def test_stop_loss_is_half_points_from_base(self):
        """Test that stop loss is exactly 0.5 × Points from base."""
        stop_loss_long = self.pm.calculate_stop_loss(50130, self.levels, 'long')
        stop_loss_short = self.pm.calculate_stop_loss(49870, self.levels, 'short')
        
        # Distance should be 0.5 × Points
        distance_long = self.levels['base'] - stop_loss_long
        distance_short = stop_loss_short - self.levels['base']
        
        expected_distance = self.levels['points'] * 0.5
        
        assert abs(distance_long - expected_distance) < 0.01
        assert abs(distance_short - expected_distance) < 0.01
    
    def test_invalid_direction_raises_error(self):
        """Test that invalid direction raises ValueError."""
        with pytest.raises(ValueError, match="Invalid direction"):
            self.pm.calculate_stop_loss(50130, self.levels, 'sideways')
    
    def test_invalid_levels_raises_error(self):
        """Test that invalid levels dictionary raises ValueError."""
        with pytest.raises(ValueError, match="Invalid levels"):
            self.pm.calculate_stop_loss(50130, {}, 'long')


class TestPyramiding:
    """Test pyramiding logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pm = PositionManager()
        self.calculator = LevelCalculator()
        self.levels = self.calculator.calculate_levels(50000.00, '1m')
    
    def test_pyramid_on_profitable_long(self):
        """Test pyramiding on profitable long position."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'size': 10,
            'initial_size': 10
        }
        
        # Price at BU2 (profitable)
        result = self.pm.should_pyramid(position, 50261, self.levels)
        
        assert result['should_pyramid'] is True
        assert result['add_size'] == 10
    
    def test_pyramid_on_profitable_short(self):
        """Test pyramiding on profitable short position."""
        position = {
            'direction': 'short',
            'entry_price': 49870,
            'size': 10,
            'initial_size': 10
        }
        
        # Price at BE2 (profitable)
        result = self.pm.should_pyramid(position, 49739, self.levels)
        
        assert result['should_pyramid'] is True
        assert result['add_size'] == 10
    
    def test_no_pyramid_on_unprofitable_position(self):
        """Test no pyramiding on unprofitable position."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'size': 10,
            'initial_size': 10
        }
        
        # Price below entry (unprofitable)
        result = self.pm.should_pyramid(position, 50000, self.levels)
        
        assert result['should_pyramid'] is False
        assert result['reason'] == 'Position not profitable'
    
    def test_no_pyramid_at_max_size(self):
        """Test no pyramiding when max size reached (100× initial)."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'size': 1000,  # 100× initial
            'initial_size': 10
        }
        
        result = self.pm.should_pyramid(position, 50261, self.levels)
        
        assert result['should_pyramid'] is False
        assert 'Max size reached' in result['reason']
    
    def test_pyramid_size_limited_by_max(self):
        """Test that pyramid size is limited by max size."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'size': 995,  # Close to max (1000)
            'initial_size': 10
        }
        
        result = self.pm.should_pyramid(position, 50261, self.levels)
        
        assert result['should_pyramid'] is True
        assert result['add_size'] == 5  # Only 5 more to reach 1000
    
    def test_invalid_direction_no_pyramid(self):
        """Test that invalid direction prevents pyramiding."""
        position = {
            'direction': 'invalid',
            'entry_price': 50130,
            'size': 10,
            'initial_size': 10
        }
        
        result = self.pm.should_pyramid(position, 50261, self.levels)
        
        assert result['should_pyramid'] is False


class TestTrailingStops:
    """Test trailing stop loss adjustment."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pm = PositionManager()
        self.calculator = LevelCalculator()
        self.levels = self.calculator.calculate_levels(50000.00, '1m')
    
    def test_move_to_breakeven_at_bu2(self):
        """Test moving stop to breakeven at BU2 for long position."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'stop_loss': 49935
        }
        
        # Price at BU2
        result = self.pm.adjust_stop_loss(position, self.levels['bu2'], self.levels)
        
        assert result['new_stop_loss'] == 50130  # Moved to entry
        assert 'breakeven' in result['reason'].lower()
    
    def test_trail_to_bu1_at_bu3(self):
        """Test trailing stop to BU1 at BU3 for long position."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'stop_loss': 50130  # Already at breakeven
        }
        
        # Price at BU3
        result = self.pm.adjust_stop_loss(position, self.levels['bu3'], self.levels)
        
        assert result['new_stop_loss'] == self.levels['bu1']
        assert 'trailing' in result['reason'].lower()
    
    def test_move_to_breakeven_at_be2_short(self):
        """Test moving stop to breakeven at BE2 for short position."""
        position = {
            'direction': 'short',
            'entry_price': 49870,
            'stop_loss': 50065
        }
        
        # Price at BE2
        result = self.pm.adjust_stop_loss(position, self.levels['be2'], self.levels)
        
        assert result['new_stop_loss'] == 49870  # Moved to entry
        assert 'breakeven' in result['reason'].lower()
    
    def test_trail_to_be1_at_be3_short(self):
        """Test trailing stop to BE1 at BE3 for short position."""
        position = {
            'direction': 'short',
            'entry_price': 49870,
            'stop_loss': 49870  # Already at breakeven
        }
        
        # Price at BE3
        result = self.pm.adjust_stop_loss(position, self.levels['be3'], self.levels)
        
        assert result['new_stop_loss'] == self.levels['be1']
        assert 'trailing' in result['reason'].lower()
    
    def test_no_adjustment_needed(self):
        """Test no adjustment when conditions not met."""
        position = {
            'direction': 'long',
            'entry_price': 50130,
            'stop_loss': 49935
        }
        
        # Price still at BU1
        result = self.pm.adjust_stop_loss(position, 50150, self.levels)
        
        assert result['new_stop_loss'] == 49935  # No change
        assert 'No adjustment' in result['reason']
    
    def test_invalid_direction_no_adjustment(self):
        """Test that invalid direction returns current stop."""
        position = {
            'direction': 'invalid',
            'entry_price': 50130,
            'stop_loss': 49935
        }
        
        result = self.pm.adjust_stop_loss(position, 50261, self.levels)
        
        assert result['new_stop_loss'] == 49935


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
