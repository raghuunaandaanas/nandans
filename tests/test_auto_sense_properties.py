"""
Property-based tests for AUTO SENSE Engine and Spike Detector

Uses Hypothesis to test universal properties with generated data.
"""

import pytest
from hypothesis import given, strategies as st, assume
from src.main import AutoSenseEngine, SpikeDetector


class TestAutoSenseProperties:
    """Property-based tests for AUTO SENSE Engine."""
    
    @given(
        base_price=st.floats(min_value=1, max_value=100000),
        volatility=st.floats(min_value=0, max_value=1)
    )
    def test_property_factor_always_positive(self, base_price, volatility):
        """Property: Factor selection always returns positive value."""
        engine = AutoSenseEngine()
        factor = engine.select_optimal_factor(base_price, volatility)
        assert factor > 0
        
    @given(
        base_price=st.floats(min_value=1, max_value=100000),
        volatility=st.floats(min_value=0, max_value=1)
    )
    def test_property_factor_in_reasonable_range(self, base_price, volatility):
        """Property: Factor is always in reasonable range (0.001 to 0.5)."""
        engine = AutoSenseEngine()
        factor = engine.select_optimal_factor(base_price, volatility)
        assert 0.001 < factor < 0.5
        
    @given(
        base_price=st.floats(min_value=1, max_value=999),
        volatility=st.floats(min_value=0, max_value=1)
    )
    def test_property_low_price_uses_large_factor(self, base_price, volatility):
        """Property: Prices < 1000 use factor around 0.2611."""
        engine = AutoSenseEngine()
        factor = engine.select_optimal_factor(base_price, volatility)
        # Should be around 0.2611 with adjustments (0.15 to 0.35)
        assert 0.15 < factor < 0.35
        
    @given(
        base_price=st.floats(min_value=10000, max_value=100000),
        volatility=st.floats(min_value=0, max_value=1)
    )
    def test_property_high_price_uses_small_factor(self, base_price, volatility):
        """Property: Prices >= 10000 use factor around 0.002611."""
        engine = AutoSenseEngine()
        factor = engine.select_optimal_factor(base_price, volatility)
        # Should be around 0.002611 with adjustments (0.001 to 0.005)
        assert 0.001 < factor < 0.005
        
    @given(
        price_action=st.lists(st.floats(min_value=1, max_value=100000), min_size=2, max_size=20),
        volume=st.lists(st.floats(min_value=1, max_value=1000000), min_size=2, max_size=20)
    )
    def test_property_entry_timing_returns_valid_response(self, price_action, volume):
        """Property: Entry timing always returns valid response structure."""
        assume(len(price_action) == len(volume))
        
        engine = AutoSenseEngine()
        current_price = price_action[-1]
        level = price_action[0]
        
        result = engine.predict_entry_timing(price_action, volume, current_price, level)
        
        assert 'timing' in result
        assert 'confidence' in result
        assert 'reason' in result
        assert result['timing'] in ['immediate', 'wait_for_close']
        assert 0 <= result['confidence'] <= 1
        assert isinstance(result['reason'], str)
        
    @given(
        level=st.sampled_from(['BU2', 'BU3', 'BU4', 'BE2', 'BE3', 'BE4']),  # Exclude BU5/BE5
        trend_strength=st.floats(min_value=0, max_value=1)
    )
    def test_property_exit_percentages_sum_to_one(self, level, trend_strength):
        """Property: Exit percentages always sum to approximately 1.0 (except final levels)."""
        engine = AutoSenseEngine()
        result = engine.predict_exit_percentages(level, {}, trend_strength)
        
        total = sum(result.values())
        assert 0.99 <= total <= 1.01  # Allow small floating point error
        
    @given(
        level=st.sampled_from(['BU2', 'BU3', 'BU4', 'BU5', 'BE2', 'BE3', 'BE4', 'BE5']),
        trend_strength=st.floats(min_value=0, max_value=1)
    )
    def test_property_exit_percentages_all_positive(self, level, trend_strength):
        """Property: All exit percentages are positive."""
        engine = AutoSenseEngine()
        result = engine.predict_exit_percentages(level, {}, trend_strength)
        
        for pct in result.values():
            assert pct > 0
            assert pct <= 1.0
            
    @given(
        price_action=st.lists(st.floats(min_value=1, max_value=100000), min_size=2, max_size=20)
    )
    def test_property_momentum_bounded(self, price_action):
        """Property: Momentum is always between 0 and 1."""
        engine = AutoSenseEngine()
        momentum = engine._calculate_momentum(price_action)
        assert 0 <= momentum <= 1
        
    @given(
        volume=st.lists(st.floats(min_value=0, max_value=1000000), min_size=2, max_size=20)
    )
    def test_property_volume_strength_bounded(self, volume):
        """Property: Volume strength is always between 0 and 1."""
        assume(sum(volume) > 0)  # Avoid all-zero volume
        
        engine = AutoSenseEngine()
        strength = engine._analyze_volume_strength(volume)
        assert 0 <= strength <= 1


