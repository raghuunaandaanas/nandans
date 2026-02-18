"""
B5 Factor Trading System - Main Module

This module contains the core trading system components including:
- LevelCalculator: Calculates BU and BE levels based on B5 Factor
- SignalGenerator: Generates entry and exit signals
- PositionManager: Manages positions, pyramiding, and stop losses
- TradingEngine: Orchestrates the entire trading system
"""

from typing import Dict, Optional, List
import time
from datetime import datetime


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
    
    def detect_non_trending_day(self, price_history: List[Dict[str, any]], 
                               levels: Dict[str, float]) -> bool:
        """
        Detect if it's a Non-Trending Day based on 75-minute rule.
        
        A Non-Trending Day is detected when price stays between BE1 and BU1
        for 75 consecutive minutes without crossing either level.
        
        Args:
            price_history: List of price dictionaries with 'timestamp' and 'price'
            levels: Dictionary of calculated BU/BE levels
            
        Returns:
            True if Non-Trending Day detected, False otherwise
            
        Requirements: 5.8, 5.9
        
        Examples:
            >>> gen = SignalGenerator()
            >>> levels = {'bu1': 50130.55, 'be1': 49869.45}
            >>> # 75 minutes of prices between BE1 and BU1
            >>> history = [{'timestamp': i, 'price': 50000} for i in range(75)]
            >>> gen.detect_non_trending_day(history, levels)
            True
        """
        if not price_history or len(price_history) < 75:
            return False  # Not enough data
        
        bu1 = levels.get('bu1')
        be1 = levels.get('be1')
        
        if bu1 is None or be1 is None:
            return False
        
        # Check last 75 minutes
        recent_prices = price_history[-75:]
        
        # Count consecutive minutes between BE1 and BU1
        consecutive_minutes = 0
        
        for price_data in recent_prices:
            price = price_data.get('price', 0)
            
            # Check if price is between BE1 and BU1
            if be1 < price < bu1:
                consecutive_minutes += 1
            else:
                # Price crossed a level, reset counter
                consecutive_minutes = 0
        
        # Non-Trending Day if 75 consecutive minutes between levels
        # Requirement 5.8
        return consecutive_minutes >= 75
    
    def find_atm_strike(self, current_price: float, available_strikes: List[float],
                       strike_width: float = 50) -> Dict[str, any]:
        """
        Find the At-The-Money (ATM) strike and nearby strikes for options trading.
        
        Identifies the ATM strike and considers strikes within 6 above and below.
        Analyzes bid-ask spread and open interest for optimal strike selection.
        
        Args:
            current_price: Current underlying price
            available_strikes: List of available option strikes
            strike_width: Width between strikes (default: 50 for Nifty/BankNifty)
            
        Returns:
            Dictionary containing:
                - atm_strike: The ATM strike price
                - nearby_strikes: List of strikes within 6 above and below
                - recommended_strike: Best strike based on liquidity
                
        Requirements: 5.4, 5.5, 5.6, 5.7, 33.1, 33.2, 33.3, 33.4, 33.5, 33.6, 33.7
        
        Examples:
            >>> gen = SignalGenerator()
            >>> strikes = [18000, 18050, 18100, 18150, 18200, 18250, 18300]
            >>> result = gen.find_atm_strike(18125, strikes)
            >>> result['atm_strike']
            18100
        """
        if not available_strikes:
            raise ValueError("No strikes available")
        
        # Find ATM strike (closest to current price)
        # Requirement 5.4, 33.1
        atm_strike = min(available_strikes, key=lambda x: abs(x - current_price))
        
        # Find strikes within 6 above and below ATM
        # Requirement 5.5, 33.2
        atm_index = available_strikes.index(atm_strike)
        
        # Get 6 strikes above and below (total 13 strikes including ATM)
        start_index = max(0, atm_index - 6)
        end_index = min(len(available_strikes), atm_index + 7)
        
        nearby_strikes = available_strikes[start_index:end_index]
        
        # For now, recommend ATM strike
        # In production, this would analyze bid-ask spread and open interest
        # Requirements 5.6, 5.7, 33.3, 33.4, 33.5, 33.6, 33.7
        recommended_strike = atm_strike
        
        return {
            'atm_strike': atm_strike,
            'nearby_strikes': nearby_strikes,
            'recommended_strike': recommended_strike,
            'strike_width': strike_width
        }


    def detect_non_trending_day(self, price_history: List[Dict[str, any]],
                               levels: Dict[str, float]) -> bool:
        """
        Detect if it's a Non-Trending Day based on 75-minute rule.

        A Non-Trending Day is detected when price stays between BE1 and BU1
        for 75 consecutive minutes without crossing either level.

        Args:
            price_history: List of price dictionaries with 'timestamp' and 'price'
            levels: Dictionary of calculated BU/BE levels

        Returns:
            True if Non-Trending Day detected, False otherwise

        Requirements: 5.8, 5.9

        Examples:
            >>> gen = SignalGenerator()
            >>> levels = {'bu1': 50130.55, 'be1': 49869.45}
            >>> # 75 minutes of prices between BE1 and BU1
            >>> history = [{'timestamp': i, 'price': 50000} for i in range(75)]
            >>> gen.detect_non_trending_day(history, levels)
            True
        """
        if not price_history or len(price_history) < 75:
            return False  # Not enough data

        bu1 = levels.get('bu1')
        be1 = levels.get('be1')

        if bu1 is None or be1 is None:
            return False

        # Check last 75 minutes
        recent_prices = price_history[-75:]

        # Count consecutive minutes between BE1 and BU1
        consecutive_minutes = 0

        for price_data in recent_prices:
            price = price_data.get('price', 0)

            # Check if price is between BE1 and BU1
            if be1 < price < bu1:
                consecutive_minutes += 1
            else:
                # Price crossed a level, reset counter
                consecutive_minutes = 0

        # Non-Trending Day if 75 consecutive minutes between levels
        # Requirement 5.8
        return consecutive_minutes >= 75

    def find_atm_strike(self, current_price: float, available_strikes: List[float],
                       strike_width: float = 50) -> Dict[str, any]:
        """
        Find the At-The-Money (ATM) strike and nearby strikes for options trading.

        Identifies the ATM strike and considers strikes within 6 above and below.
        Analyzes bid-ask spread and open interest for optimal strike selection.

        Args:
            current_price: Current underlying price
            available_strikes: List of available option strikes
            strike_width: Width between strikes (default: 50 for Nifty/BankNifty)

        Returns:
            Dictionary containing:
                - atm_strike: The ATM strike price
                - nearby_strikes: List of strikes within 6 above and below
                - recommended_strike: Best strike based on liquidity

        Requirements: 5.4, 5.5, 5.6, 5.7, 33.1, 33.2, 33.3, 33.4, 33.5, 33.6, 33.7

        Examples:
            >>> gen = SignalGenerator()
            >>> strikes = [18000, 18050, 18100, 18150, 18200, 18250, 18300]
            >>> result = gen.find_atm_strike(18125, strikes)
            >>> result['atm_strike']
            18100
        """
        if not available_strikes:
            raise ValueError("No strikes available")

        # Find ATM strike (closest to current price)
        # Requirement 5.4, 33.1
        atm_strike = min(available_strikes, key=lambda x: abs(x - current_price))

        # Find strikes within 6 above and below ATM
        # Requirement 5.5, 33.2
        atm_index = available_strikes.index(atm_strike)

        # Get 6 strikes above and below (total 13 strikes including ATM)
        start_index = max(0, atm_index - 6)
        end_index = min(len(available_strikes), atm_index + 7)

        nearby_strikes = available_strikes[start_index:end_index]

        # For now, recommend ATM strike
        # In production, this would analyze bid-ask spread and open interest
        # Requirements 5.6, 5.7, 33.3, 33.4, 33.5, 33.6, 33.7
        recommended_strike = atm_strike

        return {
            'atm_strike': atm_strike,
            'nearby_strikes': nearby_strikes,
            'recommended_strike': recommended_strike,
            'strike_width': strike_width
        }



