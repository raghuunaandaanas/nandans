"""
B5 Factor Trading System - Main Module

This module contains the core trading system components including:
- LevelCalculator: Calculates BU and BE levels based on B5 Factor
- SignalGenerator: Generates entry and exit signals
- PositionManager: Manages positions, pyramiding, and stop losses
- TradingEngine: Orchestrates the entire trading system
"""

from typing import Dict, Optional, List


class LevelCalculator:
    """
    Calculates BU (Bullish) and BE (Bearish) levels using the B5 Factor method.
    
    The B5 Factor is based on the master number 0.2611, which varies by price range:
    - 0.2611% for prices 10000-99999
    - 2.61% for prices 1000-9999
    - 26.11% for prices 0-999
    
    Levels are calculated as:
    - Points = base_price × factor
    - BU1-BU5 = base_price + (Points × 1 through 5)
    - BE1-BE5 = base_price - (Points × 1 through 5)
    """
    
    def calculate_levels(self, base_price: float, timeframe: str) -> Dict[str, float]:
        """
        Calculate BU1-BU5 and BE1-BE5 levels based on base price.
        
        Args:
            base_price: The close price of the first candle in the timeframe
            timeframe: The timeframe ('1m', '5m', or '15m')
            
        Returns:
            Dictionary containing:
                - base: The base price
                - factor: The selected factor (as decimal)
                - points: The calculated points value
                - bu1 through bu5: Bullish levels
                - be1 through be5: Bearish levels
                
        Raises:
            ValueError: If base_price is invalid (negative or zero)
            
        Examples:
            >>> calc = LevelCalculator()
            >>> levels = calc.calculate_levels(50000.00, '1m')
            >>> levels['bu1']  # Should be base_price + points
            50130.55
        """
        # Validate input
        if base_price <= 0:
            raise ValueError(f"Invalid base_price: {base_price}. Must be positive.")
        
        # Determine factor based on price range
        # Requirements 1.2, 9.1, 9.2, 9.3
        factor = self._select_factor(base_price)
        
        # Calculate Points = base_price × factor
        # Requirement 1.3
        points = base_price * factor
        
        # Calculate BU levels (Bullish)
        # Requirement 1.4
        bu1 = base_price + (points * 1)
        bu2 = base_price + (points * 2)
        bu3 = base_price + (points * 3)
        bu4 = base_price + (points * 4)
        bu5 = base_price + (points * 5)
        
        # Calculate BE levels (Bearish)
        # Requirement 1.5
        be1 = base_price - (points * 1)
        be2 = base_price - (points * 2)
        be3 = base_price - (points * 3)
        be4 = base_price - (points * 4)
        be5 = base_price - (points * 5)
        
        return {
            'base': round(base_price, 2),
            'factor': factor,
            'points': round(points, 2),
            'bu1': round(bu1, 2),
            'bu2': round(bu2, 2),
            'bu3': round(bu3, 2),
            'bu4': round(bu4, 2),
            'bu5': round(bu5, 2),
            'be1': round(be1, 2),
            'be2': round(be2, 2),
            'be3': round(be3, 2),
            'be4': round(be4, 2),
            'be5': round(be5, 2),
        }
    
    def _select_factor(self, base_price: float) -> float:
        """
        Select the appropriate factor based on price range.
        
        Args:
            base_price: The price to determine factor for
            
        Returns:
            The factor as a decimal (0.002611, 0.02611, or 0.2611)
            
        Factor selection logic:
        - Price < 1000: 26.11% (0.2611)
        - Price 1000-9999: 2.61% (0.02611)
        - Price >= 10000: 0.2611% (0.002611)
        """
        if base_price < 1000:
            return 0.2611  # 26.11%
        elif base_price < 10000:
            return 0.02611  # 2.61%
        else:
            return 0.002611  # 0.2611%


