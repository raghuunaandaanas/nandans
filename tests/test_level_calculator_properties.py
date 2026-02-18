"""
Property-Based Tests for Level Calculator

This module contains property-based tests using Hypothesis to verify
the correctness properties of the LevelCalculator class.

Each test validates a specific property that should hold true across
all valid inputs, as defined in the design document.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hypothesis import given, strategies as st, settings
from src.main import LevelCalculator
import pytest


# Test fixtures
@pytest.fixture
def calculator():
    """Fixture providing a LevelCalculator instance."""
    return LevelCalculator()


# Property 1: Level Calculation Correctness
# **Validates: Requirements 1.1-1.8, 9.1-9.3**
@given(
    base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    timeframe=st.sampled_from(['1m', '5m', '15m'])
)
@settings(max_examples=100)
def test_property_1_level_calculation_correctness(base_price, timeframe):
    """
    Property 1: Level Calculation Correctness
    
    For any base price and timeframe, calculating levels twice with the same
    base price should produce identical level values.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    """
    calculator = LevelCalculator()
    
    levels1 = calculator.calculate_levels(base_price, timeframe)
    levels2 = calculator.calculate_levels(base_price, timeframe)
    
    # All level values should be identical
    assert levels1 == levels2, "Calculating levels twice should produce identical results"
    
    # Verify all expected keys are present
    expected_keys = ['base', 'factor', 'points', 'bu1', 'bu2', 'bu3', 'bu4', 'bu5', 
                     'be1', 'be2', 'be3', 'be4', 'be5']
    assert all(key in levels1 for key in expected_keys), "All level keys should be present"


# Property 2: Factor Selection Determinism
# **Validates: Requirements 1.2, 9.1, 9.2, 9.3**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_2_factor_selection_determinism(base_price):
    """
    Property 2: Factor Selection Determinism
    
    For any base price, the selected factor should be:
    - 26.11% (0.2611) if price < 1000
    - 2.61% (0.02611) if 1000 <= price < 10000
    - 0.2611% (0.002611) if price >= 10000
    
    **Validates: Requirements 1.2, 9.1, 9.2, 9.3**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    if base_price < 1000:
        expected_factor = 0.2611
    elif base_price < 10000:
        expected_factor = 0.02611
    else:
        expected_factor = 0.002611
    
    assert levels['factor'] == expected_factor, \
        f"Factor for price {base_price} should be {expected_factor}, got {levels['factor']}"


# Property 3: Points Calculation
# **Validates: Requirements 1.3**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_3_points_calculation(base_price):
    """
    Property 3: Points Calculation
    
    For any base price and factor, Points should equal base_price × factor
    with precision maintained.
    
    **Validates: Requirements 1.3**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    expected_points = round(base_price * levels['factor'], 2)
    
    assert levels['points'] == expected_points, \
        f"Points should be {expected_points}, got {levels['points']}"


# Property 4: BU Level Ordering
# **Validates: Requirements 1.4**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_4_bu_level_ordering(base_price):
    """
    Property 4: BU Level Ordering
    
    For any calculated levels, BU1 < BU2 < BU3 < BU4 < BU5 should always hold.
    
    **Validates: Requirements 1.4**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    assert levels['bu1'] < levels['bu2'], "BU1 should be less than BU2"
    assert levels['bu2'] < levels['bu3'], "BU2 should be less than BU3"
    assert levels['bu3'] < levels['bu4'], "BU3 should be less than BU4"
    assert levels['bu4'] < levels['bu5'], "BU4 should be less than BU5"
    
    # Also verify all BU levels are above base
    assert levels['base'] < levels['bu1'], "Base should be less than BU1"


# Property 5: BE Level Ordering
# **Validates: Requirements 1.5**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_5_be_level_ordering(base_price):
    """
    Property 5: BE Level Ordering
    
    For any calculated levels, BE5 < BE4 < BE3 < BE2 < BE1 < Base should always hold.
    
    **Validates: Requirements 1.5**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    assert levels['be5'] < levels['be4'], "BE5 should be less than BE4"
    assert levels['be4'] < levels['be3'], "BE4 should be less than BE3"
    assert levels['be3'] < levels['be2'], "BE3 should be less than BE2"
    assert levels['be2'] < levels['be1'], "BE2 should be less than BE1"
    assert levels['be1'] < levels['base'], "BE1 should be less than Base"


# Property 6: Level Symmetry
# **Validates: Requirements 1.4, 1.5**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_6_level_symmetry(base_price):
    """
    Property 6: Level Symmetry
    
    For any base price, the distance from Base to BU1 should equal
    the distance from Base to BE1.
    
    **Validates: Requirements 1.4, 1.5**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    distance_to_bu1 = levels['bu1'] - levels['base']
    distance_to_be1 = levels['base'] - levels['be1']
    
    # Allow tolerance for rounding to 2 decimal places
    # Since values are rounded to 2 decimals, max difference is 0.02
    assert abs(distance_to_bu1 - distance_to_be1) <= 0.02, \
        f"Distance to BU1 ({distance_to_bu1}) should equal distance to BE1 ({distance_to_be1})"
    
    # Verify this holds for all levels
    for i in range(1, 6):
        bu_key = f'bu{i}'
        be_key = f'be{i}'
        distance_to_bu = levels[bu_key] - levels['base']
        distance_to_be = levels['base'] - levels[be_key]
        
        # Allow tolerance for rounding effects (0.02 per level, plus accumulation)
        tolerance = 0.02 * i
        assert abs(distance_to_bu - distance_to_be) <= tolerance, \
            f"Distance to {bu_key.upper()} should equal distance to {be_key.upper()}"


# Property 7: Display Precision
# **Validates: Requirements 1.8**
@given(base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_7_display_precision(base_price):
    """
    Property 7: Display Precision
    
    For any calculated level value, when formatted for display,
    it should have exactly 2 decimal places.
    
    **Validates: Requirements 1.8**
    """
    calculator = LevelCalculator()
    levels = calculator.calculate_levels(base_price, '1m')
    
    # Check all level values have exactly 2 decimal places
    for key, value in levels.items():
        if key == 'factor':
            continue  # Factor is not a display value
        
        # Convert to string and check decimal places
        value_str = f"{value:.2f}"
        reconstructed = float(value_str)
        
        # The value should equal its 2-decimal representation
        assert abs(value - reconstructed) < 0.001, \
            f"{key} value {value} should have 2 decimal precision"
        
        # Verify the stored value is already rounded to 2 decimals
        assert value == round(value, 2), \
            f"{key} value {value} should be rounded to 2 decimal places"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
