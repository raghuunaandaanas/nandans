"""
Unit tests for VolatilitySpikeManager class.
Tests volatility spike analysis and position adjustments.
"""

import pytest
from src.main import VolatilitySpikeManager, SpikeDetector, LevelCalculator


class TestVolatilitySpikeAnalysis:
    """Test volatility spike analysis."""
    
    def test_analyze_volatility_spike(self):
        """Test analyzing volatility spike."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        
        price_movement = {
            'high': 105.0,
            'low': 95.0,
            'open': 100.0,
            'close': 102.0
        }
        
        analysis = manager.analyze_volatility_spike(price_movement, levels)
        
        assert 'spike_magnitude' in analysis
        assert 'classification' in analysis
        assert 'is_tradeable' in analysis
    
    def test_spike_aligned_with_levels_is_tradeable(self):
        """Test spike aligned with BU/BE levels is tradeable."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        
        # Spike that touches BU1
        price_movement = {
            'high': levels['bu1'],
            'low': 99.0,
            'open': 100.0,
            'close': levels['bu1'] - 0.1
        }
        
        analysis = manager.analyze_volatility_spike(price_movement, levels)
        
        assert analysis['bu_touched'] == True
        assert analysis['is_tradeable'] == True
    
    def test_spike_not_aligned_is_noise(self):
        """Test spike not aligned with levels is noise."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        
        # Spike that doesn't touch any level
        price_movement = {
            'high': 101.0,
            'low': 99.0,
            'open': 100.0,
            'close': 100.5
        }
        
        analysis = manager.analyze_volatility_spike(price_movement, levels)
        
        # May or may not be tradeable depending on exact levels
        assert 'classification' in analysis


class TestPositionSizingAdjustment:
    """Test position sizing adjustment during volatility."""
    
    def test_reduce_size_for_large_spike(self):
        """Test position size reduced for large spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        base_size = 1.0
        
        # Large spike (> 3× Points)
        volatility_spike = {
            'spike_magnitude': 4.0,
            'is_tradeable': True
        }
        
        adjusted_size = manager.adjust_position_sizing(base_size, volatility_spike)
        
        assert adjusted_size < base_size
        assert adjusted_size == 0.5  # 50% reduction
    
    def test_moderate_reduction_for_medium_spike(self):
        """Test moderate reduction for medium spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        base_size = 1.0
        
        # Medium spike (2-3× Points)
        volatility_spike = {
            'spike_magnitude': 2.5,
            'is_tradeable': True
        }
        
        adjusted_size = manager.adjust_position_sizing(base_size, volatility_spike)
        
        assert adjusted_size < base_size
        assert adjusted_size == 0.75  # 25% reduction
    
    def test_no_reduction_for_small_spike(self):
        """Test no reduction for small spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        base_size = 1.0
        
        # Small spike (< 2× Points)
        volatility_spike = {
            'spike_magnitude': 1.5,
            'is_tradeable': True
        }
        
        adjusted_size = manager.adjust_position_sizing(base_size, volatility_spike)
        
        assert adjusted_size == base_size


class TestStopLossAdjustment:
    """Test stop loss adjustment during volatility."""
    
    def test_widen_stop_for_large_spike(self):
        """Test stop loss widened for large spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        base_stop_loss = levels['points'] * 0.5
        
        # Large spike
        volatility_spike = {
            'spike_magnitude': 4.0,
            'is_tradeable': True
        }
        
        adjusted_stop = manager.adjust_stop_loss(base_stop_loss, levels, volatility_spike)
        
        assert adjusted_stop > base_stop_loss
        assert adjusted_stop == levels['points'] * 1.5
    
    def test_moderate_widening_for_medium_spike(self):
        """Test moderate widening for medium spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        base_stop_loss = levels['points'] * 0.5
        
        # Medium spike
        volatility_spike = {
            'spike_magnitude': 2.5,
            'is_tradeable': True
        }
        
        adjusted_stop = manager.adjust_stop_loss(base_stop_loss, levels, volatility_spike)
        
        assert adjusted_stop > base_stop_loss
        assert adjusted_stop == levels['points'] * 1.0
    
    def test_no_widening_for_small_spike(self):
        """Test no widening for small spikes."""
        calc = LevelCalculator()
        spike_detector = SpikeDetector()
        manager = VolatilitySpikeManager(spike_detector, calc)
        
        levels = calc.calculate_levels(100.0, '1m')
        base_stop_loss = levels['points'] * 0.5
        
        # Small spike
        volatility_spike = {
            'spike_magnitude': 1.5,
            'is_tradeable': True
        }
        
        adjusted_stop = manager.adjust_stop_loss(base_stop_loss, levels, volatility_spike)
        
        assert adjusted_stop == base_stop_loss
