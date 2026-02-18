"""
Property-Based Tests for Database Module

This module contains property-based tests using Hypothesis to verify
the correctness properties of the DatabaseManager class.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import tempfile
import shutil
from datetime import datetime
from hypothesis import given, strategies as st, settings, HealthCheck
from src.database import DatabaseManager


# Strategy for generating valid trade data
def trade_data_strategy():
    return st.fixed_dictionaries({
        'id': st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-')),
        'timestamp': st.just(datetime.now().isoformat()),
        'instrument': st.sampled_from(['BTC-USD', 'ETH-USD', 'NIFTY', 'BANKNIFTY']),
        'direction': st.sampled_from(['long', 'short']),
        'entry_price': st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        'quantity': st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
        'levels_used': st.just('{}'),
        'timeframe': st.sampled_from(['1m', '5m', '15m']),
        'mode': st.sampled_from(['soft', 'smooth', 'aggressive']),
        'entry_time': st.just(datetime.now().isoformat())
    })


# Strategy for generating valid level data
def levels_data_strategy():
    return st.builds(
        lambda base_price, instrument, timeframe: {
            'id': f'level_{hash((base_price, instrument, timeframe)) % 100000}',
            'timestamp': datetime.now().isoformat(),
            'instrument': instrument,
            'timeframe': timeframe,
            'base_price': base_price,
            'factor': 0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611),
            'points': round(base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)), 2),
            'bu1': round(base_price + base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 1, 2),
            'bu2': round(base_price + base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 2, 2),
            'bu3': round(base_price + base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 3, 2),
            'bu4': round(base_price + base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 4, 2),
            'bu5': round(base_price + base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 5, 2),
            'be1': round(base_price - base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 1, 2),
            'be2': round(base_price - base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 2, 2),
            'be3': round(base_price - base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 3, 2),
            'be4': round(base_price - base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 4, 2),
            'be5': round(base_price - base_price * (0.002611 if base_price >= 10000 else (0.02611 if base_price >= 1000 else 0.2611)) * 5, 2),
        },
        base_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        instrument=st.sampled_from(['BTC-USD', 'ETH-USD', 'NIFTY']),
        timeframe=st.sampled_from(['1m', '5m', '15m'])
    )


# Property 19: Database Round Trip for Trades
# **Validates: Requirement 18.1**
@given(trade_data=trade_data_strategy())
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_19_trade_database_round_trip(trade_data):
    """
    Property 19: Database Round Trip
    
    For any trade record, storing it to trades.db then retrieving it
    should produce an equivalent trade record.
    
    **Validates: Requirement 18.1**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        # Insert trade
        result = db_manager.insert_trade(trade_data)
        assert result is True, "Trade insertion should succeed"
        
        # Retrieve trade
        trades = db_manager.get_trades()
        assert len(trades) == 1, "Should retrieve exactly one trade"
        
        retrieved_trade = trades[0]
        
        # Verify all fields match
        assert retrieved_trade['id'] == trade_data['id']
        assert retrieved_trade['instrument'] == trade_data['instrument']
        assert retrieved_trade['direction'] == trade_data['direction']
        assert retrieved_trade['entry_price'] == trade_data['entry_price']
        assert retrieved_trade['quantity'] == trade_data['quantity']
        assert retrieved_trade['timeframe'] == trade_data['timeframe']
        assert retrieved_trade['mode'] == trade_data['mode']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property 20: Level Database Round Trip