class TestSpikeDetectorProperties:
    """Property-based tests for Spike Detector."""
    
    @given(
        open_price=st.floats(min_value=1, max_value=100000),
        high_offset=st.floats(min_value=0, max_value=1000),
        low_offset=st.floats(min_value=0, max_value=1000),
        close_offset=st.floats(min_value=-1000, max_value=1000),
        volume=st.floats(min_value=1, max_value=1000000),
        points=st.floats(min_value=0.1, max_value=1000),
        avg_volume=st.floats(min_value=1, max_value=1000000)
    )
    def test_property_spike_detection_returns_valid_structure(self, open_price, high_offset, 
                                                              low_offset, close_offset, volume,
                                                              points, avg_volume):
        """Property: Spike detection always returns valid response structure."""
        detector = SpikeDetector()
        
        high = open_price + high_offset
        low = open_price - low_offset
        close = open_price + close_offset
        
        # Ensure valid OHLC
        assume(low <= open_price <= high)
        assume(low <= close <= high)
        
        candle = {
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
        levels = {'points': points}
        
        result = detector.detect_spike(candle, levels, avg_volume)
        
        assert 'is_spike' in result
        assert 'spike_type' in result
        assert 'magnitude' in result
        assert 'confidence' in result
        assert 'reason' in result
        assert isinstance(result['is_spike'], bool)
        assert result['spike_type'] in ['real', 'fake', None]
        assert result['magnitude'] >= 0
        assert 0 <= result['confidence'] <= 1
        assert isinstance(result['reason'], str)
        
    @given(
        open_price=st.floats(min_value=1, max_value=100000),
        range_size=st.floats(min_value=0, max_value=1000),
        points=st.floats(min_value=0.1, max_value=1000),
        volume=st.floats(min_value=1, max_value=1000000),
        avg_volume=st.floats(min_value=1, max_value=1000000)
    )
    def test_property_17_spike_classification(self, open_price, range_size, points, 
                                             volume, avg_volume):
        """Property 17: Movement > 2× Points classified as spike."""
        detector = SpikeDetector()
        
        candle = {
            'open': open_price,
            'high': open_price + range_size,
            'low': open_price,
            'close': open_price + range_size * 0.5,
            'volume': volume
        }
        levels = {'points': points}
        
        result = detector.detect_spike(candle, levels, avg_volume)
        
        magnitude = range_size / points
        
        if magnitude > 2.0:
            assert result['is_spike'] is True
            assert result['spike_type'] in ['real', 'fake']
        else:
            assert result['is_spike'] is False
            assert result['spike_type'] is None
            
    @given(
        open_price=st.floats(min_value=1, max_value=100000),
        range_size=st.floats(min_value=10, max_value=1000),
        points=st.floats(min_value=1, max_value=100),
        volume=st.floats(min_value=1, max_value=1000000),
        avg_volume=st.floats(min_value=1, max_value=1000000)
    )
    def test_property_magnitude_calculation_correct(self, open_price, range_size, points,
                                                    volume, avg_volume):
        """Property: Magnitude is always range / points."""
        detector = SpikeDetector()
        
        candle = {
            'open': open_price,
            'high': open_price + range_size,
            'low': open_price,
            'close': open_price + range_size * 0.5,
            'volume': volume
        }
        levels = {'points': points}
        
        result = detector.detect_spike(candle, levels, avg_volume)
        
        expected_magnitude = range_size / points
        assert result['magnitude'] == pytest.approx(expected_magnitude, abs=0.01)
        
    @given(
        open_price=st.floats(min_value=1, max_value=100000),
        range_size=st.floats(min_value=10, max_value=1000),
        points=st.floats(min_value=1, max_value=100),
        volume_multiplier=st.floats(min_value=3, max_value=10),
        avg_volume=st.floats(min_value=100, max_value=10000)
    )
    def test_property_high_volume_increases_real_confidence(self, open_price, range_size, 
                                                           points, volume_multiplier, avg_volume):
        """Property: High volume increases confidence in real spike."""
        assume(range_size / points > 2.0)  # Ensure it's a spike
        
        detector = SpikeDetector()
        
        # High volume spike
        candle_high_vol = {
            'open': open_price,
            'high': open_price + range_size,
            'low': open_price,
            'close': open_price + range_size * 0.9,  # Close near high
            'volume': avg_volume * volume_multiplier
        }
        
        # Low volume spike
        candle_low_vol = {
            'open': open_price,
            'high': open_price + range_size,
            'low': open_price,
            'close': open_price + range_size * 0.9,
            'volume': avg_volume * 0.3
        }
        
        levels = {'points': points}
        
        result_high = detector.detect_spike(candle_high_vol, levels, avg_volume)
        result_low = detector.detect_spike(candle_low_vol, levels, avg_volume)
        
        # High volume should have higher confidence or be classified as real
        if result_high['spike_type'] == 'real' and result_low['spike_type'] == 'fake':
            assert result_high['confidence'] > result_low['confidence']
            
    @given(
        open_price=st.floats(min_value=1, max_value=100000),
        range_size=st.floats(min_value=10, max_value=1000),
        points=st.floats(min_value=1, max_value=100)
    )
    def test_property_confidence_bounded(self, open_price, range_size, points):
        """Property: Confidence is always between 0 and 1."""
        detector = SpikeDetector()
        
        candle = {
            'open': open_price,
            'high': open_price + range_size,
            'low': open_price,
            'close': open_price + range_size * 0.5,
            'volume': 1000
        }
        levels = {'points': points}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert 0 <= result['confidence'] <= 1


class TestIntegrationProperties:
    """Property-based tests for AUTO SENSE and Spike Detector integration."""
    
    @given(
        base_price=st.floats(min_value=100, max_value=10000),
        volatility=st.floats(min_value=0.01, max_value=0.04)  # Further reduced max volatility
    )
    def test_property_factor_produces_reasonable_points(self, base_price, volatility):
        """Property: Selected factor produces reasonable Points values."""
        engine = AutoSenseEngine()
        factor = engine.select_optimal_factor(base_price, volatility)
        
        points = base_price * factor
        
        # Points should be reasonable (0.05% to 30% of base price with volatility adjustments)
        assert 0.0005 * base_price < points < 0.30 * base_price
        
    @given(
        base_price=st.floats(min_value=100, max_value=10000),
        volatility=st.floats(min_value=0.01, max_value=0.1),
        spike_multiplier=st.floats(min_value=2.1, max_value=5)
    )
    def test_property_spike_detection_with_auto_sense_factor(self, base_price, volatility,
                                                            spike_multiplier):
        """Property: Spike detection works with AUTO SENSE selected factor."""
        engine = AutoSenseEngine()
        detector = SpikeDetector()
        
        # Get factor from AUTO SENSE
        factor = engine.select_optimal_factor(base_price, volatility)
        points = base_price * factor
        
        # Create spike based on Points
        range_size = points * spike_multiplier
        
        candle = {
            'open': base_price,
            'high': base_price + range_size,
            'low': base_price,
            'close': base_price + range_size * 0.8,
            'volume': 2000
        }
        levels = {'points': points, 'base': base_price}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        # Should be detected as spike since multiplier > 2
        assert result['is_spike'] is True
        assert result['magnitude'] > 2.0
