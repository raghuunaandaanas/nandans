"""
Property-based tests for Phase 11: HFT Mode & Advanced Features.
Uses Hypothesis to validate universal properties.
"""

import pytest
from hypothesis import given, strategies as st, assume
from src.main import HFTMicroTickTrader, FibonacciAnalyzer, MultiTimeframeCoordinator, LevelCalculator


class TestHFTMicroTickProperties:
    """Property-based tests for HFT Micro Tick Trader."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hft_trader = HFTMicroTickTrader()
    
    @given(price=st.floats(min_value=1.0, max_value=999999.99, allow_nan=False, allow_infinity=False))
    def test_property_micro_digit_extraction(self, price):
        """
        Property 18: Micro Tick Digit Extraction
        Correctly extract last 1, 2, 3 digits from any price.
        """
        assume(price > 0)
        
        result = self.hft_trader.extract_micro_levels(price)
        
        # All digits should be non-negative
        assert result['last_digit'] >= 0
        assert result['last_2_digits'] >= 0
        assert result['last_3_digits'] >= 0
        
        # Digits should be within valid ranges
        assert 0 <= result['last_digit'] <= 9
        assert 0 <= result['last_2_digits'] <= 99
        assert 0 <= result['last_3_digits'] <= 999
        
        # Price should be preserved
        assert result['price'] == price
    
    @given(
        last_digit=st.integers(min_value=0, max_value=9),
        last_2_digits=st.integers(min_value=0, max_value=99),
        last_3_digits=st.integers(min_value=0, max_value=999)
    )
    def test_property_micro_points_calculation(self, last_digit, last_2_digits, last_3_digits):
        """
        Property: Micro points calculation is deterministic and proportional.
        """
        digits = {
            'last_digit': last_digit,
            'last_2_digits': last_2_digits,
            'last_3_digits': last_3_digits
        }
        
        result = self.hft_trader.calculate_micro_points(digits)
        
        # Points should be non-negative
        assert result['micro_points'] >= 0
        assert result['mini_points'] >= 0
        assert result['standard_points'] >= 0
        
        # Points should be proportional to digits
        assert result['micro_points'] == pytest.approx(last_digit * 0.002611, rel=1e-6)
        assert result['mini_points'] == pytest.approx(last_2_digits * 0.002611, rel=1e-6)
        assert result['standard_points'] == pytest.approx(last_3_digits * 0.002611, rel=1e-6)
    
    @given(
        entry_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        elapsed_seconds=st.floats(min_value=0.0, max_value=120.0, allow_nan=False, allow_infinity=False)
    )
    def test_property_hft_exit_logic(self, entry_price, elapsed_seconds):
        """
        Property: HFT exit logic is consistent and deterministic.
        """
        assume(entry_price > 0)
        assume(elapsed_seconds >= 0)
        
        trade = {
            'direction': 'long',
            'entry_price': entry_price,
            'target_price': entry_price * 1.003,
            'stop_loss_price': entry_price * 0.9995
        }
        
        # Test at entry price (should not exit unless max time)
        result = self.hft_trader.check_hft_exit(trade, entry_price, elapsed_seconds)
        
        if elapsed_seconds >= self.hft_trader.max_hold_seconds:
            assert result['should_exit'] is True
            assert result['reason'] == 'Max hold time reached'
        else:
            # At entry price, P&L should be zero
            assert result['pnl_pct'] == pytest.approx(0.0, abs=1e-6)


class TestFibonacciAnalyzerProperties:
    """Property-based tests for Fibonacci Analyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fib_analyzer = FibonacciAnalyzer()
    
    @given(price=st.floats(min_value=1.0, max_value=999999.99, allow_nan=False, allow_infinity=False))
    def test_property_fibonacci_recognition(self, price):
        """
        Property 27: Fibonacci Number Recognition
        Correctly identify Fibonacci digits in prices.
        """
        assume(price > 0)
        
        result = self.fib_analyzer.recognize_fib_numbers(price)
        
        # Result should always have required keys
        assert 'fib_found' in result
        assert 'fib_type' in result
        assert 'fib_value' in result
        assert 'price' in result
        
        # If fib found, type and value should be set
        if result['fib_found']:
            assert result['fib_type'] in ['support', 'resistance']
            assert result['fib_value'] in self.fib_analyzer.FIB_NUMBERS
        else:
            assert result['fib_type'] is None
            assert result['fib_value'] is None
    
    @given(
        num_touches=st.integers(min_value=0, max_value=10),
        level=st.floats(min_value=10.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_property_rally_prediction_touch_count(self, num_touches, level):
        """
        Property: Rally prediction requires at least 3 touches.
        """
        assume(level > 0)
        
        price_touches = [
            {'timestamp': i * 1000, 'price': level + (i % 2) * 0.1}
            for i in range(num_touches)
        ]
        
        result = self.fib_analyzer.predict_rally(price_touches, level)
        
        if num_touches < 3:
            assert result['rally_predicted'] is False
        else:
            # With 3+ touches, prediction depends on other factors
            assert 'rally_predicted' in result
    
    @given(
        price=st.floats(min_value=1000.0, max_value=99999.99, allow_nan=False, allow_infinity=False),
        base_price=st.floats(min_value=1000.0, max_value=99999.99, allow_nan=False, allow_infinity=False)
    )
    def test_property_combine_with_levels(self, price, base_price):
        """
        Property: Combining Fibonacci with levels produces valid signal strength.
        """
        assume(price > 0)
        assume(base_price > 0)
        
        # Create simple BU/BE levels
        factor = 0.002611 if base_price >= 10000 else 0.0261
        points = base_price * factor
        
        bu_be_levels = {
            'Base': base_price,
            'Points': points,
            'BU1': base_price + points,
            'BE1': base_price - points
        }
        
        result = self.fib_analyzer.combine_with_levels(price, bu_be_levels)
        
        # Signal strength should be between 0 and 1
        assert 0.0 <= result['signal_strength'] <= 1.0
        
        # Position multiplier should be positive
        assert result['position_multiplier'] > 0
        
        # Should have all required keys
        assert 'aligned_levels' in result
        assert 'reasons' in result


class TestMultiTimeframeProperties:
    """Property-based tests for Multi-Timeframe Coordinator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.level_calculator = LevelCalculator()
        self.mtf_coordinator = MultiTimeframeCoordinator(self.level_calculator)
    
    @given(
        signal_1m=st.sampled_from(['bullish', 'bearish', 'neutral']),
        signal_5m=st.sampled_from(['bullish', 'bearish', 'neutral']),
        signal_15m=st.sampled_from(['bullish', 'bearish', 'neutral'])
    )
    def test_property_timeframe_alignment(self, signal_1m, signal_5m, signal_15m):
        """
        Property 23: Multi-Timeframe Signal Alignment
        All timeframes aligned increases position size.
        """
        signals_1m = {'signal': signal_1m}
        signals_5m = {'signal': signal_5m}
        signals_15m = {'signal': signal_15m}
        
        result = self.mtf_coordinator.check_timeframe_alignment(
            signals_1m, signals_5m, signals_15m
        )
        
        # Result should have required keys
        assert 'aligned' in result
        assert 'direction' in result
        assert 'confidence' in result
        assert 'position_multiplier' in result
        
        # Confidence should be between 0 and 1
        assert 0.0 <= result['confidence'] <= 1.0
        
        # Position multiplier should be positive
        assert result['position_multiplier'] > 0
        
        # If all signals are the same and not neutral, should be aligned
        if signal_1m == signal_5m == signal_15m and signal_1m != 'neutral':
            assert result['aligned'] is True
            assert result['direction'] == signal_1m
            assert result['position_multiplier'] == 1.5
            assert result['confidence'] == 0.95
    
    @given(
        base_price_1m=st.floats(min_value=1000.0, max_value=99999.99, allow_nan=False, allow_infinity=False),
        base_price_5m=st.floats(min_value=1000.0, max_value=99999.99, allow_nan=False, allow_infinity=False),
        base_price_15m=st.floats(min_value=1000.0, max_value=99999.99, allow_nan=False, allow_infinity=False)
    )
    def test_property_all_timeframe_levels(self, base_price_1m, base_price_5m, base_price_15m):
        """
        Property: All timeframe levels are calculated independently.
        """
        assume(base_price_1m > 0)
        assume(base_price_5m > 0)
        assume(base_price_15m > 0)
        
        base_prices = {
            '1m': base_price_1m,
            '5m': base_price_5m,
            '15m': base_price_15m
        }
        
        result = self.mtf_coordinator.calculate_all_timeframe_levels(base_prices)
        
        # Should have levels for all timeframes
        assert '1m' in result
        assert '5m' in result
        assert '15m' in result
        
        # Each timeframe should have BU and BE levels
        for tf in ['1m', '5m', '15m']:
            assert 'bu1' in result[tf]
            assert 'be1' in result[tf]
            assert 'base' in result[tf]
            assert 'points' in result[tf]
    
    @given(
        signal_1m=st.sampled_from(['bullish', 'bearish', 'neutral']),
        signal_5m=st.sampled_from(['bullish', 'bearish', 'neutral']),
        signal_15m=st.sampled_from(['bullish', 'bearish', 'neutral'])
    )
    def test_property_weighted_signal(self, signal_1m, signal_5m, signal_15m):
        """
        Property: Weighted signal respects timeframe importance (15m > 5m > 1m).
        """
        signals_1m = {'signal': signal_1m}
        signals_5m = {'signal': signal_5m}
        signals_15m = {'signal': signal_15m}
        
        result = self.mtf_coordinator.get_weighted_signal(
            signals_1m, signals_5m, signals_15m
        )
        
        # Result should have required keys
        assert 'signal' in result
        assert 'confidence' in result
        assert 'bullish_score' in result
        assert 'bearish_score' in result
        
        # Scores should be non-negative
        assert result['bullish_score'] >= 0.0
        assert result['bearish_score'] >= 0.0
        
        # Scores should not exceed 1.0 (sum of all weights)
        assert result['bullish_score'] <= 1.0
        assert result['bearish_score'] <= 1.0
        
        # If 15m is bullish, bullish score should include 0.5 weight
        if signal_15m == 'bullish':
            assert result['bullish_score'] >= 0.5
        
        # If 15m is bearish, bearish score should include 0.5 weight
        if signal_15m == 'bearish':
            assert result['bearish_score'] >= 0.5
