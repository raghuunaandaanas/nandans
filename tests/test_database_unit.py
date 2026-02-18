"""
Unit Tests for Database Module

This module contains unit tests for the DatabaseManager class,
testing specific examples and edge cases for database operations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from src.database import DatabaseManager


@pytest.fixture
def temp_db_dir():
    """Create a temporary directory for test databases"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def db_manager(temp_db_dir):
    """Create a DatabaseManager instance with temporary directory"""
    return DatabaseManager(db_dir=temp_db_dir)


class TestDatabaseInitialization:
    """Test database initialization and schema creation"""
    
    def test_database_files_created(self, db_manager, temp_db_dir):
        """Test that all database files are created"""
        db_dir = Path(temp_db_dir)
        
        assert (db_dir / "trades.db").exists()
        assert (db_dir / "patterns.db").exists()
        assert (db_dir / "performance.db").exists()
        assert (db_dir / "levels.db").exists()
        assert (db_dir / "positions.db").exists()
        assert (db_dir / "config.db").exists()
    
    def test_default_config_values(self, db_manager):
        """Test that default configuration values are set"""
        config = db_manager.get_all_config()
        
        assert config['max_daily_loss_percent'] == 5.0
        assert config['max_per_trade_loss_percent'] == 1.0
        assert config['initial_position_size'] == 0.01
        assert config['max_pyramiding_multiplier'] == 100
        assert config['trading_mode'] == 'smooth'
        assert config['paper_trading'] is True


class TestTradeOperations:
    """Test trade database operations"""
    
    def test_insert_trade(self, db_manager):
        """Test inserting a trade record"""
        trade_data = {
            'id': 'trade_001',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'quantity': 0.1,
            'profit_loss': 100.0,
            'levels_used': '{"bu1": 50500, "bu2": 51000}',
            'entry_level': 'BU1',
            'exit_level': 'BU2',
            'timeframe': '5m',
            'mode': 'smooth',
            'stop_loss': 49500.0,
            'entry_time': datetime.now().isoformat()
        }
        
        result = db_manager.insert_trade(trade_data)
        assert result is True
        
        # Verify trade was inserted
        trades = db_manager.get_trades()
        assert len(trades) == 1
        assert trades[0]['id'] == 'trade_001'
        assert trades[0]['instrument'] == 'BTC-USD'
        assert trades[0]['profit_loss'] == 100.0
    
    def test_get_trades_by_instrument(self, db_manager):
        """Test filtering trades by instrument"""
        # Insert multiple trades
        for i, instrument in enumerate(['BTC-USD', 'ETH-USD', 'BTC-USD']):
            trade_data = {
                'id': f'trade_{i:03d}',
                'timestamp': datetime.now().isoformat(),
                'instrument': instrument,
                'direction': 'long',
                'entry_price': 50000.0,
                'quantity': 0.1,
                'levels_used': '{}',
                'timeframe': '5m',
                'mode': 'smooth',
                'entry_time': datetime.now().isoformat()
            }
            db_manager.insert_trade(trade_data)
        
        # Get BTC trades only
        btc_trades = db_manager.get_trades(instrument='BTC-USD')
        assert len(btc_trades) == 2
        assert all(t['instrument'] == 'BTC-USD' for t in btc_trades)
    
    def test_trade_with_pyramiding(self, db_manager):
        """Test inserting trade with pyramiding information"""
        trade_data = {
            'id': 'trade_pyramid',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'quantity': 0.5,
            'levels_used': '{}',
            'timeframe': '5m',
            'mode': 'aggressive',
            'was_pyramided': 1,
            'pyramid_count': 3,
            'entry_time': datetime.now().isoformat()
        }
        
        result = db_manager.insert_trade(trade_data)
        assert result is True
        
        trades = db_manager.get_trades()
        assert trades[0]['was_pyramided'] == 1
        assert trades[0]['pyramid_count'] == 3