class SignalGenerator:
    """
    Generates entry and exit signals based on price movements relative to BU/BE levels.
    
    Entry signals are generated when price crosses BU1 (bullish) or BE1 (bearish).
    Exit signals are generated when price reaches BU2-BU5 or BE2-BE5 levels.
    
    The generator considers trading mode (soft, smooth, aggressive) to determine
    whether to enter immediately on cross or wait for candle close confirmation.
    """
    
    def check_entry_signal(self, current_price: float, levels: Dict[str, float], 
                          mode: str = 'smooth') -> Dict[str, any]:
        """
        Check for entry signals based on price crossing BU1 or BE1.
        
        Args:
            current_price: Current market price
            levels: Dictionary of calculated BU/BE levels from LevelCalculator
            mode: Trading mode - 'soft', 'smooth', or 'aggressive'
            
        Returns:
            Dictionary containing:
                - signal: 'buy', 'sell', or None
                - level: 'BU1', 'BE1', or None
                - confidence: float (0-1) indicating signal strength
                - wait_for_close: bool indicating if should wait for candle close
                
        Requirements: 5.1, 5.2, 5.3
        
        Examples:
            >>> gen = SignalGenerator()
            >>> levels = {'base': 50000, 'bu1': 50130.55, 'be1': 49869.45, 'points': 130.55}
            >>> signal = gen.check_entry_signal(50150, levels, 'smooth')
            >>> signal['signal']
            'buy'
        """
        # Validate inputs
        if not levels or 'bu1' not in levels or 'be1' not in levels:
            raise ValueError("Invalid levels dictionary")
        
        if mode not in ['soft', 'smooth', 'aggressive']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'soft', 'smooth', or 'aggressive'")
        
        base_price = levels['base']
        bu1 = levels['bu1']
        be1 = levels['be1']
        
        # Check for bullish signal: price crosses above BU1
        # Requirement 5.1
        if current_price > bu1:
            confidence = self._calculate_confidence(current_price, levels, 'bullish')
            wait_for_close = self._should_wait_for_close(mode, confidence)
            
            return {
                'signal': 'buy',
                'level': 'BU1',
                'confidence': confidence,
                'wait_for_close': wait_for_close
            }
        
        # Check for bearish signal: price crosses below BE1
        # Requirement 5.2
        if current_price < be1:
            confidence = self._calculate_confidence(current_price, levels, 'bearish')
            wait_for_close = self._should_wait_for_close(mode, confidence)
            
            return {
                'signal': 'sell',
                'level': 'BE1',
                'confidence': confidence,
                'wait_for_close': wait_for_close
            }
        
        # No signal - price is between BE1 and BU1
        return {
            'signal': None,
            'level': None,
            'confidence': 0.0,
            'wait_for_close': False
        }
    
    def check_exit_signal(self, current_price: float, position: Dict[str, any], 
                         levels: Dict[str, float]) -> Dict[str, any]:
        """
        Check for exit signals based on price reaching BU2-BU5 or BE2-BE5 levels.
        
        Args:
            current_price: Current market price
            position: Dictionary containing position info with 'direction' ('long' or 'short')
            levels: Dictionary of calculated BU/BE levels
            
        Returns:
            Dictionary containing:
                - action: 'exit_partial', 'exit_full', 'reverse', or None
                - level: 'BU2', 'BU3', 'BU4', 'BU5', 'BE2', 'BE3', 'BE4', 'BE5', or None
                - percentage: float (0-1) indicating what percentage to exit
                
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
        
        Examples:
            >>> gen = SignalGenerator()
            >>> levels = {'bu2': 50261.10, 'bu3': 50391.65, 'bu4': 50522.20, 'bu5': 50652.75}
            >>> position = {'direction': 'long'}
            >>> signal = gen.check_exit_signal(50270, position, levels)
            >>> signal['action']
            'exit_partial'
        """
        # Validate inputs
        if not position or 'direction' not in position:
            raise ValueError("Invalid position dictionary - must contain 'direction'")
        
        if position['direction'] not in ['long', 'short']:
            raise ValueError(f"Invalid direction: {position['direction']}")
        
        direction = position['direction']
        
        # Check exit signals for long positions
        if direction == 'long':
            # BU5: Final exit or reverse (Requirement 6.4)
            if current_price >= levels['bu5']:
                return {
                    'action': 'exit_full',
                    'level': 'BU5',
                    'percentage': 1.0
                }
            
            # BU4: Partial exit (Requirement 6.3)
            elif current_price >= levels['bu4']:
                return {
                    'action': 'exit_partial',
                    'level': 'BU4',
                    'percentage': 0.25
                }
            
            # BU3: Partial exit (Requirement 6.2)
            elif current_price >= levels['bu3']:
                return {
                    'action': 'exit_partial',
                    'level': 'BU3',
                    'percentage': 0.25
                }
            
            # BU2: Partial exit (Requirement 6.1)
            elif current_price >= levels['bu2']:
                return {
                    'action': 'exit_partial',
                    'level': 'BU2',
                    'percentage': 0.25
                }
        
        # Check exit signals for short positions
        elif direction == 'short':
            # BE5: Final exit or reverse (Requirement 6.8)
            if current_price <= levels['be5']:
                return {
                    'action': 'exit_full',
                    'level': 'BE5',
                    'percentage': 1.0
                }
            
            # BE4: Partial exit (Requirement 6.7)
            elif current_price <= levels['be4']:
                return {
                    'action': 'exit_partial',
                    'level': 'BE4',
                    'percentage': 0.25
                }
            
            # BE3: Partial exit (Requirement 6.6)
            elif current_price <= levels['be3']:
                return {
                    'action': 'exit_partial',
                    'level': 'BE3',
                    'percentage': 0.25
                }
            
            # BE2: Partial exit (Requirement 6.5)
            elif current_price <= levels['be2']:
                return {
                    'action': 'exit_partial',
                    'level': 'BE2',
                    'percentage': 0.25
                }
        
        # No exit signal
        return {
            'action': None,
            'level': None,
            'percentage': 0.0
        }
    
    def should_wait_for_close(self, price_action: List[float], volume: List[float], 
                             mode: str) -> bool:
        """
        Determine if should wait for candle close or enter immediately.
        
        Analyzes price action momentum and volume to determine entry timing.
        
        Args:
            price_action: List of recent prices to analyze momentum
            volume: List of recent volume values
            mode: Trading mode - 'soft', 'smooth', or 'aggressive'
            
        Returns:
            True if should wait for candle close, False if can enter immediately
            
        Requirements: 5.3, 10.1, 10.2, 10.3
        
        Examples:
            >>> gen = SignalGenerator()
            >>> prices = [50000, 50050, 50100, 50150, 50200]  # Strong uptrend
            >>> volumes = [1000, 1200, 1500, 1800, 2000]  # Increasing volume
            >>> gen.should_wait_for_close(prices, volumes, 'aggressive')
            False
        """
        # Validate inputs
        if not price_action or len(price_action) < 2:
            return True  # Not enough data, wait for close
        
        if mode not in ['soft', 'smooth', 'aggressive']:
            raise ValueError(f"Invalid mode: {mode}")
        
        # Soft mode always waits for close (Requirement 26.5)
        if mode == 'soft':
            return True
        
        # Aggressive mode never waits (Requirement 26.7)
        if mode == 'aggressive':
            return False
        
        # Smooth mode: analyze momentum and volume (Requirement 26.6)
        momentum = self._calculate_momentum(price_action)
        volume_strength = self._analyze_volume_strength(volume) if volume else 0.5
        
        # Strong momentum + strong volume = enter immediately
        # Requirement 10.2
        if momentum > 0.7 and volume_strength > 0.6:
            return False
        
        # Weak momentum or weak volume = wait for close
        # Requirement 10.3
        return True
    
    def _calculate_confidence(self, current_price: float, levels: Dict[str, float], 
                             direction: str) -> float:
        """
        Calculate confidence level for a signal based on how far price is beyond the level.
        
        Args:
            current_price: Current market price
            levels: Dictionary of levels
            direction: 'bullish' or 'bearish'
            
        Returns:
            Confidence value between 0 and 1
        """
        points = levels.get('points', 0)
        if points == 0:
            return 0.5  # Default confidence
        
        if direction == 'bullish':
            bu1 = levels['bu1']
            # Confidence increases with distance above BU1
            distance = current_price - bu1
            confidence = min(1.0, 0.5 + (distance / points) * 0.5)
        else:  # bearish
            be1 = levels['be1']
            # Confidence increases with distance below BE1
            distance = be1 - current_price
            confidence = min(1.0, 0.5 + (distance / points) * 0.5)
        
        return round(confidence, 2)
    
    def _should_wait_for_close(self, mode: str, confidence: float) -> bool:
        """
        Determine if should wait for close based on mode and confidence.
        
        Args:
            mode: Trading mode
            confidence: Signal confidence (0-1)
            
        Returns:
            True if should wait for close
        """
        # Soft mode always waits
        if mode == 'soft':
            return True
        
        # Aggressive mode never waits
        if mode == 'aggressive':
            return False
        
        # Smooth mode: wait if confidence is low
        return confidence < 0.7
    
    def _calculate_momentum(self, price_action: List[float]) -> float:
        """
        Calculate momentum from price action.
        
        Args:
            price_action: List of recent prices
            
        Returns:
            Momentum value between 0 and 1
        """
        if len(price_action) < 2:
            return 0.5
        
        # Calculate rate of change
        total_change = price_action[-1] - price_action[0]
        avg_price = sum(price_action) / len(price_action)
        
        if avg_price == 0:
            return 0.5
        
        # Normalize to 0-1 range
        momentum = abs(total_change / avg_price) * 10  # Scale up
        return min(1.0, momentum)
    
    def _analyze_volume_strength(self, volume: List[float]) -> float:
        """
        Analyze volume strength.
        
        Args:
            volume: List of recent volume values
            
        Returns:
            Volume strength between 0 and 1
        """
        if not volume or len(volume) < 2:
            return 0.5
        
        # Compare recent volume to average
        avg_volume = sum(volume[:-1]) / len(volume[:-1]) if len(volume) > 1 else volume[0]
        current_volume = volume[-1]
        
        if avg_volume == 0:
            return 0.5
        
        # Volume ratio
        ratio = current_volume / avg_volume
        
        # Normalize to 0-1 range (ratio > 1.5 is strong)
        strength = min(1.0, ratio / 1.5)
        return strength


