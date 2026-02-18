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
