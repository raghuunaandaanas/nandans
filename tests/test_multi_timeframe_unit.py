"""
Unit tests for Multi-Timeframe Coordinator.
Tests timeframe alignment, weighted signals, and entry recommendations.
"""

import pytest
from src.main import MultiTimeframeCoordinator, LevelCalculator


class TestMultiTimeframeCoordinator:
    """Test Multi-Timeframe Coordinator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.level_calculator = LevelCalculator()
        self.mtf_coordinator = MultiTimeframeCoordinator(self.level_calculator)
    
    def test_calculate_all_timeframe_levels(self):
        """Test calculating levels for all timeframes."""
        base_prices = {
            '1m': 50000.00,
            '5m': 50100.00,
            '15m': 50200.00
        }
        
        result = self.mtf_coordinator.calculate_all_timeframe_levels(base_prices)
        
        assert '1m' in result
        assert '5m' in result
        assert '15m' in result
        assert 'bu1' in result['1m']
        assert 'be1' in result['1m']
    
    def test_check_timeframe_alignment_all_bullish(self):
        """Test alignment when all timeframes are bullish."""
        signals_1m = {'signal': 'bullish'}
        signals_5m = {'signal': 'bullish'}
        signals_15m = {'signal': 'bullish'}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['aligned'] is True
        assert result['direction'] == 'bullish'
        assert result['confidence'] == 0.95
        assert result['position_multiplier'] == 1.5
        assert 'All timeframes bullish' in result['reason']
    
    def test_check_timeframe_alignment_all_bearish(self):
        """Test alignment when all timeframes are bearish."""
        signals_1m = {'signal': 'bearish'}
        signals_5m = {'signal': 'bearish'}
        signals_15m = {'signal': 'bearish'}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['aligned'] is True
        assert result['direction'] == 'bearish'
        assert result['confidence'] == 0.95
        assert result['position_multiplier'] == 1.5
        assert 'All timeframes bearish' in result['reason']
    
    def test_check_timeframe_alignment_partial_bullish(self):
        """Test alignment with 2 out of 3 bullish."""
        signals_1m = {'signal': 'bullish'}
        signals_5m = {'signal': 'bullish'}
        signals_15m = {'signal': 'neutral'}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['aligned'] is True
        assert result['direction'] == 'bullish'
        assert result['confidence'] == 0.75
        assert result['position_multiplier'] == 1.0
    
    def test_check_timeframe_alignment_partial_bearish(self):
        """Test alignment with 2 out of 3 bearish."""
        signals_1m = {'signal': 'bearish'}
        signals_5m = {'signal': 'neutral'}
        signals_15m = {'signal': 'bearish'}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['aligned'] is True
        assert result['direction'] == 'bearish'
        assert result['confidence'] == 0.75
        assert result['position_multiplier'] == 1.0
    
    def test_check_timeframe_alignment_conflicting(self):
        """Test alignment with conflicting signals."""
        signals_1m = {'signal': 'bullish'}
        signals_5m = {'signal': 'bearish'}
        signals_15m = {'signal': 'neutral'}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['aligned'] is False
        assert result['direction'] == 'neutral'
        assert result['confidence'] == 0.3
        assert result['position_multiplier'] == 0.5
        assert 'conflicting' in result['reason']
    
    def test_get_weighted_signal_strong_bullish(self):
        """Test weighted signal with strong bullish bias."""
        signals_1m = {'signal': 'bullish'}
        signals_5m = {'signal': 'bullish'}
        signals_15m = {'signal': 'bullish'}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['signal'] == 'bullish'
        assert result['confidence'] == 1.0  # All weights sum to 1.0
        assert result['bullish_score'] == 1.0
        assert result['bearish_score'] == 0.0
    
    def test_get_weighted_signal_strong_bearish(self):
        """Test weighted signal with strong bearish bias."""
        signals_1m = {'signal': 'bearish'}
        signals_5m = {'signal': 'bearish'}
        signals_15m = {'signal': 'bearish'}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['signal'] == 'bearish'
        assert result['confidence'] == 1.0
        assert result['bullish_score'] == 0.0
        assert result['bearish_score'] == 1.0
    
    def test_get_weighted_signal_15m_dominant(self):
        """Test weighted signal with 15m timeframe dominant."""
        signals_1m = {'signal': 'neutral'}
        signals_5m = {'signal': 'neutral'}
        signals_15m = {'signal': 'bullish'}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['signal'] == 'bullish'
        assert result['confidence'] == 0.5  # 15m weight
        assert result['dominant_timeframe'] == '15m'
    
    def test_get_weighted_signal_mixed(self):
        """Test weighted signal with mixed signals."""
        signals_1m = {'signal': 'bullish'}
        signals_5m = {'signal': 'bearish'}
        signals_15m = {'signal': 'neutral'}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        # 1m bullish (0.2) vs 5m bearish (0.3)
        # bearish score (0.3) > bullish score (0.2), but need >= 0.5 for signal
        # So result should be neutral
        assert result['signal'] == 'neutral'
        assert result['bullish_score'] == 0.2
        assert result['bearish_score'] == 0.3
    
    def test_get_weighted_signal_neutral(self):
        """Test weighted signal with all neutral."""
        signals_1m = {'signal': 'neutral'}
        signals_5m = {'signal': 'neutral'}
        signals_15m = {'signal': 'neutral'}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        assert result['signal'] == 'neutral'
        assert result['confidence'] == 0.0
        assert result['bullish_score'] == 0.0
        assert result['bearish_score'] == 0.0
    
    def test_get_entry_recommendation_not_aligned(self):
        """Test entry recommendation when timeframes not aligned."""
        alignment = {
            'aligned': False,
            'direction': 'neutral'
        }
        
        result = self.mtf_coordinator.get_entry_recommendation(
            current_price=50000.00,
            all_levels={},
            alignment=alignment
        )
        
        assert result['should_enter'] is False
        assert 'not aligned' in result['reason']
    
    def test_get_entry_recommendation_no_15m_levels(self):
        """Test entry recommendation without 15m levels."""
        alignment = {
            'aligned': True,
            'direction': 'bullish',
            'confidence': 0.95,
            'position_multiplier': 1.5
        }
        
        all_levels = {
            '1m': {'BU1': 50130.55, 'Base': 50000.00, 'Points': 130.55}
        }
        
        result = self.mtf_coordinator.get_entry_recommendation(
            current_price=50130.00,
            all_levels=all_levels,
            alignment=alignment
        )
        
        assert result['should_enter'] is False
        assert '15m levels not available' in result['reason']
    
    def test_get_entry_recommendation_bullish_at_bu1(self):
        """Test entry recommendation for bullish signal at BU1."""
        alignment = {
            'aligned': True,
            'direction': 'bullish',
            'confidence': 0.95,
            'position_multiplier': 1.5
        }
        
        all_levels = {
            '1m': {
                'base': 50000.00,
                'points': 130.55,
                'bu1': 50130.55,
                'bu2': 50261.10,
                'bu3': 50391.65,
                'bu4': 50522.20,
                'bu5': 50652.75
            },
            '15m': {
                'base': 50000.00,
                'points': 130.55,
                'bu1': 50130.55
            }
        }
        
        result = self.mtf_coordinator.get_entry_recommendation(
            current_price=50130.00,  # Near BU1
            all_levels=all_levels,
            alignment=alignment
        )
        
        assert result['should_enter'] is True
        assert result['direction'] == 'long'
        assert result['position_multiplier'] == 1.5
        assert len(result['targets']) == 4
    
    def test_get_entry_recommendation_bearish_at_be1(self):
        """Test entry recommendation for bearish signal at BE1."""
        alignment = {
            'aligned': True,
            'direction': 'bearish',
            'confidence': 0.95,
            'position_multiplier': 1.5
        }
        
        all_levels = {
            '1m': {
                'base': 50000.00,
                'points': 130.55,
                'be1': 49869.45,
                'be2': 49738.90,
                'be3': 49608.35,
                'be4': 49477.80,
                'be5': 49347.25
            },
            '15m': {
                'base': 50000.00,
                'points': 130.55,
                'be1': 49869.45
            }
        }
        
        result = self.mtf_coordinator.get_entry_recommendation(
            current_price=49870.00,  # Near BE1
            all_levels=all_levels,
            alignment=alignment
        )
        
        assert result['should_enter'] is True
        assert result['direction'] == 'short'
        assert result['position_multiplier'] == 1.5
        assert len(result['targets']) == 4
    
    def test_get_entry_recommendation_waiting_for_entry(self):
        """Test entry recommendation waiting for precise entry."""
        alignment = {
            'aligned': True,
            'direction': 'bullish',
            'confidence': 0.95,
            'position_multiplier': 1.5
        }
        
        all_levels = {
            '1m': {
                'base': 50000.00,
                'points': 130.55,
                'bu1': 50130.55,
                'bu2': 50261.10,
                'bu3': 50391.65,
                'bu4': 50522.20,
                'bu5': 50652.75
            },
            '15m': {
                'base': 50000.00,
                'points': 130.55,
                'bu1': 50130.55
            }
        }
        
        result = self.mtf_coordinator.get_entry_recommendation(
            current_price=49500.00,  # Far from bu1 (50130.55) - more than 1% away
            all_levels=all_levels,
            alignment=alignment
        )
        
        assert result['should_enter'] is False
        assert 'Waiting for precise entry' in result['reason']
    
    def test_timeframe_weights(self):
        """Test that timeframe weights are correctly set."""
        assert self.mtf_coordinator.timeframe_weights['15m'] == 0.5
        assert self.mtf_coordinator.timeframe_weights['5m'] == 0.3
        assert self.mtf_coordinator.timeframe_weights['1m'] == 0.2
        assert sum(self.mtf_coordinator.timeframe_weights.values()) == 1.0