class TestPatternOperations:
    """Test pattern database operations"""
    
    def test_insert_pattern(self, db_manager):
        """Test inserting a pattern record"""
        pattern_data = {
            'id': 'pattern_001',
            'pattern_type': 'level_rejection',
            'level': 'BU3',
            'success_rate': 0.75,
            'conditions': '{"volume": "high", "momentum": "strong"}',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'timeframe': '5m'
        }
        
        result = db_manager.insert_pattern(pattern_data)
        assert result is True
        
        patterns = db_manager.get_patterns()
        assert len(patterns) == 1
        assert patterns[0]['pattern_type'] == 'level_rejection'
        assert patterns[0]['success_rate'] == 0.75
    
    def test_update_pattern(self, db_manager):
        """Test updating pattern success rate"""
        # Insert pattern
        pattern_data = {
            'id': 'pattern_update',
            'pattern_type': 'breakout',
            'level': 'BU1',
            'success_rate': 0.60,
            'conditions': '{}',
            'timestamp': datetime.now().isoformat()
        }
        db_manager.insert_pattern(pattern_data)
        
        # Update pattern
        result = db_manager.update_pattern('pattern_update', 0.80, 10)
        assert result is True
        
        patterns = db_manager.get_patterns()
        assert patterns[0]['success_rate'] == 0.80
        assert patterns[0]['occurrences'] == 10
    
    def test_get_patterns_by_level(self, db_manager):
        """Test filtering patterns by level"""
        # Insert patterns at different levels
        for i, level in enumerate(['BU1', 'BU2', 'BU1']):
            pattern_data = {
                'id': f'pattern_{i:03d}',
                'pattern_type': 'test',
                'level': level,
                'success_rate': 0.5,
                'conditions': '{}',
                'timestamp': datetime.now().isoformat()
            }
            db_manager.insert_pattern(pattern_data)
        
        bu1_patterns = db_manager.get_patterns(level='BU1')
        assert len(bu1_patterns) == 2
        assert all(p['level'] == 'BU1' for p in bu1_patterns)


class TestPerformanceOperations:
    """Test performance database operations"""
    
    def test_insert_performance(self, db_manager):
        """Test inserting performance metrics"""
        perf_data = {
            'date': '2024-01-15',
            'total_trades': 25,
            'winning_trades': 20,
            'losing_trades': 5,
            'win_rate': 0.80,
            'total_pnl': 1500.0,
            'profit_factor': 3.5,
            'sharpe_ratio': 2.1,
            'max_drawdown': -200.0,
            'avg_win': 100.0,
            'avg_loss': -40.0,
            'best_trade': 250.0,
            'worst_trade': -80.0
        }
        
        result = db_manager.insert_performance(perf_data)
        assert result is True
        
        performance = db_manager.get_performance()
        assert len(performance) == 1
        assert performance[0]['win_rate'] == 0.80
        assert performance[0]['total_pnl'] == 1500.0
    
    def test_update_performance_same_date(self, db_manager):
        """Test that inserting performance for same date updates the record"""
        perf_data = {
            'date': '2024-01-15',
            'total_trades': 10,
            'win_rate': 0.70,
            'total_pnl': 500.0,
            'max_drawdown': -50.0
        }
        db_manager.insert_performance(perf_data)
        
        # Update with new data for same date
        perf_data['total_trades'] = 15
        perf_data['total_pnl'] = 750.0
        db_manager.insert_performance(perf_data)
        
        performance = db_manager.get_performance()
        assert len(performance) == 1  # Should still be one record
        assert performance[0]['total_trades'] == 15
        assert performance[0]['total_pnl'] == 750.0


class TestLevelOperations:
    """Test level database operations"""
    
    def test_insert_levels(self, db_manager):
        """Test inserting level calculations"""
        levels_data = {
            'id': 'levels_001',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'timeframe': '5m',
            'base_price': 50000.0,
            'factor': 0.002611,
            'points': 130.55,
            'bu1': 50130.55,
            'bu2': 50261.10,
            'bu3': 50391.65,
            'bu4': 50522.20,
            'bu5': 50652.75,
            'be1': 49869.45,
            'be2': 49738.90,
            'be3': 49608.35,
            'be4': 49477.80,
            'be5': 49347.25
        }
        
        result = db_manager.insert_levels(levels_data)
        assert result is True
        
        levels = db_manager.get_levels('BTC-USD', '5m')
        assert len(levels) == 1
        assert levels[0]['base_price'] == 50000.0
        assert levels[0]['bu1'] == 50130.55
    
    def test_get_most_recent_levels(self, db_manager):
        """Test retrieving most recent levels"""
        # Insert multiple level records
        for i in range(3):
            levels_data = {
                'id': f'levels_{i:03d}',
                'timestamp': f'2024-01-15T10:{i:02d}:00',
                'instrument': 'BTC-USD',
                'timeframe': '5m',
                'base_price': 50000.0 + i * 100,
                'factor': 0.002611,
                'points': 130.55,
                'bu1': 50130.55,
                'bu2': 50261.10,
                'bu3': 50391.65,
                'bu4': 50522.20,
                'bu5': 50652.75,
                'be1': 49869.45,
                'be2': 49738.90,
                'be3': 49608.35,
                'be4': 49477.80,
                'be5': 49347.25
            }
            db_manager.insert_levels(levels_data)
        
        # Get most recent
        levels = db_manager.get_levels('BTC-USD', '5m', limit=1)
        assert len(levels) == 1
        assert levels[0]['base_price'] == 50200.0  # Most recent


