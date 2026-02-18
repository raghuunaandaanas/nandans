"""
Unit tests for GammaDetector class.
Tests gamma level calculation and strike prediction.
"""

import pytest
from src.main import GammaDetector, LevelCalculator


class TestGammaLevelCalculation:
    """Test gamma level calculation."""
    
    def test_calculate_gamma_levels(self):
        """Test gamma level calculation for a strike."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        levels = detector.calculate_gamma_levels(
            strike=50000.0,
            base_price=50000.0,
            expiry_days=7
        )
        
        assert 'strike' in levels
        assert 'gamma_factor' in levels
        assert 'potential_multiplier' in levels
        assert levels['strike'] == 50000.0
    
    def test_atm_has_highest_gamma(self):
        """Test ATM options have highest gamma factor."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        atm_levels = detector.calculate_gamma_levels(50000.0, 50000.0, 7)
        otm_levels = detector.calculate_gamma_levels(52000.0, 50000.0, 7)
        
        assert atm_levels['gamma_factor'] > otm_levels['gamma_factor']
    
    def test_time_decay_factor(self):
        """Test time decay factor decreases with expiry."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        near_expiry = detector.calculate_gamma_levels(50000.0, 50000.0, 1)
        far_expiry = detector.calculate_gamma_levels(50000.0, 50000.0, 30)
        
        assert near_expiry['time_decay_factor'] < far_expiry['time_decay_factor']


class TestGammaStrikePrediction:
    """Test gamma strike prediction."""
    
    def test_predict_gamma_strikes(self):
        """Test predicting gamma strikes."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        strikes = [49000.0, 49500.0, 50000.0, 50500.0, 51000.0]
        
        predictions = detector.predict_gamma_strikes(
            instrument='BTCUSD',
            current_price=50000.0,
            available_strikes=strikes,
            expiry_date='2026-02-25'
        )
        
        assert isinstance(predictions, list)
        for pred in predictions:
            assert 'strike' in pred
            assert 'potential' in pred
            assert 'gamma_levels' in pred
    
    def test_predictions_sorted_by_potential(self):
        """Test predictions sorted by potential multiplier."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        strikes = [49000.0, 49500.0, 50000.0, 50500.0, 51000.0]
        
        predictions = detector.predict_gamma_strikes(
            instrument='BTCUSD',
            current_price=50000.0,
            available_strikes=strikes,
            expiry_date='2026-02-25'
        )
        
        if len(predictions) > 1:
            for i in range(len(predictions) - 1):
                assert (predictions[i]['gamma_levels']['potential_multiplier'] >= 
                       predictions[i+1]['gamma_levels']['potential_multiplier'])
    
    def test_filters_far_otm_strikes(self):
        """Test filters out far OTM strikes."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        strikes = [40000.0, 50000.0, 60000.0]  # Far OTM strikes
        
        predictions = detector.predict_gamma_strikes(
            instrument='BTCUSD',
            current_price=50000.0,
            available_strikes=strikes,
            expiry_date='2026-02-25'
        )
        
        # Should filter out strikes > 5% from ATM
        for pred in predictions:
            distance_pct = abs(pred['strike'] - 50000.0) / 50000.0 * 100
            assert distance_pct <= 5


class TestGammaMonitoring:
    """Test gamma opportunity monitoring."""
    
    def test_monitor_gamma_opportunities(self):
        """Test monitoring gamma opportunities."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        stocks = ['STOCK1', 'STOCK2']
        market_data = {
            'STOCK1': {
                'current_price': 100.0,
                'strikes': [95.0, 100.0, 105.0],
                'expiry_date': '2026-02-25'
            }
        }
        
        opportunities = detector.monitor_gamma_opportunities(stocks, market_data)
        
        assert isinstance(opportunities, list)
    
    def test_limits_to_10_stocks(self):
        """Test monitoring limits to 10 stocks."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        stocks = [f'STOCK{i}' for i in range(20)]
        market_data = {}
        
        detector.monitor_gamma_opportunities(stocks, market_data)
        
        assert len(detector.monitored_stocks) == 10


class TestGammaAlerts:
    """Test gamma opportunity alerts."""
    
    def test_generate_gamma_alert(self):
        """Test generating gamma alert."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        opportunity = {
            'instrument': 'BTCUSD',
            'strike': 50000.0,
            'potential': 'HIGH',
            'entry_price': 1.0,
            'target_price': 100.0,
            'risk_reward': 100.0
        }
        
        alert = detector.alert_gamma_opportunity(opportunity)
        
        assert alert['type'] == 'GAMMA_OPPORTUNITY'
        assert alert['instrument'] == 'BTCUSD'
        assert 'message' in alert
        assert 'timestamp' in alert
    
    def test_alert_includes_risk_reward(self):
        """Test alert includes risk/reward ratio."""
        calc = LevelCalculator()
        detector = GammaDetector(calc)
        
        opportunity = {
            'instrument': 'BTCUSD',
            'strike': 50000.0,
            'potential': 'HIGH',
            'entry_price': 1.0,
            'target_price': 100.0,
            'risk_reward': 100.0
        }
        
        alert = detector.alert_gamma_opportunity(opportunity)
        
        assert alert['risk_reward'] == 100.0