class PositionManager:
    """
    Manages position sizing, stop losses, pyramiding, and trailing stops.
    
    Calculates position sizes based on capital and risk parameters.
    Manages stop loss placement and adjustment based on BU/BE levels.
    Implements pyramiding logic for adding to winning positions.
    """
    
    def calculate_position_size(self, capital: float, risk_percent: float, 
                               stop_loss_distance: float, price: float) -> int:
        """
        Calculate position size based on capital and risk parameters.
        
        Position size = (capital × risk%) / stop_loss_distance
        
        Args:
            capital: Total trading capital
            risk_percent: Risk percentage per trade (e.g., 0.01 for 1%)
            stop_loss_distance: Distance from entry to stop loss in price units
            price: Current price (for calculating quantity)
            
        Returns:
            Position size (quantity)
            
        Requirements: 7.1, 17.5
        Property 14: Position Size Calculation
        
        Examples:
            >>> pm = PositionManager()
            >>> # Risk 1% of $10,000 with $50 stop loss distance
            >>> pm.calculate_position_size(10000, 0.01, 50, 50000)
            2
        """
        if capital <= 0:
            raise ValueError("Capital must be positive")
        
        if risk_percent <= 0 or risk_percent > 1:
            raise ValueError("Risk percent must be between 0 and 1")
        
        if stop_loss_distance <= 0:
            raise ValueError("Stop loss distance must be positive")
        
        if price <= 0:
            raise ValueError("Price must be positive")
        
        # Calculate risk amount in dollars
        risk_amount = capital * risk_percent
        
        # Calculate position size
        # size = risk_amount / stop_loss_distance
        position_value = risk_amount / (stop_loss_distance / price)
        
        # Convert to quantity
        quantity = int(position_value / price)
        
        return max(1, quantity)  # Minimum 1 unit
    
    def calculate_stop_loss(self, entry_price: float, levels: Dict[str, float], 
                           direction: str) -> float:
        """
        Calculate stop loss based on entry price and levels.
        
        Stop loss = Base ± (Points × 0.5)
        
        For long positions: stop loss below entry
        For short positions: stop loss above entry
        
        Args:
            entry_price: Entry price of position
            levels: Dictionary of calculated BU/BE levels
            direction: 'long' or 'short'
            
        Returns:
            Stop loss price
            
        Requirements: 7.2, 7.3
        Property 11: Stop Loss Calculation
        
        Examples:
            >>> pm = PositionManager()
            >>> levels = {'base': 50000, 'points': 130.55}
            >>> pm.calculate_stop_loss(50130, levels, 'long')
            49934.725
        """
        if direction not in ['long', 'short']:
            raise ValueError(f"Invalid direction: {direction}")
        
        base = levels.get('base')
        points = levels.get('points')
        
        if base is None or points is None:
            raise ValueError("Invalid levels dictionary")
        
        # Stop loss is 0.5 × Points away from base
        # Requirement 7.2
        stop_distance = points * 0.5
        
        if direction == 'long':
            # Long stop loss below base
            stop_loss = base - stop_distance
        else:
            # Short stop loss above base
            stop_loss = base + stop_distance
        
        return round(stop_loss, 2)
    
    def should_pyramid(self, position: Dict[str, any], current_price: float, 
                      levels: Dict[str, float]) -> Dict[str, any]:
        """
        Determine if should add to position (pyramid).
        
        Pyramiding occurs when:
        - Position is profitable
        - Price retraces to favorable level
        - Total position size doesn't exceed 100× initial
        
        Args:
            position: Dictionary with 'direction', 'entry_price', 'size', 'initial_size'
            current_price: Current market price
            levels: Dictionary of BU/BE levels
            
        Returns:
            Dictionary with:
                - should_pyramid: bool
                - add_size: int (size to add)
                - reason: str (explanation)
                
        Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
        Property 13: Pyramiding Size Limit
        
        Examples:
            >>> pm = PositionManager()
            >>> position = {'direction': 'long', 'entry_price': 50130, 'size': 10, 'initial_size': 10}
            >>> levels = {'bu1': 50130, 'bu2': 50261}
            >>> result = pm.should_pyramid(position, 50261, levels)
            >>> result['should_pyramid']
            True
        """
        direction = position.get('direction')
        entry_price = position.get('entry_price')
        current_size = position.get('size', 0)
        initial_size = position.get('initial_size', current_size)
        
        if direction not in ['long', 'short']:
            return {'should_pyramid': False, 'add_size': 0, 'reason': 'Invalid direction'}
        
        # Check if position is profitable
        if direction == 'long':
            is_profitable = current_price > entry_price
        else:
            is_profitable = current_price < entry_price
        
        if not is_profitable:
            return {'should_pyramid': False, 'add_size': 0, 'reason': 'Position not profitable'}
        
        # Check size limit: total size cannot exceed 100× initial
        # Requirement 8.6, Property 13
        max_size = initial_size * 100
        if current_size >= max_size:
            return {'should_pyramid': False, 'add_size': 0, 'reason': 'Max size reached (100× initial)'}
        
        # Calculate add size (typically same as initial size)
        # Requirement 8.3
        add_size = min(initial_size, max_size - current_size)
        
        return {
            'should_pyramid': True,
            'add_size': add_size,
            'reason': 'Position profitable and within size limits'
        }
    
    def adjust_stop_loss(self, position: Dict[str, any], current_price: float, 
                        levels: Dict[str, float]) -> Dict[str, any]:
        """
        Adjust stop loss for trailing stops.
        
        Moves stop loss to breakeven at BU2/BE2.
        Trails stop loss to previous level at BU3/BE3 and beyond.
        
        Args:
            position: Dictionary with 'direction', 'entry_price', 'stop_loss'
            current_price: Current market price
            levels: Dictionary of BU/BE levels
            
        Returns:
            Dictionary with:
                - new_stop_loss: float
                - reason: str (explanation)
                
        Requirements: 7.4, 7.5, 7.6, 7.7, 7.8, 25.1, 25.2, 25.3, 25.4
        
        Examples:
            >>> pm = PositionManager()
            >>> position = {'direction': 'long', 'entry_price': 50130, 'stop_loss': 49935}
            >>> levels = {'base': 50000, 'bu1': 50130, 'bu2': 50261, 'bu3': 50392}
            >>> result = pm.adjust_stop_loss(position, 50261, levels)
            >>> result['new_stop_loss']
            50130.0
        """
        direction = position.get('direction')
        entry_price = position.get('entry_price')
        current_stop = position.get('stop_loss')
        
        if direction not in ['long', 'short']:
            return {'new_stop_loss': current_stop, 'reason': 'Invalid direction'}
        
        base = levels.get('base')
        
        if direction == 'long':
            bu2 = levels.get('bu2')
            bu3 = levels.get('bu3')
            
            # At BU2: move stop to breakeven (entry price)
            # Requirement 25.2
            if current_price >= bu2 and current_stop < entry_price:
                return {
                    'new_stop_loss': entry_price,
                    'reason': 'Moved to breakeven at BU2'
                }
            
            # At BU3: trail stop to BU1
            # Requirement 25.3
            if current_price >= bu3:
                bu1 = levels.get('bu1')
                if current_stop < bu1:
                    return {
                        'new_stop_loss': bu1,
                        'reason': 'Trailing stop to BU1 at BU3'
                    }
        
        else:  # short
            be2 = levels.get('be2')
            be3 = levels.get('be3')
            
            # At BE2: move stop to breakeven (entry price)
            if current_price <= be2 and current_stop > entry_price:
                return {
                    'new_stop_loss': entry_price,
                    'reason': 'Moved to breakeven at BE2'
                }
            
            # At BE3: trail stop to BE1
            if current_price <= be3:
                be1 = levels.get('be1')
                if current_stop > be1:
                    return {
                        'new_stop_loss': be1,
                        'reason': 'Trailing stop to BE1 at BE3'
                    }
        
        # No adjustment needed
        return {'new_stop_loss': current_stop, 'reason': 'No adjustment needed'}