class TestPositionOperations:
    """Test position database operations"""
    
    def test_insert_position(self, db_manager):
        """Test inserting a position"""
        position_data = {
            'id': 'pos_001',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50500.0,
            'quantity': 0.1,
            'initial_quantity': 0.05,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 50.0,
            'levels_used': '{"bu1": 50130.55}',
            'last_updated': datetime.now().isoformat()
        }
        
        result = db_manager.insert_position(position_data)
        assert result is True
        
        positions = db_manager.get_positions()
        assert len(positions) == 1
        assert positions[0]['instrument'] == 'BTC-USD'
        assert positions[0]['unrealized_pnl'] == 50.0
    
    def test_update_position(self, db_manager):
        """Test updating an existing position"""
        position_data = {
            'id': 'pos_update',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50500.0,
            'quantity': 0.1,
            'initial_quantity': 0.1,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 50.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        db_manager.insert_position(position_data)
        
        # Update position
        position_data['current_price'] = 51000.0
        position_data['unrealized_pnl'] = 100.0
        db_manager.insert_position(position_data)
        
        positions = db_manager.get_positions()
        assert len(positions) == 1  # Should still be one position
        assert positions[0]['current_price'] == 51000.0
        assert positions[0]['unrealized_pnl'] == 100.0
    
    def test_delete_position(self, db_manager):
        """Test deleting a position"""
        position_data = {
            'id': 'pos_delete',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50500.0,
            'quantity': 0.1,
            'initial_quantity': 0.1,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 50.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        db_manager.insert_position(position_data)
        
        result = db_manager.delete_position('pos_delete')
        assert result is True
        
        positions = db_manager.get_positions()
        assert len(positions) == 0
    
    def test_get_positions_by_instrument(self, db_manager):
        """Test filtering positions by instrument"""
        for i, instrument in enumerate(['BTC-USD', 'ETH-USD']):
            position_data = {
                'id': f'pos_{i:03d}',
                'instrument': instrument,
                'direction': 'long',
                'entry_price': 50000.0,
                'current_price': 50500.0,
                'quantity': 0.1,
                'initial_quantity': 0.1,
                'entry_time': datetime.now().isoformat(),
                'stop_loss': 49500.0,
                'unrealized_pnl': 50.0,
                'levels_used': '{}',
                'last_updated': datetime.now().isoformat()
            }
            db_manager.insert_position(position_data)
        
        btc_positions = db_manager.get_positions(instrument='BTC-USD')
        assert len(btc_positions) == 1
        assert btc_positions[0]['instrument'] == 'BTC-USD'


class TestConfigOperations:
    """Test configuration database operations"""
    
    def test_get_config(self, db_manager):
        """Test retrieving configuration values"""
        max_loss = db_manager.get_config('max_daily_loss_percent')
        assert max_loss == 5.0
        
        paper_trading = db_manager.get_config('paper_trading')
        assert paper_trading is True
        
        mode = db_manager.get_config('trading_mode')
        assert mode == 'smooth'
    
    def test_set_config(self, db_manager):
        """Test setting configuration values"""
        result = db_manager.set_config('max_daily_loss_percent', 10.0, 'float')
        assert result is True
        
        value = db_manager.get_config('max_daily_loss_percent')
        assert value == 10.0
    
    def test_config_type_conversion(self, db_manager):
        """Test that config values are converted to correct types"""
        db_manager.set_config('test_int', 42, 'int')
        db_manager.set_config('test_float', 3.14, 'float')
        db_manager.set_config('test_bool', True, 'bool')
        db_manager.set_config('test_str', 'hello', 'str')
        
        assert db_manager.get_config('test_int') == 42
        assert isinstance(db_manager.get_config('test_int'), int)
        
        assert db_manager.get_config('test_float') == 3.14
        assert isinstance(db_manager.get_config('test_float'), float)
        
        assert db_manager.get_config('test_bool') is True
        assert isinstance(db_manager.get_config('test_bool'), bool)
        
        assert db_manager.get_config('test_str') == 'hello'
        assert isinstance(db_manager.get_config('test_str'), str)
    
    def test_get_all_config(self, db_manager):
        """Test retrieving all configuration values"""
        config = db_manager.get_all_config()
        
        assert isinstance(config, dict)
        assert 'max_daily_loss_percent' in config
        assert 'paper_trading' in config
        assert 'trading_mode' in config


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_get_nonexistent_config(self, db_manager):
        """Test getting a config key that doesn't exist"""
        value = db_manager.get_config('nonexistent_key')
        assert value is None
    
    def test_empty_database_queries(self, db_manager):
        """Test querying empty databases"""
        assert db_manager.get_trades() == []
        assert db_manager.get_patterns() == []
        assert db_manager.get_performance() == []
        assert db_manager.get_positions() == []
    
    def test_insert_with_missing_optional_fields(self, db_manager):
        """Test inserting records with minimal required fields"""
        trade_data = {
            'id': 'trade_minimal',
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
        
        result = db_manager.insert_trade(trade_data)
        assert result is True
        
        trades = db_manager.get_trades()
        assert len(trades) == 1
    
    def test_get_trade_by_id(self, db_manager):
        """Test retrieving a specific trade by ID"""
        trade_data = {
            'id': 'trade_specific',
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
        
        # Get by ID
        trade = db_manager.get_trade_by_id('trade_specific')
        assert trade is not None
        assert trade['id'] == 'trade_specific'
        assert trade['instrument'] == 'BTC-USD'
        
        # Get non-existent ID
        trade = db_manager.get_trade_by_id('nonexistent')
        assert trade is None
    
    def test_update_position_method(self, db_manager):
        """Test the update_position method"""
        # Insert initial position
        position_data = {
            'id': 'pos_update_method',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50500.0,
            'quantity': 0.1,
            'initial_quantity': 0.1,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 50.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        db_manager.insert_position(position_data)
        
        # Update specific fields
        updates = {
            'current_price': 51000.0,
            'unrealized_pnl': 100.0,
            'quantity': 0.2
        }
        result = db_manager.update_position('pos_update_method', updates)
        assert result is True
        
        # Verify updates
        positions = db_manager.get_positions()
        assert len(positions) == 1
        assert positions[0]['current_price'] == 51000.0
        assert positions[0]['unrealized_pnl'] == 100.0
        assert positions[0]['quantity'] == 0.2
        # Other fields should remain unchanged
        assert positions[0]['entry_price'] == 50000.0
        assert positions[0]['instrument'] == 'BTC-USD'


class TestTransactionAndBackup:
    """Test transaction retry and backup operations"""
    
    def test_transaction_rollback_on_error(self, db_manager):
        """
        Test transaction rollback on error
        
        Validates: Requirement 18.8 - Database transactions for data integrity
        """
        import sqlite3
        
        # First, insert a valid trade
        valid_trade_data = {
            'id': 'trade_valid_first',
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
        db_manager.insert_trade(valid_trade_data)
        
        # Verify one trade exists
        trades = db_manager.get_trades()
        assert len(trades) == 1
        
        # Now try to insert a trade with a duplicate ID (should fail due to PRIMARY KEY constraint)
        duplicate_trade_data = {
            'id': 'trade_valid_first',  # Same ID - will violate PRIMARY KEY constraint
            'timestamp': datetime.now().isoformat(),
            'instrument': 'ETH-USD',
            'direction': 'short',
            'entry_price': 3000.0,
            'quantity': 0.5,
            'levels_used': '{}',
            'timeframe': '5m',
            'mode': 'smooth',
            'entry_time': datetime.now().isoformat()
        }
        
        # This should fail and not insert anything
        result = db_manager.insert_trade(duplicate_trade_data)
        assert result is False
        
        # Verify still only one trade exists (rollback occurred)
        trades = db_manager.get_trades()
        assert len(trades) == 1
        assert trades[0]['id'] == 'trade_valid_first'
        assert trades[0]['instrument'] == 'BTC-USD'  # Original trade unchanged
        
        # Now insert another valid trade with different ID to ensure database is still functional
        another_valid_trade = {
            'id': 'trade_valid_second',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'ETH-USD',
            'direction': 'short',
            'entry_price': 3000.0,
            'quantity': 0.5,
            'levels_used': '{}',
            'timeframe': '5m',
            'mode': 'smooth',
            'entry_time': datetime.now().isoformat()
        }
        
        result = db_manager.insert_trade(another_valid_trade)
        assert result is True
        
        trades = db_manager.get_trades()
        assert len(trades) == 2
    
    def test_retry_logic_with_simulated_failure(self, db_manager):
        """
        Test retry logic with simulated database lock
        
        Validates: Requirement 18.9 - Retry up to 3 times on write failure
        """
        import sqlite3
        
        # Create a function that fails twice then succeeds
        attempt_count = {'count': 0}
        
        def operation_with_failures():
            attempt_count['count'] += 1
            if attempt_count['count'] < 3:
                raise sqlite3.OperationalError("Database is locked")
            return True
        
        # Test execute_with_retry
        result = db_manager.execute_with_retry(operation_with_failures, max_retries=3)
        assert result is True
        assert attempt_count['count'] == 3  # Should have tried 3 times
    
    def test_retry_exhaustion(self, db_manager):
        """
        Test that retry logic gives up after max attempts
        
        Validates: Requirement 18.9 - Retry up to 3 times on write failure
        """
        import sqlite3
        
        # Create a function that always fails
        def always_fails():
            raise sqlite3.OperationalError("Database is locked")
        
        # Should fail after 3 attempts
        result = db_manager.execute_with_retry(always_fails, max_retries=3)
        assert result is False
    
    def test_save_trade_with_retry(self, db_manager):
        """Test save_trade method with retry logic"""
        trade_data = {
            'id': 'trade_retry',
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
        
        result = db_manager.save_trade(trade_data)
        assert result is True
        
        trades = db_manager.get_trades()
        assert len(trades) == 1
        assert trades[0]['id'] == 'trade_retry'
    
    def test_save_pattern_with_retry(self, db_manager):
        """Test save_pattern method with retry logic"""
        pattern_data = {
            'id': 'pattern_retry',
            'pattern_type': 'test',
            'level': 'BU1',
            'success_rate': 0.75,
            'conditions': '{}',
            'timestamp': datetime.now().isoformat()
        }
        
        result = db_manager.save_pattern(pattern_data)
        assert result is True
        
        patterns = db_manager.get_patterns()
        assert len(patterns) == 1
    
    def test_save_performance_with_retry(self, db_manager):
        """Test save_performance method with retry logic"""
        perf_data = {
            'date': '2024-01-15',
            'total_trades': 10,
            'win_rate': 0.80,
            'total_pnl': 500.0,
            'max_drawdown': -50.0
        }
        
        result = db_manager.save_performance(perf_data)
        assert result is True
        
        performance = db_manager.get_performance()
        assert len(performance) == 1
    
    def test_save_levels_with_retry(self, db_manager):
        """Test save_levels method with retry logic"""
        levels_data = {
            'id': 'levels_retry',
            'timestamp': datetime.now().isoformat(),
            'instrument': 'BTC-USD',
            'timeframe': '5m',
            'base_price': 50000.0,
            'factor': 0.002611,
            'points': 130.55,
            'bu1': 50130.55,
            'bu2': 50261.10,
            'bu3': 50391.65,
            'bu4': 50522.20,
            'bu5': 50652.75,
            'be1': 49869.45,
            'be2': 49738.90,
            'be3': 49608.35,
            'be4': 49477.80,
            'be5': 49347.25
        }
        
        result = db_manager.save_levels(levels_data)
        assert result is True
        
        levels = db_manager.get_levels('BTC-USD', '5m')
        assert len(levels) == 1
    
    def test_save_position_with_retry(self, db_manager):
        """Test save_position method with retry logic"""
        position_data = {
            'id': 'pos_retry',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50500.0,
            'quantity': 0.1,
            'initial_quantity': 0.1,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 50.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        
        result = db_manager.save_position(position_data)
        assert result is True
        
        positions = db_manager.get_positions()
        assert len(positions) == 1
    
    def test_save_config_with_retry(self, db_manager):
        """Test save_config method with retry logic"""
        result = db_manager.save_config('test_key', 'test_value', 'str', 'Test description')
        assert result is True
        
        value = db_manager.get_config('test_key')
        assert value == 'test_value'
    
    def test_backup_databases(self, db_manager, temp_db_dir):
        """Test database backup functionality"""
        # Insert some data
        trade_data = {
            'id': 'trade_backup',
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
        
        # Create backup
        backup_dir = Path(temp_db_dir) / "test_reports"
        result = db_manager.backup_databases(backup_dir=str(backup_dir))
        assert result is True
        
        # Verify backup directory exists
        assert backup_dir.exists()
        
        # Verify backup files exist
        backup_subdirs = list(backup_dir.glob("backup_*"))
        assert len(backup_subdirs) > 0
        
        backup_subdir = backup_subdirs[0]
        assert (backup_subdir / "trades.db").exists()
        assert (backup_subdir / "config.db").exists()
    
    def test_restore_from_backup(self, db_manager, temp_db_dir):
        """Test database restore functionality"""
        # Insert initial data
        trade_data = {
            'id': 'trade_restore',
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
        
        # Create backup
        backup_dir = Path(temp_db_dir) / "test_reports"
        db_manager.backup_databases(backup_dir=str(backup_dir))
        
        # Modify data
        trade_data['id'] = 'trade_modified'
        db_manager.insert_trade(trade_data)
        
        trades = db_manager.get_trades()
        assert len(trades) == 2
        
        # Restore from backup
        backup_subdirs = list(backup_dir.glob("backup_*"))
        result = db_manager.restore_from_backup(str(backup_subdirs[0]))
        assert result is True
        
        # Verify restored data
        trades = db_manager.get_trades()
        assert len(trades) == 1
        assert trades[0]['id'] == 'trade_restore'


class TestConcurrentAccess:
    """Test concurrent access handling"""
    
    def test_concurrent_writes_to_different_tables(self, db_manager):
        """
        Test concurrent writes to different database tables
        
        Validates: Requirement 18.8 - Database transactions for data integrity
        """
        import threading
        import time
        
        results = {'trade': False, 'pattern': False, 'levels': False}
        
        def insert_trade():
            trade_data = {
                'id': 'trade_concurrent',
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
            results['trade'] = db_manager.insert_trade(trade_data)
        
        def insert_pattern():
            pattern_data = {
                'id': 'pattern_concurrent',
                'pattern_type': 'test',
                'level': 'BU1',
                'success_rate': 0.75,
                'conditions': '{}',
                'timestamp': datetime.now().isoformat()
            }
            results['pattern'] = db_manager.insert_pattern(pattern_data)
        
        def insert_levels():
            levels_data = {
                'id': 'levels_concurrent',
                'timestamp': datetime.now().isoformat(),
                'instrument': 'BTC-USD',
                'timeframe': '5m',
                'base_price': 50000.0,
                'factor': 0.002611,
                'points': 130.55,
                'bu1': 50130.55,
                'bu2': 50261.10,
                'bu3': 50391.65,
                'bu4': 50522.20,
                'bu5': 50652.75,
                'be1': 49869.45,
                'be2': 49738.90,
                'be3': 49608.35,
                'be4': 49477.80,
                'be5': 49347.25
            }
            results['levels'] = db_manager.insert_levels(levels_data)
        
        # Create threads for concurrent operations
        threads = [
            threading.Thread(target=insert_trade),
            threading.Thread(target=insert_pattern),
            threading.Thread(target=insert_levels)
        ]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert results['trade'] is True
        assert results['pattern'] is True
        assert results['levels'] is True
        
        # Verify data was inserted correctly
        trades = db_manager.get_trades()
        patterns = db_manager.get_patterns()
        levels = db_manager.get_levels('BTC-USD', '5m')
        
        assert len(trades) == 1
        assert len(patterns) == 1
        assert len(levels) == 1
    
    def test_concurrent_reads_and_writes(self, db_manager):
        """
        Test concurrent reads and writes to the same table
        
        Validates: Requirement 18.8 - Database transactions for data integrity
        """
        import threading
        
        # Insert initial data
        for i in range(5):
            trade_data = {
                'id': f'trade_{i:03d}',
                'timestamp': datetime.now().isoformat(),
                'instrument': 'BTC-USD',
                'direction': 'long',
                'entry_price': 50000.0 + i * 100,
                'quantity': 0.1,
                'levels_used': '{}',
                'timeframe': '5m',
                'mode': 'smooth',
                'entry_time': datetime.now().isoformat()
            }
            db_manager.insert_trade(trade_data)
        
        read_results = []
        write_results = []
        
        def read_trades():
            trades = db_manager.get_trades()
            read_results.append(len(trades))
        
        def write_trade(trade_id):
            trade_data = {
                'id': trade_id,
                'timestamp': datetime.now().isoformat(),
                'instrument': 'ETH-USD',
                'direction': 'short',
                'entry_price': 3000.0,
                'quantity': 0.5,
                'levels_used': '{}',
                'timeframe': '5m',
                'mode': 'smooth',
                'entry_time': datetime.now().isoformat()
            }
            result = db_manager.insert_trade(trade_data)
            write_results.append(result)
        
        # Create threads for concurrent reads and writes
        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=read_trades))
            threads.append(threading.Thread(target=write_trade, args=(f'trade_new_{i}',)))
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        assert len(read_results) == 3
        assert len(write_results) == 3
        assert all(result is True for result in write_results)
        
        # Verify final state
        all_trades = db_manager.get_trades()
        assert len(all_trades) == 8  # 5 initial + 3 new
    
    def test_concurrent_position_updates(self, db_manager):
        """
        Test concurrent updates to the same position
        
        Validates: Requirement 18.8 - Database transactions for data integrity
        """
        import threading
        
        # Insert initial position
        position_data = {
            'id': 'pos_concurrent',
            'instrument': 'BTC-USD',
            'direction': 'long',
            'entry_price': 50000.0,
            'current_price': 50000.0,
            'quantity': 0.1,
            'initial_quantity': 0.1,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': 49500.0,
            'unrealized_pnl': 0.0,
            'levels_used': '{}',
            'last_updated': datetime.now().isoformat()
        }
        db_manager.insert_position(position_data)
        
        update_results = []
        
        def update_position(price):
            updates = {
                'current_price': price,
                'unrealized_pnl': (price - 50000.0) * 0.1
            }
            result = db_manager.update_position('pos_concurrent', updates)
            update_results.append(result)
        
        # Create threads for concurrent updates
        prices = [50100.0, 50200.0, 50300.0, 50400.0, 50500.0]
        threads = [threading.Thread(target=update_position, args=(price,)) for price in prices]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all updates completed
        assert len(update_results) == 5
        assert all(result is True for result in update_results)
        
        # Verify position exists and has been updated
        positions = db_manager.get_positions()
        assert len(positions) == 1
        assert positions[0]['id'] == 'pos_concurrent'
        # Current price should be one of the updated prices
        assert positions[0]['current_price'] in prices
    
    def test_database_integrity_under_load(self, db_manager):
        """
        Test database integrity under high concurrent load
        
        Validates: Requirements 18.8, 18.9 - Transactions and retry logic
        """
        import threading
        
        num_threads = 10
        operations_per_thread = 5
        results = []
        
        def perform_operations(thread_id):
            thread_results = []
            for i in range(operations_per_thread):
                trade_data = {
                    'id': f'trade_t{thread_id}_op{i}',
                    'timestamp': datetime.now().isoformat(),
                    'instrument': 'BTC-USD',
                    'direction': 'long',
                    'entry_price': 50000.0 + thread_id * 100 + i,
                    'quantity': 0.1,
                    'levels_used': '{}',
                    'timeframe': '5m',
                    'mode': 'smooth',
                    'entry_time': datetime.now().isoformat()
                }
                result = db_manager.save_trade(trade_data)
                thread_results.append(result)
            results.append(thread_results)
        
        # Create and start threads
        threads = [threading.Thread(target=perform_operations, args=(i,)) for i in range(num_threads)]
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert len(results) == num_threads
        for thread_results in results:
            assert len(thread_results) == operations_per_thread
            assert all(result is True for result in thread_results)
        
        # Verify correct number of trades inserted
        trades = db_manager.get_trades()
        assert len(trades) == num_threads * operations_per_thread


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