# **Validates: Requirement 18.4**
@given(levels_data=levels_data_strategy())
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_20_level_database_round_trip(levels_data):
    """
    Property 20: Level Database Round Trip
    
    For any level record, storing it to levels.db then retrieving it
    should produce an equivalent level record.
    
    **Validates: Requirement 18.4**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        # Insert levels
        result = db_manager.insert_levels(levels_data)
        assert result is True, "Levels insertion should succeed"
        
        # Retrieve levels
        levels = db_manager.get_levels(
            levels_data['instrument'],
            levels_data['timeframe']
        )
        assert len(levels) == 1, "Should retrieve exactly one level record"
        
        retrieved_levels = levels[0]
        
        # Verify all fields match
        assert retrieved_levels['id'] == levels_data['id']
        assert retrieved_levels['instrument'] == levels_data['instrument']
        assert retrieved_levels['timeframe'] == levels_data['timeframe']
        assert retrieved_levels['base_price'] == levels_data['base_price']
        assert retrieved_levels['factor'] == levels_data['factor']
        assert retrieved_levels['points'] == levels_data['points']
        assert retrieved_levels['bu1'] == levels_data['bu1']
        assert retrieved_levels['bu5'] == levels_data['bu5']
        assert retrieved_levels['be1'] == levels_data['be1']
        assert retrieved_levels['be5'] == levels_data['be5']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Config Type Preservation
# **Validates: Requirement 18.6**
@given(
    int_value=st.integers(min_value=1, max_value=1000),
    float_value=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
    bool_value=st.booleans(),
    str_value=st.text(min_size=1, max_size=50)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_config_type_preservation(int_value, float_value, bool_value, str_value):
    """
    Property: Config Type Preservation
    
    For any configuration value, storing it with a type then retrieving it
    should return the value with the correct type.
    
    **Validates: Requirement 18.6**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        # Set config values
        db_manager.set_config('test_int', int_value, 'int')
        db_manager.set_config('test_float', float_value, 'float')
        db_manager.set_config('test_bool', bool_value, 'bool')
        db_manager.set_config('test_str', str_value, 'str')
        
        # Retrieve and verify types
        retrieved_int = db_manager.get_config('test_int')
        assert retrieved_int == int_value
        assert isinstance(retrieved_int, int)
        
        retrieved_float = db_manager.get_config('test_float')
        assert abs(retrieved_float - float_value) < 0.0001
        assert isinstance(retrieved_float, float)
        
        retrieved_bool = db_manager.get_config('test_bool')
        assert retrieved_bool == bool_value
        assert isinstance(retrieved_bool, bool)
        
        retrieved_str = db_manager.get_config('test_str')
        assert retrieved_str == str_value
        assert isinstance(retrieved_str, str)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Position Update Idempotency
