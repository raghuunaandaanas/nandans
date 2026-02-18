"""
Unit tests for RiskManager class.

Tests daily loss limits, per-trade loss limits, exposure limits, and circuit breakers.
"""

import pytest
from src.main import RiskManager


class TestDailyLossLimit:
    """Test daily loss limit enforcement."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rm = RiskManager(daily_loss_limit=0.05)  # 5% daily limit
    
    def test_daily_loss_limit_not_reached(self):
        """Test that daily loss below limit is OK."""
        # Loss of $400 on $10,000 capital = 4%
        result = self.rm.check_daily_loss_limit(-400, 10000)
        
        assert result['limit_reached'] is False
        assert result['current_loss_pct'] == 0.04
        assert result['limit_pct'] == 0.05
    
    def test_daily_loss_limit_reached(self):
        """Test that daily loss at or above limit is flagged."""
        # Loss of $600 on $10,000 capital = 6%
        result = self.rm.check_daily_loss_limit(-600, 10000)
        
        assert result['limit_reached'] is True
        assert result['current_loss_pct'] == 0.06
        assert result['limit_pct'] == 0.05
    
    def test_daily_loss_limit_exactly_at_limit(self):
        """Test that daily loss exactly at limit is flagged."""
        # Loss of $500 on $10,000 capital = 5%
        result = self.rm.check_daily_loss_limit(-500, 10000)
        
        assert result['limit_reached'] is True
        assert result['current_loss_pct'] == 0.05
    
    def test_daily_profit_no_limit(self):
        """Test that daily profit doesn't trigger limit."""
        # Profit of $500
        result = self.rm.check_daily_loss_limit(500, 10000)
        
        assert result['limit_reached'] is False
        assert result['current_loss_pct'] == 0.0
    
    def test_invalid_capital_raises_error(self):
        """Test that invalid capital raises ValueError."""
        with pytest.raises(ValueError, match="Capital must be positive"):
            self.rm.check_daily_loss_limit(-500, 0)


class TestPerTradeLossLimit:
    """Test per-trade loss limit enforcement."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rm = RiskManager(per_trade_loss_limit=0.02)  # 2% per trade limit
    
    def test_per_trade_loss_limit_not_reached(self):
        """Test that trade loss below limit is OK."""
        # Loss of $150 on $10,000 capital = 1.5%
        result = self.rm.check_per_trade_loss_limit(-150, 10000)
        
        assert result['limit_reached'] is False
        assert result['loss_pct'] == 0.015
        assert result['limit_pct'] == 0.02
    
    def test_per_trade_loss_limit_reached(self):
        """Test that trade loss at or above limit is flagged."""
        # Loss of $250 on $10,000 capital = 2.5%
        result = self.rm.check_per_trade_loss_limit(-250, 10000)
        
        assert result['limit_reached'] is True
        assert result['loss_pct'] == 0.025
        assert result['limit_pct'] == 0.02
    
    def test_per_trade_loss_exactly_at_limit(self):
        """Test that trade loss exactly at limit is flagged."""
        # Loss of $200 on $10,000 capital = 2%
        result = self.rm.check_per_trade_loss_limit(-200, 10000)
        
        assert result['limit_reached'] is True
        assert result['loss_pct'] == 0.02
    
    def test_winning_trade_no_limit(self):
        """Test that winning trade doesn't trigger limit."""
        # Profit of $200
        result = self.rm.check_per_trade_loss_limit(200, 10000)
        
        assert result['limit_reached'] is False
        assert result['loss_pct'] == 0.0
    
    def test_invalid_capital_raises_error(self):
        """Test that invalid capital raises ValueError."""
        with pytest.raises(ValueError, match="Capital must be positive"):
            self.rm.check_per_trade_loss_limit(-200, 0)