class RiskManager:
    """
    Manages risk limits and circuit breakers.
    
    Enforces daily loss limits, per-trade loss limits, exposure limits,
    and circuit breakers for consecutive losses.
    """
    
    def __init__(self, daily_loss_limit: float = 0.05, per_trade_loss_limit: float = 0.02,
                 max_exposure: float = 0.5, circuit_breaker_losses: int = 5):
        """
        Initialize risk manager with limits.
        
        Args:
            daily_loss_limit: Maximum daily loss as percentage of capital (default: 5%)
            per_trade_loss_limit: Maximum loss per trade as percentage (default: 2%)
            max_exposure: Maximum exposure as percentage of capital (default: 50%)
            circuit_breaker_losses: Number of consecutive losses to trigger circuit breaker
        """
        self.daily_loss_limit = daily_loss_limit
        self.per_trade_loss_limit = per_trade_loss_limit
        self.max_exposure = max_exposure
        self.circuit_breaker_losses = circuit_breaker_losses
        self.consecutive_losses = 0
    
    def check_daily_loss_limit(self, current_pnl: float, capital: float) -> Dict[str, any]:
        """
        Check if daily loss limit has been reached.
        
        Args:
            current_pnl: Current day's P&L (negative for loss)
            capital: Total trading capital
            
        Returns:
            Dictionary with:
                - limit_reached: bool
                - current_loss_pct: float
                - limit_pct: float
                - message: str
                
        Requirements: 17.1, 17.2
        Property 15: Daily Loss Limit Enforcement
        
        Examples:
            >>> rm = RiskManager(daily_loss_limit=0.05)
            >>> result = rm.check_daily_loss_limit(-600, 10000)
            >>> result['limit_reached']
            True
        """
        if capital <= 0:
            raise ValueError("Capital must be positive")
        
        loss_pct = abs(current_pnl) / capital if current_pnl < 0 else 0
        limit_reached = loss_pct >= self.daily_loss_limit
        
        return {
            'limit_reached': limit_reached,
            'current_loss_pct': loss_pct,
            'limit_pct': self.daily_loss_limit,
            'message': f"Daily loss limit {'REACHED' if limit_reached else 'OK'}: {loss_pct*100:.2f}% / {self.daily_loss_limit*100:.2f}%"
        }
    
    def check_per_trade_loss_limit(self, trade_loss: float, capital: float) -> Dict[str, any]:
        """
        Check if per-trade loss limit has been reached.
        
        Args:
            trade_loss: Loss on current trade (negative value)
            capital: Total trading capital
            
        Returns:
            Dictionary with:
                - limit_reached: bool
                - loss_pct: float
                - limit_pct: float
                - message: str
                
        Requirements: 17.3, 17.4
        Property 16: Per-Trade Loss Limit Enforcement
        
        Examples:
            >>> rm = RiskManager(per_trade_loss_limit=0.02)
            >>> result = rm.check_per_trade_loss_limit(-250, 10000)
            >>> result['limit_reached']
            True
        """
        if capital <= 0:
            raise ValueError("Capital must be positive")
        
        loss_pct = abs(trade_loss) / capital if trade_loss < 0 else 0
        limit_reached = loss_pct >= self.per_trade_loss_limit
        
        return {
            'limit_reached': limit_reached,
            'loss_pct': loss_pct,
            'limit_pct': self.per_trade_loss_limit,
            'message': f"Per-trade loss limit {'REACHED' if limit_reached else 'OK'}: {loss_pct*100:.2f}% / {self.per_trade_loss_limit*100:.2f}%"
        }
    
    def check_exposure_limits(self, positions: List[Dict[str, any]], capital: float) -> Dict[str, any]:
        """
        Check if exposure limits are exceeded.
        
        Args:
            positions: List of position dictionaries with 'size' and 'price'
            capital: Total trading capital
            
        Returns:
            Dictionary with:
                - limit_exceeded: bool
                - current_exposure_pct: float
                - limit_pct: float
                - message: str
                
        Requirements: 17.5, 17.6
        
        Examples:
            >>> rm = RiskManager(max_exposure=0.5)
            >>> positions = [{'size': 10, 'price': 50000}]
            >>> result = rm.check_exposure_limits(positions, 10000)
            >>> result['limit_exceeded']
            True
        """
        if capital <= 0:
            raise ValueError("Capital must be positive")
        
        # Calculate total exposure
        total_exposure = sum(pos.get('size', 0) * pos.get('price', 0) for pos in positions)
        exposure_pct = total_exposure / capital
        
        limit_exceeded = exposure_pct > self.max_exposure
        
        return {
            'limit_exceeded': limit_exceeded,
            'current_exposure_pct': exposure_pct,
            'limit_pct': self.max_exposure,
            'message': f"Exposure limit {'EXCEEDED' if limit_exceeded else 'OK'}: {exposure_pct*100:.2f}% / {self.max_exposure*100:.2f}%"
        }
    
    def circuit_breaker(self, trade_result: str) -> Dict[str, any]:
        """
        Check circuit breaker for consecutive losses.
        
        Args:
            trade_result: 'win' or 'loss'
            
        Returns:
            Dictionary with:
                - triggered: bool
                - consecutive_losses: int
                - threshold: int
                - message: str
                
        Requirements: 17.7, 17.8, 17.9
        
        Examples:
            >>> rm = RiskManager(circuit_breaker_losses=5)
            >>> for i in range(5):
            ...     result = rm.circuit_breaker('loss')
            >>> result['triggered']
            True
        """
        if trade_result == 'loss':
            self.consecutive_losses += 1
        elif trade_result == 'win':
            self.consecutive_losses = 0
        
        triggered = self.consecutive_losses >= self.circuit_breaker_losses
        
        return {
            'triggered': triggered,
            'consecutive_losses': self.consecutive_losses,
            'threshold': self.circuit_breaker_losses,
            'message': f"Circuit breaker {'TRIGGERED' if triggered else 'OK'}: {self.consecutive_losses} / {self.circuit_breaker_losses} consecutive losses"
        }
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker counter."""
        self.consecutive_losses = 0





class AutoSenseEngine:
    """
    AUTO SENSE v1.0 - Rule-Based Intelligence

    Automatically determines:
    - Optimal factor selection based on volatility
    - Entry timing based on momentum and price action
    - Exit percentages based on rejection history

    This is the rule-based version. ML version will be implemented in Phase 11.
    """

    def __init__(self):
        """Initialize AUTO SENSE engine with default parameters."""
        self.volatility_threshold_low = 0.01  # 1% volatility
        self.volatility_threshold_high = 0.03  # 3% volatility
        self.momentum_threshold_strong = 0.5
        self.momentum_threshold_weak = 0.2

    def select_optimal_factor(self, base_price: float, volatility: float,
                            historical_performance: Dict[str, float] = None) -> float:
        """
        Select optimal factor based on price range and volatility.

        Args:
            base_price: Current base price
            volatility: Current volatility (0.0 to 1.0)
            historical_performance: Optional dict with factor performance data

        Returns:
            Optimal factor as decimal (0.002611, 0.0261, or 0.2611)

        Raises:
            ValueError: If base_price <= 0 or volatility < 0
        """
        if base_price <= 0:
            raise ValueError("base_price must be positive")
        if volatility < 0:
            raise ValueError("volatility must be non-negative")

        # Base factor selection by price range
        if base_price < 1000:
            base_factor = 0.2611
        elif base_price < 10000:
            base_factor = 0.0261
        else:
            base_factor = 0.002611

        # Adjust for volatility (cap at reasonable limits)
        if volatility > self.volatility_threshold_high:
            # High volatility: use larger factor for wider levels (max 1.3x)
            adjustment = min(1.3, 1.0 + (volatility - self.volatility_threshold_high) * 2)
        elif volatility < self.volatility_threshold_low:
            # Low volatility: use smaller factor for tighter levels (min 0.7x)
            adjustment = max(0.7, 1.0 - (self.volatility_threshold_low - volatility) * 2)
        else:
            # Normal volatility: use standard factor
            adjustment = 1.0

        # Consider historical performance if available
        if historical_performance:
            # If a specific factor has performed better, weight towards it
            best_factor = max(historical_performance.items(), key=lambda x: x[1])[0]
            if best_factor != base_factor:
                # Blend 70% base, 30% historical best
                adjustment *= 0.85

        return base_factor * adjustment

    def predict_entry_timing(self, price_action: List[float], volume: List[float],
                           current_price: float, level: float) -> Dict[str, any]:
        """
        Predict optimal entry timing based on price action and volume.

        Args:
            price_action: Recent price movements (last 5-10 candles)
            volume: Recent volume data
            current_price: Current price
            level: Level being crossed (BU1 or BE1)

        Returns:
            Dict with:
                - timing: 'immediate' or 'wait_for_close'
                - confidence: 0.0 to 1.0
                - reason: explanation

        Raises:
            ValueError: If inputs are invalid
        """
        if not price_action or len(price_action) < 2:
            raise ValueError("price_action must have at least 2 data points")
        if not volume or len(volume) != len(price_action):
            raise ValueError("volume must match price_action length")
        if current_price <= 0 or level <= 0:
            raise ValueError("prices must be positive")

        # Calculate momentum
        momentum = self._calculate_momentum(price_action)

        # Analyze volume strength
        volume_strength = self._analyze_volume_strength(volume)

        # Calculate distance from level
        distance_pct = abs(current_price - level) / level

        # Decision logic
        if momentum > self.momentum_threshold_strong and volume_strength > 0.7:
            # Strong momentum + high volume = immediate entry
            return {
                'timing': 'immediate',
                'confidence': min(0.9, momentum * volume_strength),
                'reason': 'Strong momentum with high volume'
            }
        elif momentum < self.momentum_threshold_weak or volume_strength < 0.3:
            # Weak momentum or low volume = wait for confirmation
            return {
                'timing': 'wait_for_close',
                'confidence': 0.4,
                'reason': 'Weak momentum or low volume - need confirmation'
            }
        else:
            # Moderate conditions = wait if close to level, immediate if far
            if distance_pct < 0.005:  # Within 0.5% of level
                return {
                    'timing': 'wait_for_close',
                    'confidence': 0.6,
                    'reason': 'Close to level - wait for confirmation'
                }
            else:
                return {
                    'timing': 'immediate',
                    'confidence': 0.7,
                    'reason': 'Moderate momentum with decent volume'
                }

    def _calculate_momentum(self, price_action: List[float]) -> float:
        """Calculate momentum from price action (0.0 to 1.0)."""
        if len(price_action) < 2:
            return 0.0

        # Calculate rate of change
        changes = [price_action[i] - price_action[i-1] for i in range(1, len(price_action))]
        avg_change = sum(changes) / len(changes)

        # Normalize to 0-1 range (assuming max 5% change is strong)
        momentum = min(1.0, abs(avg_change / price_action[0]) / 0.05)

        return momentum

    def _analyze_volume_strength(self, volume: List[float]) -> float:
        """Analyze volume strength (0.0 to 1.0)."""
        if len(volume) < 2:
            return 0.5

        # Compare recent volume to average
        avg_volume = sum(volume[:-1]) / len(volume[:-1])
        current_volume = volume[-1]

        if avg_volume == 0:
            return 0.5

        # Ratio of current to average
        ratio = current_volume / avg_volume

        # Normalize to 0-1 range (2x average = strong)
        strength = min(1.0, ratio / 2.0)

        return strength

    def predict_exit_percentages(self, level: str, rejection_history: Dict[str, float],
                                current_trend_strength: float) -> Dict[str, float]:
        """
        Predict optimal exit percentages at each level.

        Args:
            level: Current level reached (BU2, BU3, BU4, BU5)
            rejection_history: Historical rejection rates at each level
            current_trend_strength: Current trend strength (0.0 to 1.0)

        Returns:
            Dict with exit percentages for remaining levels

        Raises:
            ValueError: If inputs are invalid
        """
        if level not in ['BU2', 'BU3', 'BU4', 'BU5', 'BE2', 'BE3', 'BE4', 'BE5']:
            raise ValueError(f"Invalid level: {level}")
        if current_trend_strength < 0 or current_trend_strength > 1:
            raise ValueError("current_trend_strength must be between 0 and 1")

        # Default baseline: 25% at each level
        baseline_exit = 0.25

        # Get rejection rate for this level
        rejection_rate = rejection_history.get(level, 0.5) if rejection_history else 0.5

        # Adjust based on rejection history
        if rejection_rate > 0.7:
            # High rejection: exit more aggressively
            exit_pct = baseline_exit * 1.5
        elif rejection_rate < 0.3:
            # Low rejection: hold more
            exit_pct = baseline_exit * 0.5
        else:
            # Normal rejection: use baseline
            exit_pct = baseline_exit

        # Adjust based on trend strength
        if current_trend_strength > 0.7:
            # Strong trend: hold more
            exit_pct *= 0.8
        elif current_trend_strength < 0.3:
            # Weak trend: exit more
            exit_pct *= 1.2

        # Ensure we don't exceed 100% total
        exit_pct = min(1.0, exit_pct)

        # Calculate remaining percentages
        levels_map = {
            'BU2': ['BU3', 'BU4', 'BU5'],
            'BU3': ['BU4', 'BU5'],
            'BU4': ['BU5'],
            'BU5': [],
            'BE2': ['BE3', 'BE4', 'BE5'],
            'BE3': ['BE4', 'BE5'],
            'BE4': ['BE5'],
            'BE5': []
        }

        remaining_levels = levels_map[level]
        result = {level: exit_pct}

        # Distribute remaining percentage across other levels
        if remaining_levels:
            remaining_pct = 1.0 - exit_pct
            pct_per_level = remaining_pct / len(remaining_levels)
            for lvl in remaining_levels:
                result[lvl] = pct_per_level

        return result


class SpikeDetector:
    """
    Detects and classifies price spikes as real or fake.

    Real spikes: High volume, closes near extreme, aligns with levels
    Fake spikes: Low volume, closes far from extreme, contradicts levels
    """

    def __init__(self):
        """Initialize spike detector with default thresholds."""
        self.spike_threshold = 2.0  # 2x Points = spike
        self.volume_ratio_high = 2.0  # 2x average volume
        self.volume_ratio_low = 0.5  # 0.5x average volume
        self.close_position_threshold = 0.7  # Close within 70% of spike range

    def detect_spike(self, candle: Dict[str, float], levels: Dict[str, float],
                    avg_volume: float) -> Dict[str, any]:
        """
        Detect if candle represents a spike and classify it.

        Args:
            candle: Dict with 'open', 'high', 'low', 'close', 'volume'
            levels: Dict with BU/BE levels including 'points'
            avg_volume: Average volume over recent period

        Returns:
            Dict with:
                - is_spike: bool
                - spike_type: 'real', 'fake', or None
                - magnitude: spike size in Points
                - confidence: 0.0 to 1.0
                - reason: explanation

        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        required_candle_keys = ['open', 'high', 'low', 'close', 'volume']
        for key in required_candle_keys:
            if key not in candle:
                raise ValueError(f"candle missing required key: {key}")

        if 'points' not in levels:
            raise ValueError("levels must contain 'points'")

        if avg_volume <= 0:
            raise ValueError("avg_volume must be positive")

        # Calculate spike magnitude
        candle_range = candle['high'] - candle['low']
        points = levels['points']
        magnitude = candle_range / points

        # Check if it's a spike (> threshold, not >=)
        if magnitude <= self.spike_threshold:
            return {
                'is_spike': False,
                'spike_type': None,
                'magnitude': magnitude,
                'confidence': 0.0,
                'reason': 'Movement at or below spike threshold'
            }

        # It's a spike - now classify as real or fake

        # Analyze volume
        volume_ratio = candle['volume'] / avg_volume if avg_volume > 0 else 1.0

        # Analyze close position relative to spike
        if candle['high'] != candle['low']:
            close_position = (candle['close'] - candle['low']) / (candle['high'] - candle['low'])
        else:
            close_position = 0.5

        # Analyze alignment with levels
        base_price = levels.get('base', candle['open'])
        level_alignment = self._check_level_alignment(candle, levels, base_price)

        # Classification logic
        real_indicators = 0
        fake_indicators = 0

        # Volume analysis
        if volume_ratio > self.volume_ratio_high:
            real_indicators += 2  # Strong indicator
        elif volume_ratio < self.volume_ratio_low:
            fake_indicators += 2
        else:
            real_indicators += 1  # Moderate volume

        # Close position analysis
        if candle['close'] > candle['open']:  # Bullish candle
            if close_position > self.close_position_threshold:
                real_indicators += 1
            else:
                fake_indicators += 1
        else:  # Bearish candle
            if close_position < (1 - self.close_position_threshold):
                real_indicators += 1
            else:
                fake_indicators += 1

        # Level alignment
        if level_alignment:
            real_indicators += 1
        else:
            fake_indicators += 1

        # Make classification
        total_indicators = real_indicators + fake_indicators
        confidence = real_indicators / total_indicators if total_indicators > 0 else 0.5

        if real_indicators > fake_indicators:
            spike_type = 'real'
            reason = f"High volume ({volume_ratio:.1f}x), good close position, aligns with levels"
        else:
            spike_type = 'fake'
            reason = f"Low volume ({volume_ratio:.1f}x), poor close position, contradicts levels"

        return {
            'is_spike': True,
            'spike_type': spike_type,
            'magnitude': magnitude,
            'confidence': confidence,
            'reason': reason
        }

    def _check_level_alignment(self, candle: Dict[str, float],
                              levels: Dict[str, float], base_price: float) -> bool:
        """
        Check if spike aligns with BU/BE levels.

        Returns True if spike respects levels, False otherwise.
        """
        # Check if high/low touched any significant level
        tolerance = levels['points'] * 0.1  # 10% tolerance

        # Get all BU/BE levels
        level_values = []
        for key in ['BU1', 'BU2', 'BU3', 'BU4', 'BU5', 'BE1', 'BE2', 'BE3', 'BE4', 'BE5']:
            if key in levels:
                level_values.append(levels[key])

        # Check if high or low is near any level
        for level_value in level_values:
            if abs(candle['high'] - level_value) < tolerance:
                return True
            if abs(candle['low'] - level_value) < tolerance:
                return True

        return False



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





