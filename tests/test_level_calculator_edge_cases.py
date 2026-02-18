"""
Unit Tests for Level Calculator Edge Cases

This module contains unit tests for specific edge cases and boundary conditions
in the Level Calculator, focusing on factor selection boundaries.

**Validates: Requirements 1.2**
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from main import LevelCalculator


class TestLevelCalculatorEdgeCases:
    """Test edge cases and boundary conditions for Level Calculator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calculator = LevelCalculator()
    
    def test_price_zero_raises_error(self):
        """
        Test that price = 0 is handled gracefully with ValueError.
        
        Edge case: Zero price should be rejected as invalid.
        **Validates: Requirements 1.2**
        """
        with pytest.raises(ValueError, match="Invalid base_price.*Must be positive"):
            self.calculator.calculate_levels(0, '1m')
    
    def test_price_999_99_uses_26_11_percent_factor(self):
        """
        Test boundary for 26.11% factor at price = 999.99.
        
        Edge case: Price just below 1000 should use 26.11% factor (0.2611).
        **Validates: Requirements 1.2**
        """
        levels = self.calculator.calculate_levels(999.99, '1m')
        
        # Should use 26.11% factor
        assert levels['factor'] == 0.2611, f"Expected factor 0.2611, got {levels['factor']}"
        
        # Verify points calculation
        expected_points = 999.99 * 0.2611
        assert abs(levels['points'] - expected_points) < 0.01, \
            f"Expected points ~{expected_points:.2f}, got {levels['points']}"
        
        # Verify base price
        assert levels['base'] == 999.99
        
        # Verify BU levels are above base
        assert levels['bu1'] > levels['base']
        assert levels['bu2'] > levels['bu1']
        
        # Verify BE levels are below base
        assert levels['be1'] < levels['base']
        assert levels['be2'] < levels['be1']
    
    def test_price_1000_00_uses_2_61_percent_factor(self):
        """
        Test boundary for 2.61% factor at price = 1000.00.
        
        Edge case: Price exactly at 1000 should use 2.61% factor (0.02611).
        **Validates: Requirements 1.2**
        """
        levels = self.calculator.calculate_levels(1000.00, '1m')
        
        # Should use 2.61% factor
        assert levels['factor'] == 0.02611, f"Expected factor 0.02611, got {levels['factor']}"
        
        # Verify points calculation
        expected_points = 1000.00 * 0.02611
        assert abs(levels['points'] - expected_points) < 0.01, \
            f"Expected points ~{expected_points:.2f}, got {levels['points']}"
        
        # Verify base price
        assert levels['base'] == 1000.00
        
        # Verify BU levels are above base
        assert levels['bu1'] > levels['base']
        assert levels['bu2'] > levels['bu1']
        
        # Verify BE levels are below base
        assert levels['be1'] < levels['base']
        assert levels['be2'] < levels['be1']
    
    def test_price_9999_99_uses_2_61_percent_factor(self):
        """
        Test boundary for 2.61% factor at price = 9999.99.
        
        Edge case: Price just below 10000 should use 2.61% factor (0.02611).
        **Validates: Requirements 1.2**
        """
        levels = self.calculator.calculate_levels(9999.99, '1m')
        
        # Should use 2.61% factor
        assert levels['factor'] == 0.02611, f"Expected factor 0.02611, got {levels['factor']}"
        
        # Verify points calculation
        expected_points = 9999.99 * 0.02611
        assert abs(levels['points'] - expected_points) < 0.01, \
            f"Expected points ~{expected_points:.2f}, got {levels['points']}"
        
        # Verify base price
        assert levels['base'] == 9999.99
        
        # Verify BU levels are above base
        assert levels['bu1'] > levels['base']
        assert levels['bu2'] > levels['bu1']
        
        # Verify BE levels are below base
        assert levels['be1'] < levels['base']
        assert levels['be2'] < levels['be1']
    
    def test_price_10000_00_uses_0_2611_percent_factor(self):
        """
        Test boundary for 0.2611% factor at price = 10000.00.
        
        Edge case: Price exactly at 10000 should use 0.2611% factor (0.002611).
        **Validates: Requirements 1.2**
        """
        levels = self.calculator.calculate_levels(10000.00, '1m')
        
        # Should use 0.2611% factor
        assert levels['factor'] == 0.002611, f"Expected factor 0.002611, got {levels['factor']}"
        
        # Verify points calculation
        expected_points = 10000.00 * 0.002611
        assert abs(levels['points'] - expected_points) < 0.01, \
            f"Expected points ~{expected_points:.2f}, got {levels['points']}"
        
        # Verify base price
        assert levels['base'] == 10000.00
        
        # Verify BU levels are above base
        assert levels['bu1'] > levels['base']
        assert levels['bu2'] > levels['bu1']
        
        # Verify BE levels are below base
        assert levels['be1'] < levels['base']
        assert levels['be2'] < levels['be1']
    
    def test_all_edge_cases_maintain_level_ordering(self):
        """
        Test that all edge case prices maintain proper level ordering.
        
        Verifies that BU levels are ordered correctly (BU1 < BU2 < ... < BU5)
        and BE levels are ordered correctly (BE5 < BE4 < ... < BE1 < Base).
        **Validates: Requirements 1.2, 1.4, 1.5**
        """
        edge_prices = [999.99, 1000.00, 9999.99, 10000.00]
        
        for price in edge_prices:
            levels = self.calculator.calculate_levels(price, '1m')
            
            # Verify BU level ordering
            assert levels['bu1'] < levels['bu2'], f"BU1 should be < BU2 for price {price}"
            assert levels['bu2'] < levels['bu3'], f"BU2 should be < BU3 for price {price}"
            assert levels['bu3'] < levels['bu4'], f"BU3 should be < BU4 for price {price}"
            assert levels['bu4'] < levels['bu5'], f"BU4 should be < BU5 for price {price}"
            
            # Verify BE level ordering
            assert levels['be5'] < levels['be4'], f"BE5 should be < BE4 for price {price}"
            assert levels['be4'] < levels['be3'], f"BE4 should be < BE3 for price {price}"
            assert levels['be3'] < levels['be2'], f"BE3 should be < BE2 for price {price}"
            assert levels['be2'] < levels['be1'], f"BE2 should be < BE1 for price {price}"
            assert levels['be1'] < levels['base'], f"BE1 should be < Base for price {price}"
    
    def test_all_edge_cases_have_two_decimal_precision(self):
        """
        Test that all edge case prices produce levels with 2 decimal places.
        
        **Validates: Requirements 1.8**
        """
        edge_prices = [999.99, 1000.00, 9999.99, 10000.00]
        
        for price in edge_prices:
            levels = self.calculator.calculate_levels(price, '1m')
            
            # Check all level values have 2 decimal places
            for key in ['base', 'points', 'bu1', 'bu2', 'bu3', 'bu4', 'bu5', 
                       'be1', 'be2', 'be3', 'be4', 'be5']:
                value = levels[key]
                # Convert to string and check decimal places
                value_str = f"{value:.2f}"
                reconstructed = float(value_str)
                assert abs(value - reconstructed) < 0.001, \
                    f"{key} value {value} for price {price} should have 2 decimal precision"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
