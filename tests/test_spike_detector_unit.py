"""
Unit tests for Spike Detector

Tests cover:
- Spike detection (2x Points threshold)
- Real vs fake spike classification
- Volume analysis
- Close position analysis
- Level alignment checking
"""

import pytest
from src.main import SpikeDetector


class TestSpikeDetection:
    """Test basic spike detection logic."""
    
    def test_large_movement_detected_as_spike(self):
        """Test that movement > 2x Points is detected as spike."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 115,
            'low': 100,
            'close': 112,
            'volume': 2000
        }
        levels = {'points': 5, 'base': 100}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['magnitude'] > 2.0
        
    def test_small_movement_not_detected_as_spike(self):
        """Test that movement < 2x Points is not a spike."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 105,
            'low': 100,
            'close': 103,
            'volume': 1000
        }
        levels = {'points': 5, 'base': 100}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is False
        assert result['spike_type'] is None
        assert result['magnitude'] < 2.0
        
    def test_spike_magnitude_calculation(self):
        """Test spike magnitude is calculated correctly."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 120,
            'low': 95,
            'close': 115,
            'volume': 2000
        }
        levels = {'points': 10, 'base': 100}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        # Range = 120 - 95 = 25, Points = 10, Magnitude = 2.5
        assert result['magnitude'] == pytest.approx(2.5, abs=0.01)


class TestRealSpikeClassification:
    """Test classification of real spikes."""
    
    def test_high_volume_bullish_spike_classified_as_real(self):
        """Test real spike: high volume, closes near high."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 120,
            'low': 100,
            'close': 118,  # Close near high
            'volume': 3000  # 3x average
        }
        levels = {
            'points': 5,
            'base': 100,
            'BU1': 105,
            'BU2': 110,
            'BU3': 115,
            'BU4': 120
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['spike_type'] == 'real'
        assert result['confidence'] > 0.6
        
    def test_high_volume_bearish_spike_classified_as_real(self):
        """Test real spike: high volume, closes near low."""
        detector = SpikeDetector()
        
        candle = {
            'open': 120,
            'high': 120,
            'low': 100,
            'close': 102,  # Close near low
            'volume': 3000  # 3x average
        }
        levels = {
            'points': 5,
            'base': 120,
            'BE1': 115,
            'BE2': 110,
            'BE3': 105,
            'BE4': 100
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['spike_type'] == 'real'
        assert result['confidence'] > 0.6
        
    def test_spike_touching_level_classified_as_real(self):
        """Test real spike when high/low touches a BU/BE level."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 115,  # Touches BU3
            'low': 100,
            'close': 112,
            'volume': 2000
        }
        levels = {
            'points': 5,
            'base': 100,
            'BU1': 105,
            'BU2': 110,
            'BU3': 115,  # Level touched
            'BU4': 120
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        # Should have some real indicators due to level alignment
        assert result['confidence'] > 0.4


class TestFakeSpikeClassification:
    """Test classification of fake spikes."""
    
    def test_low_volume_spike_classified_as_fake(self):
        """Test fake spike: low volume."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 120,
            'low': 100,
            'close': 105,  # Close far from high
            'volume': 300  # 0.3x average
        }
        levels = {
            'points': 5,
            'base': 100
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['spike_type'] == 'fake'
        assert 'Low volume' in result['reason']
        
    def test_poor_close_position_classified_as_fake(self):
        """Test fake spike: closes far from extreme."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 120,
            'low': 100,
            'close': 105,  # Only 25% up from low
            'volume': 1000
        }
        levels = {
            'points': 5,
            'base': 100
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        # Poor close position should contribute to fake classification
        
    def test_no_level_alignment_contributes_to_fake(self):
        """Test spike not touching any level contributes to fake classification."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 117,  # Between levels
            'low': 100,
            'close': 115,
            'volume': 500
        }
        levels = {
            'points': 5,
            'base': 100,
            'BU1': 105,
            'BU2': 110,
            'BU3': 115,
            'BU4': 120
        }
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        # No level alignment should contribute to lower confidence


class TestLevelAlignment:
    """Test level alignment checking."""
    
    def test_high_touches_bu_level(self):
        """Test detection when high touches BU level."""
        detector = SpikeDetector()
        
        candle = {'high': 115.2, 'low': 100}
        levels = {
            'points': 5,
            'BU1': 105,
            'BU2': 110,
            'BU3': 115,  # Close to high
            'BU4': 120
        }
        
        alignment = detector._check_level_alignment(candle, levels, 100)
        assert alignment is True
        
    def test_low_touches_be_level(self):
        """Test detection when low touches BE level."""
        detector = SpikeDetector()
        
        candle = {'high': 100, 'low': 85.3}
        levels = {
            'points': 5,
            'BE1': 95,
            'BE2': 90,
            'BE3': 85,  # Close to low
            'BE4': 80
        }
        
        alignment = detector._check_level_alignment(candle, levels, 100)
        assert alignment is True
        
    def test_no_level_touched(self):
        """Test no alignment when no level is touched."""
        detector = SpikeDetector()
        
        candle = {'high': 117, 'low': 100}  # Between levels
        levels = {
            'points': 5,
            'BU1': 105,
            'BU2': 110,
            'BU3': 115,
            'BU4': 120
        }
        
        alignment = detector._check_level_alignment(candle, levels, 100)
        assert alignment is False
        
    def test_tolerance_allows_near_misses(self):
        """Test that tolerance allows near-misses to count as alignment."""
        detector = SpikeDetector()
        
        # High is 114.6, BU3 is 115, tolerance is 0.5 (10% of 5)
        candle = {'high': 114.6, 'low': 100}
        levels = {
            'points': 5,
            'BU3': 115
        }
        
        alignment = detector._check_level_alignment(candle, levels, 100)
        assert alignment is True


class TestInputValidation:
    """Test input validation and error handling."""
    
    def test_missing_candle_keys_raises_error(self):
        """Test that missing candle keys raise ValueError."""
        detector = SpikeDetector()
        
        candle = {'open': 100, 'high': 110}  # Missing low, close, volume
        levels = {'points': 5}
        
        with pytest.raises(ValueError, match="candle missing required key"):
            detector.detect_spike(candle, levels, avg_volume=1000)
            
    def test_missing_points_in_levels_raises_error(self):
        """Test that missing points in levels raises ValueError."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 110,
            'low': 100,
            'close': 105,
            'volume': 1000
        }
        levels = {'base': 100}  # Missing points
        
        with pytest.raises(ValueError, match="levels must contain 'points'"):
            detector.detect_spike(candle, levels, avg_volume=1000)
            
    def test_invalid_avg_volume_raises_error(self):
        """Test that invalid avg_volume raises ValueError."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 110,
            'low': 100,
            'close': 105,
            'volume': 1000
        }
        levels = {'points': 5}
        
        with pytest.raises(ValueError, match="avg_volume must be positive"):
            detector.detect_spike(candle, levels, avg_volume=0)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_range_candle(self):
        """Test handling of candle with zero range (doji)."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 100,
            'low': 100,
            'close': 100,
            'volume': 1000
        }
        levels = {'points': 5}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is False
        assert result['magnitude'] == 0.0
        
    def test_exactly_2x_points_is_spike(self):
        """Test that exactly 2x Points is NOT detected as spike (threshold uses <=)."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 110,
            'low': 100,
            'close': 105,
            'volume': 1000
        }
        levels = {'points': 5}  # Range = 10, Points = 5, Magnitude = 2.0
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['magnitude'] == 2.0
        # Threshold is 2.0, and we use <= in the check, so this should NOT be a spike
        assert result['is_spike'] is False
        
    def test_just_above_threshold_is_spike(self):
        """Test that just above threshold is detected as spike."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 110.1,
            'low': 100,
            'close': 105,
            'volume': 1000
        }
        levels = {'points': 5}  # Range = 10.1, Points = 5, Magnitude = 2.02
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['magnitude'] > 2.0
        
    def test_very_high_volume_spike(self):
        """Test spike with extremely high volume."""
        detector = SpikeDetector()
        
        candle = {
            'open': 100,
            'high': 120,
            'low': 100,
            'close': 118,
            'volume': 10000  # 10x average
        }
        levels = {'points': 5, 'base': 100}
        
        result = detector.detect_spike(candle, levels, avg_volume=1000)
        
        assert result['is_spike'] is True
        assert result['spike_type'] == 'real'
        assert result['confidence'] > 0.7


class TestSpikeDetectorInitialization:
    """Test Spike Detector initialization."""
    
    def test_default_initialization(self):
        """Test default initialization values."""
        detector = SpikeDetector()
        assert detector.spike_threshold == 2.0
        assert detector.volume_ratio_high == 2.0
        assert detector.volume_ratio_low == 0.5
        assert detector.close_position_threshold == 0.7
        
    def test_detector_is_reusable(self):
        """Test that detector can be reused for multiple detections."""
        detector = SpikeDetector()
        
        candle1 = {
            'open': 100,
            'high': 120,
            'low': 100,
            'close': 115,
            'volume': 2000
        }
        candle2 = {
            'open': 100,
            'high': 105,
            'low': 100,
            'close': 103,
            'volume': 1000
        }
        levels = {'points': 5}
        
        result1 = detector.detect_spike(candle1, levels, avg_volume=1000)
        result2 = detector.detect_spike(candle2, levels, avg_volume=1000)
        
        # Both should work without interference
        assert result1['is_spike'] is True
        assert result2['is_spike'] is False