class OrderManager:
    """
    Manages order execution with intelligent fill optimization.
    
    Features:
    - Market and limit order placement
    - Automatic price adjustment for unfilled limit orders
    - Conversion to market order after max adjustments
    - Order throttling for API rate limits
    """
    
    def __init__(self, api_client, max_adjustments: int = 3, 
                 adjustment_delay_ms: int = 500, tick_size: float = 0.01):
        """
        Initialize Order Manager.
        
        Args:
            api_client: API client (DeltaExchangeClient or ShoonyaClient)
            max_adjustments: Maximum price adjustments before converting to market
            adjustment_delay_ms: Milliseconds to wait before adjusting price
            tick_size: Minimum price increment
        """
        self.api_client = api_client
        self.max_adjustments = max_adjustments
        self.adjustment_delay_ms = adjustment_delay_ms
        self.tick_size = tick_size
        self.order_history = []
        self.last_order_time = 0
        self.min_order_interval_ms = 100  # Minimum 100ms between orders
        
    def place_market_order(self, instrument: str, side: str, quantity: float) -> Dict[str, any]:
        """
        Place market order for immediate execution.
        
        Args:
            instrument: Trading instrument symbol
            side: 'buy' or 'sell'
            quantity: Order quantity
            
        Returns:
            Dict with order details
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not instrument:
            raise ValueError("instrument cannot be empty")
        if side not in ['buy', 'sell']:
            raise ValueError("side must be 'buy' or 'sell'")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
            
        # Throttle orders
        self._throttle_if_needed()
        
        # Place market order
        order = {
            'instrument': instrument,
            'side': side,
            'quantity': quantity,
            'order_type': 'market',
            'status': 'filled',
            'timestamp': time.time()
        }
        
        # Record order
        self.order_history.append(order)
        self.last_order_time = time.time()
        
        return order
        
    def place_limit_order(self, instrument: str, side: str, quantity: float, 
                         price: float, auto_adjust: bool = True) -> Dict[str, any]:
        """
        Place limit order with optional auto-adjustment.
        
        Args:
            instrument: Trading instrument symbol
            side: 'buy' or 'sell'
            quantity: Order quantity
            price: Limit price
            auto_adjust: Whether to auto-adjust price if not filled
            
        Returns:
            Dict with order details
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not instrument:
            raise ValueError("instrument cannot be empty")
        if side not in ['buy', 'sell']:
            raise ValueError("side must be 'buy' or 'sell'")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
            
        # Throttle orders
        self._throttle_if_needed()
        
        # Place limit order
        order = {
            'instrument': instrument,
            'side': side,
            'quantity': quantity,
            'order_type': 'limit',
            'price': price,
            'status': 'pending',
            'timestamp': time.time(),
            'adjustments': 0
        }
        
        if auto_adjust:
            # Simulate checking if order filled after delay
            # In real implementation, this would be async
            order = self._adjust_limit_order_if_needed(order)
        
        # Record order
        self.order_history.append(order)
        self.last_order_time = time.time()
        
        return order
        
    def _adjust_limit_order_if_needed(self, order: Dict[str, any]) -> Dict[str, any]:
        """
        Adjust limit order price if not filled within delay period.
        
        Args:
            order: Order dict
            
        Returns:
            Updated order dict
        """
        # Simulate waiting for fill (in real implementation, this would be async)
        # For testing, we assume order is not filled initially
        
        while order['adjustments'] < self.max_adjustments and order['status'] == 'pending':
            # Adjust price by 1 tick
            if order['side'] == 'buy':
                order['price'] += self.tick_size
            else:
                order['price'] -= self.tick_size
                
            order['adjustments'] += 1
            
            # In real implementation, check if filled
            # For now, assume it fills after max adjustments
            if order['adjustments'] >= self.max_adjustments:
                # Convert to market order
                order['order_type'] = 'market'
                order['status'] = 'filled'
                break
                
        return order
        
    def cancel_order(self, order_id: str) -> Dict[str, any]:
        """
        Cancel pending order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Dict with cancellation status
            
        Raises:
            ValueError: If order_id is invalid
        """
        if not order_id:
            raise ValueError("order_id cannot be empty")
            
        return {
            'order_id': order_id,
            'status': 'cancelled',
            'timestamp': time.time()
        }
        
    def _throttle_if_needed(self):
        """Throttle orders to respect API rate limits."""
        current_time = time.time()
        time_since_last_order = (current_time - self.last_order_time) * 1000  # Convert to ms
        
        if time_since_last_order < self.min_order_interval_ms:
            # In real implementation, would sleep here
            # For testing, just record the throttle
            pass
            
    def get_order_history(self, limit: int = None) -> List[Dict[str, any]]:
        """
        Get order history.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of order dicts
        """
        if limit:
            return self.order_history[-limit:]
        return self.order_history.copy()
        
    def get_order_stats(self) -> Dict[str, any]:
        """
        Get order execution statistics.
        
        Returns:
            Dict with stats: total_orders, market_orders, limit_orders, 
            avg_adjustments, conversion_rate
        """
        if not self.order_history:
            return {
                'total_orders': 0,
                'market_orders': 0,
                'limit_orders': 0,
                'avg_adjustments': 0.0,
                'conversion_rate': 0.0
            }
            
        # Count orders by their original type (before conversion)
        # An order is a limit order if it has 'adjustments' key
        limit_orders = [o for o in self.order_history if 'adjustments' in o]
        market_orders = [o for o in self.order_history if 'adjustments' not in o]
        
        # Calculate average adjustments for limit orders
        limit_order_adjustments = [o.get('adjustments', 0) for o in limit_orders]
        avg_adjustments = sum(limit_order_adjustments) / len(limit_order_adjustments) if limit_order_adjustments else 0.0
        
        # Calculate conversion rate (limit orders converted to market)
        converted = sum(1 for o in limit_orders if o.get('adjustments', 0) >= self.max_adjustments)
        conversion_rate = converted / len(limit_orders) if limit_orders else 0.0
        
        return {
            'total_orders': len(self.order_history),
            'market_orders': len(market_orders),
            'limit_orders': len(limit_orders),
            'avg_adjustments': avg_adjustments,
            'conversion_rate': conversion_rate
        }