class TestExposureLimits:
    """Test exposure limit enforcement."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rm = RiskManager(max_exposure=0.5)  # 50% max exposure
    
    def test_exposure_below_limit(self):
        """Test that exposure below limit is OK."""
        # Position worth $4,000 on $10,000 capital = 40%
        positions = [{'size': 1, 'price': 4000}]
        
        result = self.rm.check_exposure_limits(positions, 10000)
        
        assert result['limit_exceeded'] is False
        assert result['current_exposure_pct'] == 0.4
        assert result['limit_pct'] == 0.5
    
    def test_exposure_above_limit(self):
        """Test that exposure above limit is flagged."""
        # Position worth $6,000 on $10,000 capital = 60%
        positions = [{'size': 1, 'price': 6000}]
        
        result = self.rm.check_exposure_limits(positions, 10000)
        
        assert result['limit_exceeded'] is True
        assert result['current_exposure_pct'] == 0.6
    
    def test_exposure_exactly_at_limit(self):
        """Test that exposure exactly at limit is OK."""
        # Position worth $5,000 on $10,000 capital = 50%
        positions = [{'size': 1, 'price': 5000}]
        
        result = self.rm.check_exposure_limits(positions, 10000)
        
        assert result['limit_exceeded'] is False
        assert result['current_exposure_pct'] == 0.5
    
    def test_multiple_positions_exposure(self):
        """Test exposure calculation with multiple positions."""
        # Two positions: $2,000 + $3,000 = $5,000 on $10,000 capital = 50%
        positions = [
            {'size': 1, 'price': 2000},
            {'size': 1, 'price': 3000}
        ]
        
        result = self.rm.check_exposure_limits(positions, 10000)
        
        assert result['current_exposure_pct'] == 0.5
    
    def test_no_positions_zero_exposure(self):
        """Test that no positions means zero exposure."""
        result = self.rm.check_exposure_limits([], 10000)
        
        assert result['limit_exceeded'] is False
        assert result['current_exposure_pct'] == 0.0
    
    def test_invalid_capital_raises_error(self):
        """Test that invalid capital raises ValueError."""
        with pytest.raises(ValueError, match="Capital must be positive"):
            self.rm.check_exposure_limits([], 0)


class TestCircuitBreaker:
    """Test circuit breaker for consecutive losses."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rm = RiskManager(circuit_breaker_losses=5)
    
    def test_circuit_breaker_not_triggered(self):
        """Test that circuit breaker not triggered with few losses."""
        for i in range(3):
            result = self.rm.circuit_breaker('loss')
        
        assert result['triggered'] is False
        assert result['consecutive_losses'] == 3
        assert result['threshold'] == 5
    
    def test_circuit_breaker_triggered(self):
        """Test that circuit breaker triggered after threshold losses."""
        for i in range(5):
            result = self.rm.circuit_breaker('loss')
        
        assert result['triggered'] is True
        assert result['consecutive_losses'] == 5
    
    def test_circuit_breaker_reset_on_win(self):
        """Test that circuit breaker resets on winning trade."""
        # 3 losses
        for i in range(3):
            self.rm.circuit_breaker('loss')
        
        # 1 win - should reset
        result = self.rm.circuit_breaker('win')
        
        assert result['triggered'] is False
        assert result['consecutive_losses'] == 0
    
    def test_circuit_breaker_continues_after_trigger(self):
        """Test that circuit breaker stays triggered with more losses."""
        for i in range(7):
            result = self.rm.circuit_breaker('loss')
        
        assert result['triggered'] is True
        assert result['consecutive_losses'] == 7
    
    def test_circuit_breaker_manual_reset(self):
        """Test manual reset of circuit breaker."""
        # Trigger circuit breaker
        for i in range(5):
            self.rm.circuit_breaker('loss')
        
        # Manual reset
        self.rm.reset_circuit_breaker()
        
        # Check status
        result = self.rm.circuit_breaker('loss')
        assert result['consecutive_losses'] == 1
        assert result['triggered'] is False
    
    def test_circuit_breaker_alternating_results(self):
        """Test circuit breaker with alternating wins and losses."""
        # Loss, win, loss, win, loss
        self.rm.circuit_breaker('loss')
        self.rm.circuit_breaker('win')
        self.rm.circuit_breaker('loss')
        self.rm.circuit_breaker('win')
        result = self.rm.circuit_breaker('loss')
        
        # Should never trigger because wins reset the counter
        assert result['triggered'] is False
        assert result['consecutive_losses'] == 1


class TestRiskManagerInitialization:
    """Test RiskManager initialization with custom limits."""
    
    def test_default_initialization(self):
        """Test default risk manager initialization."""
        rm = RiskManager()
        
        assert rm.daily_loss_limit == 0.05
        assert rm.per_trade_loss_limit == 0.02
        assert rm.max_exposure == 0.5
        assert rm.circuit_breaker_losses == 5
        assert rm.consecutive_losses == 0
    
    def test_custom_initialization(self):
        """Test risk manager with custom limits."""
        rm = RiskManager(
            daily_loss_limit=0.03,
            per_trade_loss_limit=0.01,
            max_exposure=0.3,
            circuit_breaker_losses=3
        )
        
        assert rm.daily_loss_limit == 0.03
        assert rm.per_trade_loss_limit == 0.01
        assert rm.max_exposure == 0.3
        assert rm.circuit_breaker_losses == 3
    
    def test_conservative_limits(self):
        """Test risk manager with conservative limits."""
        rm = RiskManager(
            daily_loss_limit=0.02,  # 2% daily
            per_trade_loss_limit=0.005,  # 0.5% per trade
            max_exposure=0.25,  # 25% exposure
            circuit_breaker_losses=3  # 3 losses
        )
        
        # Test daily limit
        result = rm.check_daily_loss_limit(-250, 10000)  # 2.5% loss
        assert result['limit_reached'] is True
        
        # Test per-trade limit
        result = rm.check_per_trade_loss_limit(-60, 10000)  # 0.6% loss
        assert result['limit_reached'] is True
        
        # Test exposure limit
        result = rm.check_exposure_limits([{'size': 1, 'price': 3000}], 10000)  # 30%
        assert result['limit_exceeded'] is True
    
    def test_aggressive_limits(self):
        """Test risk manager with aggressive limits."""
        rm = RiskManager(
            daily_loss_limit=0.10,  # 10% daily
            per_trade_loss_limit=0.05,  # 5% per trade
            max_exposure=0.8,  # 80% exposure
            circuit_breaker_losses=10  # 10 losses
        )
        
        # Test daily limit
        result = rm.check_daily_loss_limit(-800, 10000)  # 8% loss
        assert result['limit_reached'] is False
        
        # Test per-trade limit
        result = rm.check_per_trade_loss_limit(-400, 10000)  # 4% loss
        assert result['limit_reached'] is False
        
        # Test exposure limit
        result = rm.check_exposure_limits([{'size': 1, 'price': 7000}], 10000)  # 70%
        assert result['limit_exceeded'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