# **Validates: Requirement 18.5**
@given(
    instrument=st.sampled_from(['BTC-USD', 'ETH-USD', 'NIFTY']),
    entry_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    quantity=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_position_update_idempotency(instrument, entry_price, quantity):
    """
    Property: Position Update Idempotency
    
    For any position, inserting it multiple times with the same ID
    should result in only one position record (update, not duplicate).
    
    **Validates: Requirement 18.5**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        position_data = {
            'id': 'test_position',
            'instrument': instrument,
            'direction': 'long',
            'entry_price': entry_price,
            'current_price': entry_price,
            'quantity': quantity,
            'initial_quantity': quantity,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': entry_price * 0.95,
            'unrealized_pnl': 0.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        
        # Insert position multiple times
        db_manager.insert_position(position_data)
        db_manager.insert_position(position_data)
        db_manager.insert_position(position_data)
        
        # Should only have one position
        positions = db_manager.get_positions()
        assert len(positions) == 1, "Multiple inserts with same ID should result in one record"
        assert positions[0]['id'] == 'test_position'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Pattern Success Rate Bounds
# **Validates: Requirement 18.2**
@given(
    pattern_type=st.sampled_from(['level_rejection', 'breakout', 'reversal']),
    level=st.sampled_from(['BU1', 'BU2', 'BU3', 'BU4', 'BU5', 'BE1', 'BE2', 'BE3', 'BE4', 'BE5']),
    success_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_pattern_success_rate_bounds(pattern_type, level, success_rate):
    """
    Property: Pattern Success Rate Bounds
    
    For any pattern, the success rate should remain between 0.0 and 1.0
    after storing and retrieving from the database.
    
    **Validates: Requirement 18.2**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        pattern_data = {
            'id': f'pattern_{hash((pattern_type, level)) % 100000}',
            'pattern_type': pattern_type,
            'level': level,
            'success_rate': success_rate,
            'conditions': '{}',
            'timestamp': datetime.now().isoformat()
        }
        
        db_manager.insert_pattern(pattern_data)
        
        patterns = db_manager.get_patterns()
        assert len(patterns) == 1
        
        retrieved_rate = patterns[0]['success_rate']
        assert 0.0 <= retrieved_rate <= 1.0, "Success rate should be between 0 and 1"
        assert abs(retrieved_rate - success_rate) < 0.0001, "Success rate should be preserved"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Performance Metrics Consistency
# **Validates: Requirement 18.3**
@given(
    total_trades=st.integers(min_value=1, max_value=1000),
    win_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_performance_metrics_consistency(total_trades, win_rate):
    """
    Property: Performance Metrics Consistency
    
    For any performance record, winning_trades + losing_trades should
    equal total_trades when both are specified.
    
    **Validates: Requirement 18.3**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        winning_trades = int(total_trades * win_rate)
        losing_trades = total_trades - winning_trades
        
        perf_data = {
            'date': '2024-01-15',
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': 1000.0,
            'max_drawdown': -100.0
        }
        
        db_manager.insert_performance(perf_data)
        
        performance = db_manager.get_performance()
        assert len(performance) == 1
        
        retrieved = performance[0]
        assert retrieved['total_trades'] == total_trades
        assert retrieved['winning_trades'] + retrieved['losing_trades'] == total_trades
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Trade Filtering Correctness
# **Validates: Requirement 18.1**
@given(
    trades_data=st.lists(
        trade_data_strategy(),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_trade_filtering_correctness(trades_data):
    """
    Property: Trade Filtering Correctness
    
    For any set of trades, filtering by instrument should return only
    trades for that instrument.
    
    **Validates: Requirement 18.1**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        # Make IDs unique
        for i, trade in enumerate(trades_data):
            trade['id'] = f"{trade['id']}_{i}"
            db_manager.insert_trade(trade)
        
        # Get all unique instruments
        instruments = set(trade['instrument'] for trade in trades_data)
        
        for instrument in instruments:
            filtered_trades = db_manager.get_trades(instrument=instrument)
            
            # All returned trades should be for the requested instrument
            assert all(t['instrument'] == instrument for t in filtered_trades)
            
            # Count should match
            expected_count = sum(1 for t in trades_data if t['instrument'] == instrument)
            assert len(filtered_trades) == expected_count
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# Property: Database Isolation
# **Validates: Requirements 18.1-18.6**
@given(
    trade_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    pattern_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_database_isolation(trade_id, pattern_id):
    """
    Property: Database Isolation
    
    For any operations on different databases, they should not interfere
    with each other. Inserting into trades.db should not affect patterns.db.
    
    **Validates: Requirements 18.1-18.6**
    """
    temp_dir = tempfile.mkdtemp()
    try:
        db_manager = DatabaseManager(db_dir=temp_dir)
        
        # Insert trade
        trade_data = {
            'id': trade_id,
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'quantity': 0.1,
            'levels_used': '{}',
            'timeframe': '5m',
            'mode': 'smooth',
            'entry_time': datetime.now().isoformat()
        }
        db_manager.insert_trade(trade_data)
        
        # Insert pattern
        pattern_data = {
            'id': pattern_id,
            'pattern_type': 'test',
            'level': 'BU1',
            'success_rate': 0.5,
            'conditions': '{}',
            'timestamp': datetime.now().isoformat()
        }
        db_manager.insert_pattern(pattern_data)
        
        # Verify both exist independently
        trades = db_manager.get_trades()
        patterns = db_manager.get_patterns()
        
        assert len(trades) == 1
        assert len(patterns) == 1
        assert trades[0]['id'] == trade_id
        assert patterns[0]['id'] == pattern_id
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