if __name__ == "__main__":
    # Example usage
    calculator = LevelCalculator()
    signal_gen = SignalGenerator()
    
    # Example 1: BTC price around 50000
    levels_btc = calculator.calculate_levels(50000.00, '1m')
    print("BTC Levels (Base: 50000.00):")
    print(f"  Factor: {levels_btc['factor']*100:.4f}%")
    print(f"  Points: {levels_btc['points']}")
    print(f"  BU Levels: {levels_btc['bu1']}, {levels_btc['bu2']}, {levels_btc['bu3']}, {levels_btc['bu4']}, {levels_btc['bu5']}")
    print(f"  BE Levels: {levels_btc['be1']}, {levels_btc['be2']}, {levels_btc['be3']}, {levels_btc['be4']}, {levels_btc['be5']}")
    print()
    
    # Test entry signals
    print("Entry Signal Tests:")
    # Price above BU1 - bullish signal
    signal = signal_gen.check_entry_signal(50150, levels_btc, 'smooth')
    print(f"  Price 50150 (above BU1): {signal}")
    
    # Price below BE1 - bearish signal
    signal = signal_gen.check_entry_signal(49850, levels_btc, 'smooth')
    print(f"  Price 49850 (below BE1): {signal}")
    
    # Price between BE1 and BU1 - no signal
    signal = signal_gen.check_entry_signal(50000, levels_btc, 'smooth')
    print(f"  Price 50000 (between levels): {signal}")
    print()
    
    # Test exit signals
    print("Exit Signal Tests:")
    long_position = {'direction': 'long'}
    
    # Price at BU2
    exit_signal = signal_gen.check_exit_signal(50261, long_position, levels_btc)
    print(f"  Long position at BU2 (50261): {exit_signal}")
    
    # Price at BU3
    exit_signal = signal_gen.check_exit_signal(50392, long_position, levels_btc)
    print(f"  Long position at BU3 (50392): {exit_signal}")
    
    # Price at BU5
    exit_signal = signal_gen.check_exit_signal(50653, long_position, levels_btc)
    print(f"  Long position at BU5 (50653): {exit_signal}")
    print()
    
    # Test wait for close logic
    print("Wait for Close Tests:")
    strong_momentum_prices = [50000, 50050, 50100, 50150, 50200]
    strong_volumes = [1000, 1200, 1500, 1800, 2000]
    
    wait_soft = signal_gen.should_wait_for_close(strong_momentum_prices, strong_volumes, 'soft')
    wait_smooth = signal_gen.should_wait_for_close(strong_momentum_prices, strong_volumes, 'smooth')
    wait_aggressive = signal_gen.should_wait_for_close(strong_momentum_prices, strong_volumes, 'aggressive')
    
    print(f"  Soft mode (strong momentum): wait={wait_soft}")
    print(f"  Smooth mode (strong momentum): wait={wait_smooth}")
    print(f"  Aggressive mode (strong momentum): wait={wait_aggressive}")
    print()
    
    # Example 2: Nifty price around 18000
    levels_nifty = calculator.calculate_levels(18000.00, '5m')
    print("Nifty Levels (Base: 18000.00):")
    print(f"  Factor: {levels_nifty['factor']*100:.4f}%")
    print(f"  Points: {levels_nifty['points']}")
    print(f"  BU Levels: {levels_nifty['bu1']}, {levels_nifty['bu2']}, {levels_nifty['bu3']}, {levels_nifty['bu4']}, {levels_nifty['bu5']}")
    print(f"  BE Levels: {levels_nifty['be1']}, {levels_nifty['be2']}, {levels_nifty['be3']}, {levels_nifty['be4']}, {levels_nifty['be5']}")
    print()
    
    # Example 3: Low price stock around 500
    levels_stock = calculator.calculate_levels(500.00, '15m')
    print("Stock Levels (Base: 500.00):")
    print(f"  Factor: {levels_stock['factor']*100:.4f}%")
    print(f"  Points: {levels_stock['points']}")
    print(f"  BU Levels: {levels_stock['bu1']}, {levels_stock['bu2']}, {levels_stock['bu3']}, {levels_stock['bu4']}, {levels_stock['bu5']}")
    print(f"  BE Levels: {levels_stock['be1']}, {levels_stock['be2']}, {levels_stock['be3']}, {levels_stock['be4']}, {levels_stock['be5']}")