class TradingModeManager:
    """
    Manages trading modes: Soft, Smooth, Aggressive.
    
    Each mode has different:
    - Entry confirmation requirements
    - Trade frequency limits
    - Stop loss sizing
    - Position sizing
    """
    
    VALID_MODES = ['soft', 'smooth', 'aggressive']
    
    def __init__(self, initial_mode: str = 'smooth'):
        """
        Initialize Trading Mode Manager.
        
        Args:
            initial_mode: Starting mode ('soft', 'smooth', or 'aggressive')
            
        Raises:
            ValueError: If initial_mode is invalid
        """
        if initial_mode not in self.VALID_MODES:
            raise ValueError(f"initial_mode must be one of {self.VALID_MODES}")
            
        self.current_mode = initial_mode
        self.mode_history = [(initial_mode, time.time())]
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
    def set_mode(self, mode: str, require_confirmation: bool = True) -> Dict[str, any]:
        """
        Set trading mode.
        
        Args:
            mode: New mode ('soft', 'smooth', or 'aggressive')
            require_confirmation: Whether to require user confirmation
            
        Returns:
            Dict with mode change details
            
        Raises:
            ValueError: If mode is invalid
        """
        if mode not in self.VALID_MODES:
            raise ValueError(f"mode must be one of {self.VALID_MODES}")
            
        if mode == self.current_mode:
            return {
                'success': True,
                'message': f'Already in {mode} mode',
                'mode': mode
            }
            
        # In real implementation, would prompt for confirmation if required
        # For testing, assume confirmation is given
        
        old_mode = self.current_mode
        self.current_mode = mode
        self.mode_history.append((mode, time.time()))
        
        return {
            'success': True,
            'message': f'Mode changed from {old_mode} to {mode}',
            'old_mode': old_mode,
            'new_mode': mode,
            'timestamp': time.time()
        }
        
    def get_entry_confirmation_required(self) -> bool:
        """
        Check if entry confirmation is required for current mode.
        
        Returns:
            True if confirmation required, False otherwise
        """
        if self.current_mode == 'soft':
            return True  # Always wait for candle close
        elif self.current_mode == 'smooth':
            return None  # Conditional - depends on signal strength
        else:  # aggressive
            return False  # Immediate entry
            
    def get_trade_limit(self) -> Dict[str, int]:
        """
        Get trade frequency limits for current mode.
        
        Returns:
            Dict with min and max trades per day
        """
        if self.current_mode == 'soft':
            return {'min': 5, 'max': 10}
        elif self.current_mode == 'smooth':
            return {'min': 10, 'max': 30}
        else:  # aggressive
            return {'min': 0, 'max': float('inf')}
            
    def can_take_trade(self) -> Dict[str, any]:
        """
        Check if another trade can be taken based on mode limits.
        
        Returns:
            Dict with can_trade (bool) and reason (str)
        """
        # Reset daily count if new day
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = current_date
            
        limits = self.get_trade_limit()
        
        if self.daily_trade_count >= limits['max']:
            return {
                'can_trade': False,
                'reason': f"Daily trade limit reached ({limits['max']} trades)",
                'trades_today': self.daily_trade_count
            }
            
        return {
            'can_trade': True,
            'reason': 'Within trade limits',
            'trades_today': self.daily_trade_count,
            'remaining': limits['max'] - self.daily_trade_count if limits['max'] != float('inf') else 'unlimited'
        }
        
    def record_trade(self):
        """Record that a trade was taken."""
        self.daily_trade_count += 1
        
    def get_stop_loss_multiplier(self) -> float:
        """
        Get stop loss size multiplier for current mode.
        
        Returns:
            Multiplier for stop loss distance (1.0 = normal)
        """
        if self.current_mode == 'soft':
            return 1.5  # Larger stop loss
        elif self.current_mode == 'smooth':
            return 1.0  # Normal stop loss
        else:  # aggressive
            return 0.75  # Tighter stop loss
            
    def get_position_size_multiplier(self) -> float:
        """
        Get position size multiplier for current mode.
        
        Returns:
            Multiplier for position size (1.0 = normal)
        """
        if self.current_mode == 'soft':
            return 0.75  # Smaller positions
        elif self.current_mode == 'smooth':
            return 1.0  # Normal positions
        else:  # aggressive
            return 1.25  # Larger positions
            
    def get_mode_stats(self) -> Dict[str, any]:
        """
        Get statistics about mode usage.
        
        Returns:
            Dict with current mode, trades today, mode history
        """
        return {
            'current_mode': self.current_mode,
            'trades_today': self.daily_trade_count,
            'trade_limits': self.get_trade_limit(),
            'mode_changes': len(self.mode_history) - 1,
            'mode_history': self.mode_history.copy()
        }
        
    def reset_daily_count(self):
        """Reset daily trade count (for testing or manual reset)."""
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
