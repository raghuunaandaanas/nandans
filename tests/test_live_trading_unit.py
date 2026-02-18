"""
Unit tests for Live Trading Engine

Tests cover:
- Live trading enablement with safety checks
- API credential verification
- Balance verification
- Emergency stop functionality
- Status tracking
"""

import pytest
from src.main import LiveTradingEngine, RiskManager
from unittest.mock import Mock


class TestLiveTradingInitialization:
    """Test live trading initialization."""
    
    def test_initialization(self):
        """Test initialization."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        assert engine.is_live is False
        assert engine.live_enabled_at is None
        assert engine.emergency_stop_triggered is False


class TestEnableLiveTrading:
    """Test enabling live trading."""
    
    def test_enable_without_confirmation_fails(self):
        """Test that enabling without confirmation fails."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        result = engine.enable_live_trading(user_confirmation=False)
        
        assert result['success'] is False
        assert 'confirmation required' in result['message'].lower()
        assert result['requires_confirmation'] is True
        assert engine.is_live is False
        
    def test_enable_with_confirmation_succeeds(self):
        """Test that enabling with confirmation succeeds."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        result = engine.enable_live_trading(user_confirmation=True)
        
        assert result['success'] is True
        assert 'REAL MONEY' in result['message']
        assert engine.is_live is True
        assert engine.live_enabled_at is not None
        
    def test_enable_when_already_enabled(self):
        """Test enabling when already enabled."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        result = engine.enable_live_trading(user_confirmation=True)
        
        assert result['success'] is False
        assert 'already enabled' in result['message'].lower()
        
    def test_enable_without_api_client_fails(self):
        """Test that enabling without API client fails."""
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(None, db, risk_manager)
        
        with pytest.raises(ValueError, match="API credentials verification failed"):
            engine.enable_live_trading(user_confirmation=True)
            
    def test_enable_with_invalid_risk_limits_fails(self):
        """Test that enabling with invalid risk limits fails."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager(daily_loss_limit=0)  # Invalid
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        with pytest.raises(ValueError, match="Risk limits not properly configured"):
            engine.enable_live_trading(user_confirmation=True)


class TestDisableLiveTrading:
    """Test disabling live trading."""
    
    def test_disable_when_enabled(self):
        """Test disabling when enabled."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        result = engine.disable_live_trading()
        
        assert result['success'] is True
        assert engine.is_live is False
        assert 'was_active_for' in result
        
    def test_disable_when_not_enabled(self):
        """Test disabling when not enabled."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        result = engine.disable_live_trading()
        
        assert result['success'] is False
        assert 'not enabled' in result['message'].lower()


class TestEmergencyStop:
    """Test emergency stop functionality."""
    
    def test_emergency_stop_when_live(self):
        """Test emergency stop when live trading is active."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        result = engine.emergency_stop()
        
        assert result['success'] is True
        assert 'EMERGENCY STOP' in result['message']
        assert engine.is_live is False
        assert engine.emergency_stop_triggered is True
        assert 'timestamp' in result
        
    def test_emergency_stop_when_not_live(self):
        """Test emergency stop when not live."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        result = engine.emergency_stop()
        
        assert result['success'] is False
        assert 'not active' in result['message'].lower()
        
    def test_emergency_stop_prevents_trading(self):
        """Test that emergency stop prevents further trading."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        engine.emergency_stop()
        
        can_place = engine.can_place_order()
        assert can_place['can_place'] is False
        assert 'Emergency stop' in can_place['reason']


class TestLiveStatus:
    """Test live trading status."""
    
    def test_status_when_not_enabled(self):
        """Test status when not enabled."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        status = engine.get_live_status()
        
        assert status['is_live'] is False
        assert status['enabled_at'] is None
        assert status['emergency_stop_triggered'] is False
        assert status['uptime'] == 0
        
    def test_status_when_enabled(self):
        """Test status when enabled."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        status = engine.get_live_status()
        
        assert status['is_live'] is True
        assert status['enabled_at'] is not None
        assert status['uptime'] >= 0
        
    def test_status_after_emergency_stop(self):
        """Test status after emergency stop."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        engine.emergency_stop()
        status = engine.get_live_status()
        
        assert status['is_live'] is False
        assert status['emergency_stop_triggered'] is True


class TestOrderPlacement:
    """Test order placement checks."""
    
    def test_can_place_order_when_live(self):
        """Test that orders can be placed when live."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        result = engine.can_place_order()
        
        assert result['can_place'] is True
        assert 'active' in result['reason'].lower()
        
    def test_cannot_place_order_when_not_live(self):
        """Test that orders cannot be placed when not live."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        result = engine.can_place_order()
        
        assert result['can_place'] is False
        assert 'not enabled' in result['reason'].lower()
        
    def test_cannot_place_order_after_emergency_stop(self):
        """Test that orders cannot be placed after emergency stop."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        engine.enable_live_trading(user_confirmation=True)
        engine.emergency_stop()
        result = engine.can_place_order()
        
        assert result['can_place'] is False
        assert 'Emergency stop' in result['reason']


class TestSafetyChecks:
    """Test safety check methods."""
    
    def test_verify_api_credentials(self):
        """Test API credential verification."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        assert engine._verify_api_credentials() is True
        
    def test_verify_api_credentials_fails_without_client(self):
        """Test API verification fails without client."""
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(None, db, risk_manager)
        
        assert engine._verify_api_credentials() is False
        
    def test_verify_sufficient_balance(self):
        """Test balance verification."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        assert engine._verify_sufficient_balance() is True
        
    def test_verify_risk_limits(self):
        """Test risk limits verification."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager()
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        assert engine._verify_risk_limits() is True
        
    def test_verify_risk_limits_fails_with_zero_limits(self):
        """Test risk limits verification fails with zero limits."""
        api_client = Mock()
        db = Mock()
        risk_manager = RiskManager(daily_loss_limit=0)
        engine = LiveTradingEngine(api_client, db, risk_manager)
        
        assert engine._verify_risk_limits() is False
