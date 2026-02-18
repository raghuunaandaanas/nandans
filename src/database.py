"""
Database module for B5 Factor Trading System

This module defines all database schemas and provides database management functions.
Implements Requirements 18.1-18.6 for data persistence.

Databases:
- trades.db: Trade execution history
- patterns.db: ML pattern learning data
- performance.db: Performance metrics and analytics
- levels.db: Historical level calculations
- positions.db: Current open positions
- config.db: System configuration
"""

import sqlite3
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path


class DatabaseManager:
    """Manages all database connections and operations"""
    
    def __init__(self, db_dir: str = "data"):
        """
        Initialize database manager
        
        Args:
            db_dir: Directory to store database files
        """
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        
        # Database file paths
        self.trades_db = self.db_dir / "trades.db"
        self.patterns_db = self.db_dir / "patterns.db"
        self.performance_db = self.db_dir / "performance.db"
        self.levels_db = self.db_dir / "levels.db"
        self.positions_db = self.db_dir / "positions.db"
        self.config_db = self.db_dir / "config.db"
        
        # Initialize all databases
        self._init_trades_db()
        self._init_patterns_db()
        self._init_performance_db()
        self._init_levels_db()
        self._init_positions_db()
        self._init_config_db()
    
    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_trades_db(self):
        """
        Initialize trades.db schema
        
        Stores all trade execution history including entry/exit details,
        profit/loss, and levels used for the trade.
        
        Validates: Requirement 18.1
        """
        conn = self._get_connection(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                profit_loss REAL,
                levels_used TEXT NOT NULL,
                entry_level TEXT,
                exit_level TEXT,
                timeframe TEXT NOT NULL,
                mode TEXT NOT NULL,
                stop_loss REAL,
                was_pyramided INTEGER DEFAULT 0,
                pyramid_count INTEGER DEFAULT 0,
                entry_time TEXT NOT NULL,
                exit_time TEXT
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp 
            ON trades(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_instrument 
            ON trades(instrument)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_patterns_db(self):
        """
        Initialize patterns.db schema
        
        Stores learned patterns for ML engine including pattern type,
        success rate, and conditions that define the pattern.
        
        Validates: Requirement 18.2
        """
        conn = self._get_connection(self.patterns_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                level TEXT NOT NULL,
                success_rate REAL NOT NULL,
                conditions TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                occurrences INTEGER DEFAULT 1,
                instrument TEXT,
                timeframe TEXT,
                last_updated TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type 
            ON patterns(pattern_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_level 
            ON patterns(level)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_performance_db(self):
        """
        Initialize performance.db schema
        
        Stores daily performance metrics including P&L, win rate,
        profit factor, Sharpe ratio, and maximum drawdown.
        
        Validates: Requirement 18.3
        """
        conn = self._get_connection(self.performance_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                date TEXT PRIMARY KEY,
                total_trades INTEGER NOT NULL,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                win_rate REAL NOT NULL,
                total_pnl REAL NOT NULL,
                profit_factor REAL,
                sharpe_ratio REAL,
                max_drawdown REAL NOT NULL,
                avg_win REAL,
                avg_loss REAL,
                best_trade REAL,
                worst_trade REAL,
                by_instrument TEXT,
                by_timeframe TEXT,
                by_mode TEXT
            )
        """)
        
        # Create index on date
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_performance_date 
            ON performance(date)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_levels_db(self):
        """
        Initialize levels.db schema
        
        Stores historical level calculations for all instruments and timeframes.
        Includes base price, factor, points, and all BU/BE levels.
        
        Validates: Requirement 18.4
        """
        conn = self._get_connection(self.levels_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                instrument TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                base_price REAL NOT NULL,
                factor REAL NOT NULL,
                points REAL NOT NULL,
                bu1 REAL NOT NULL,
                bu2 REAL NOT NULL,
                bu3 REAL NOT NULL,
                bu4 REAL NOT NULL,
                bu5 REAL NOT NULL,
                be1 REAL NOT NULL,
                be2 REAL NOT NULL,
                be3 REAL NOT NULL,
                be4 REAL NOT NULL,
                be5 REAL NOT NULL
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_levels_timestamp 
            ON levels(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_levels_instrument_timeframe 
            ON levels(instrument, timeframe)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_positions_db(self):
        """
        Initialize positions.db schema
        
        Stores current open positions including entry details, current price,
        stop loss, and unrealized P&L.
        
        Validates: Requirement 18.5
        """
        conn = self._get_connection(self.positions_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL NOT NULL,
                quantity REAL NOT NULL,
                initial_quantity REAL NOT NULL,
                entry_time TEXT NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit TEXT,
                unrealized_pnl REAL NOT NULL,
                levels_used TEXT NOT NULL,
                pyramid_history TEXT,
                last_updated TEXT NOT NULL
            )
        """)
        
        # Create index on instrument
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_instrument 
            ON positions(instrument)
        """)
        
        conn.commit()
        conn.close()
    
    def _init_config_db(self):
        """
        Initialize config.db schema
        
        Stores system configuration including risk parameters,
        API credentials, and system settings.
        
        Validates: Requirement 18.6
        """
        conn = self._get_connection(self.config_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                last_updated TEXT NOT NULL
            )
        """)
        
        # Insert default configuration values
        default_config = [
            ('max_daily_loss_percent', '5.0', 'float', 'Maximum daily loss as percentage of capital'),
            ('max_per_trade_loss_percent', '1.0', 'float', 'Maximum loss per trade as percentage of capital'),
            ('initial_position_size', '0.01', 'float', 'Initial position size in contracts'),
            ('max_pyramiding_multiplier', '100', 'int', 'Maximum pyramiding multiplier'),
            ('trading_mode', 'smooth', 'str', 'Trading mode: soft, smooth, or aggressive'),
            ('enable_hft_mode', 'false', 'bool', 'Enable high-frequency trading mode'),
            ('enable_auto_sense', 'true', 'bool', 'Enable AUTO SENSE ML features'),
            ('paper_trading', 'true', 'bool', 'Paper trading mode (true) or live trading (false)'),
            ('max_exposure_percent', '20.0', 'float', 'Maximum total exposure as percentage of capital'),
            ('max_exposure_per_instrument', '5.0', 'float', 'Maximum exposure per instrument as percentage'),
        ]
        
        timestamp = datetime.now().isoformat()
        for key, value, type_, description in default_config:
            cursor.execute("""
                INSERT OR IGNORE INTO config (key, value, type, description, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (key, value, type_, description, timestamp))
        
        conn.commit()
        conn.close()
    
    # Trade operations
    
    def insert_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Insert a trade record into trades.db
        
        Args:
            trade_data: Dictionary containing trade information
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection(self.trades_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO trades (
                    id, timestamp, instrument, direction, entry_price, exit_price,
                    quantity, profit_loss, levels_used, entry_level, exit_level,
                    timeframe, mode, stop_loss, was_pyramided, pyramid_count,
                    entry_time, exit_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data['id'],
                trade_data['timestamp'],
                trade_data['instrument'],
                trade_data['direction'],
                trade_data['entry_price'],
                trade_data.get('exit_price'),
                trade_data['quantity'],
                trade_data.get('profit_loss'),
                trade_data['levels_used'],
                trade_data.get('entry_level'),
                trade_data.get('exit_level'),
                trade_data['timeframe'],
                trade_data['mode'],
                trade_data.get('stop_loss'),
                trade_data.get('was_pyramided', 0),
                trade_data.get('pyramid_count', 0),
                trade_data['entry_time'],
                trade_data.get('exit_time')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting trade: {e}")
            return False
        finally:
            conn.close()
    
    def get_trades(self, instrument: Optional[str] = None, 
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve trades from trades.db
        
        Args:
            instrument: Filter by instrument (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)
            
        Returns:
            List of trade records as dictionaries
        """
        conn = self._get_connection(self.trades_db)
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if instrument:
            query += " AND instrument = ?"
            params.append(instrument)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific trade by ID
        
        Args:
            trade_id: Trade ID to retrieve
            
        Returns:
            Trade record as dictionary or None if not found
        """
        conn = self._get_connection(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # Pattern operations
    
    def insert_pattern(self, pattern_data: Dict[str, Any]) -> bool:
        """Insert a pattern record into patterns.db"""
        conn = self._get_connection(self.patterns_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO patterns (
                    id, pattern_type, level, success_rate, conditions,
                    timestamp, occurrences, instrument, timeframe, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern_data['id'],
                pattern_data['pattern_type'],
                pattern_data['level'],
                pattern_data['success_rate'],
                pattern_data['conditions'],
                pattern_data['timestamp'],
                pattern_data.get('occurrences', 1),
                pattern_data.get('instrument'),
                pattern_data.get('timeframe'),
                pattern_data.get('last_updated', pattern_data['timestamp'])
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting pattern: {e}")
            return False
        finally:
            conn.close()
    
    def update_pattern(self, pattern_id: str, success_rate: float, 
                      occurrences: int) -> bool:
        """Update pattern success rate and occurrences"""
        conn = self._get_connection(self.patterns_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE patterns 
                SET success_rate = ?, occurrences = ?, last_updated = ?
                WHERE id = ?
            """, (success_rate, occurrences, datetime.now().isoformat(), pattern_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating pattern: {e}")
            return False
        finally:
            conn.close()
    
    def get_patterns(self, pattern_type: Optional[str] = None,
                    level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve patterns from patterns.db"""
        conn = self._get_connection(self.patterns_db)
        cursor = conn.cursor()
        
        query = "SELECT * FROM patterns WHERE 1=1"
        params = []
        
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        if level:
            query += " AND level = ?"
            params.append(level)
        
        query += " ORDER BY success_rate DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # Performance operations
    
    def insert_performance(self, perf_data: Dict[str, Any]) -> bool:
        """Insert daily performance metrics into performance.db"""
        conn = self._get_connection(self.performance_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO performance (
                    date, total_trades, winning_trades, losing_trades, win_rate,
                    total_pnl, profit_factor, sharpe_ratio, max_drawdown,
                    avg_win, avg_loss, best_trade, worst_trade,
                    by_instrument, by_timeframe, by_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                perf_data['date'],
                perf_data['total_trades'],
                perf_data.get('winning_trades', 0),
                perf_data.get('losing_trades', 0),
                perf_data['win_rate'],
                perf_data['total_pnl'],
                perf_data.get('profit_factor'),
                perf_data.get('sharpe_ratio'),
                perf_data['max_drawdown'],
                perf_data.get('avg_win'),
                perf_data.get('avg_loss'),
                perf_data.get('best_trade'),
                perf_data.get('worst_trade'),
                perf_data.get('by_instrument'),
                perf_data.get('by_timeframe'),
                perf_data.get('by_mode')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting performance: {e}")
            return False
        finally:
            conn.close()
    
    def get_performance(self, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve performance metrics from performance.db"""
        conn = self._get_connection(self.performance_db)
        cursor = conn.cursor()
        
        query = "SELECT * FROM performance WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # Level operations
    
    def insert_levels(self, levels_data: Dict[str, Any]) -> bool:
        """Insert level calculation into levels.db"""
        conn = self._get_connection(self.levels_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO levels (
                    id, timestamp, instrument, timeframe, base_price, factor, points,
                    bu1, bu2, bu3, bu4, bu5, be1, be2, be3, be4, be5
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                levels_data['id'],
                levels_data['timestamp'],
                levels_data['instrument'],
                levels_data['timeframe'],
                levels_data['base_price'],
                levels_data['factor'],
                levels_data['points'],
                levels_data['bu1'],
                levels_data['bu2'],
                levels_data['bu3'],
                levels_data['bu4'],
                levels_data['bu5'],
                levels_data['be1'],
                levels_data['be2'],
                levels_data['be3'],
                levels_data['be4'],
                levels_data['be5']
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting levels: {e}")
            return False
        finally:
            conn.close()
    
    def get_levels(self, instrument: str, timeframe: str,
                   limit: int = 1) -> List[Dict[str, Any]]:
        """Retrieve most recent levels for instrument and timeframe"""
        conn = self._get_connection(self.levels_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM levels 
            WHERE instrument = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (instrument, timeframe, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # Position operations
    
    def insert_position(self, position_data: Dict[str, Any]) -> bool:
        """Insert or update position in positions.db"""
        conn = self._get_connection(self.positions_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO positions (
                    id, instrument, direction, entry_price, current_price,
                    quantity, initial_quantity, entry_time, stop_loss, take_profit,
                    unrealized_pnl, levels_used, pyramid_history, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_data['id'],
                position_data['instrument'],
                position_data['direction'],
                position_data['entry_price'],
                position_data['current_price'],
                position_data['quantity'],
                position_data['initial_quantity'],
                position_data['entry_time'],
                position_data['stop_loss'],
                position_data.get('take_profit'),
                position_data['unrealized_pnl'],
                position_data['levels_used'],
                position_data.get('pyramid_history'),
                position_data['last_updated']
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting position: {e}")
            return False
        finally:
            conn.close()
    
    def delete_position(self, position_id: str) -> bool:
        """Delete position from positions.db"""
        conn = self._get_connection(self.positions_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM positions WHERE id = ?", (position_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting position: {e}")
            return False
        finally:
            conn.close()
    
    def get_positions(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve current positions from positions.db"""
        conn = self._get_connection(self.positions_db)
        cursor = conn.cursor()
        
        if instrument:
            cursor.execute("SELECT * FROM positions WHERE instrument = ?", (instrument,))
        else:
            cursor.execute("SELECT * FROM positions")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_position(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of a position
        
        Args:
            position_id: Position ID to update
            updates: Dictionary of field names and new values
            
        Returns:
            True if successful, False otherwise
        """
        if not updates:
            return False
        
        conn = self._get_connection(self.positions_db)
        cursor = conn.cursor()
        
        try:
            # Build UPDATE query dynamically
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values())
            values.append(datetime.now().isoformat())  # Update last_updated
            values.append(position_id)
            
            query = f"UPDATE positions SET {set_clause}, last_updated = ? WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating position: {e}")
            return False
        finally:
            conn.close()
    
    # Configuration operations
    
    def get_config(self, key: str) -> Optional[Any]:
        """Get configuration value by key"""
        conn = self._get_connection(self.config_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value, type FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        value, type_ = row['value'], row['type']
        
        # Convert to appropriate type
        if type_ == 'int':
            return int(value)
        elif type_ == 'float':
            return float(value)
        elif type_ == 'bool':
            return value.lower() == 'true'
        else:
            return value
    
    def set_config(self, key: str, value: Any, type_: str, 
                   description: Optional[str] = None) -> bool:
        """Set configuration value"""
        conn = self._get_connection(self.config_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, type, description, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (key, str(value), type_, description, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error setting config: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values"""
        conn = self._get_connection(self.config_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value, type FROM config")
        rows = cursor.fetchall()
        conn.close()
        
        config = {}
        for row in rows:
            key, value, type_ = row['key'], row['value'], row['type']
            
            if type_ == 'int':
                config[key] = int(value)
            elif type_ == 'float':
                config[key] = float(value)
            elif type_ == 'bool':
                config[key] = value.lower() == 'true'
            else:
                config[key] = value
        
        return config
    
    # Transaction and backup operations
    
    def execute_with_retry(self, operation, max_retries: int = 3) -> bool:
        """
        Execute database operation with retry logic for data integrity
        
        Implements Requirement 18.8: Database transactions for data integrity
        Implements Requirement 18.9: Retry up to 3 times on write failure
        
        Args:
            operation: Callable that performs the database operation
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        import time
        
        for attempt in range(max_retries):
            try:
                result = operation()
                return result
            except sqlite3.OperationalError as e:
                if attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                    print(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Database operation failed after {max_retries} attempts: {e}")
                    return False
            except Exception as e:
                print(f"Unexpected error in database operation: {e}")
                return False
        
        return False
    
    def backup_databases(self, backup_dir: str = "reports") -> bool:
        """
        Backup all databases to reports folder
        
        Implements Requirement 18.7: Daily backup to reports folder
        
        Args:
            backup_dir: Directory to store backups
            
        Returns:
            True if successful, False otherwise
        """
        import shutil
        from datetime import datetime
        
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        # Create timestamped backup subdirectory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = backup_path / f"backup_{timestamp}"
        backup_subdir.mkdir(exist_ok=True)
        
        databases = [
            self.trades_db,
            self.patterns_db,
            self.performance_db,
            self.levels_db,
            self.positions_db,
            self.config_db
        ]
        
        try:
            for db_path in databases:
                if db_path.exists():
                    backup_file = backup_subdir / db_path.name
                    shutil.copy2(db_path, backup_file)
                    print(f"Backed up {db_path.name} to {backup_file}")
            
            print(f"All databases backed up successfully to {backup_subdir}")
            return True
        except Exception as e:
            print(f"Error backing up databases: {e}")
            return False
    
    def restore_from_backup(self, backup_subdir: str) -> bool:
        """
        Restore databases from backup
        
        Implements Requirement 18.10: Restore from most recent backup when corrupted
        
        Args:
            backup_subdir: Path to backup subdirectory
            
        Returns:
            True if successful, False otherwise
        """
        import shutil
        
        backup_path = Path(backup_subdir)
        
        if not backup_path.exists():
            print(f"Backup directory not found: {backup_subdir}")
            return False
        
        databases = [
            ('trades.db', self.trades_db),
            ('patterns.db', self.patterns_db),
            ('performance.db', self.performance_db),
            ('levels.db', self.levels_db),
            ('positions.db', self.positions_db),
            ('config.db', self.config_db)
        ]
        
        try:
            for db_name, db_path in databases:
                backup_file = backup_path / db_name
                if backup_file.exists():
                    shutil.copy2(backup_file, db_path)
                    print(f"Restored {db_name} from {backup_file}")
            
            print(f"All databases restored successfully from {backup_subdir}")
            return True
        except Exception as e:
            print(f"Error restoring databases: {e}")
            return False
    
    # Convenience methods with transaction support
    
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Save trade with retry logic
        
        Wrapper around insert_trade with transaction retry support
        """
        return self.execute_with_retry(lambda: self.insert_trade(trade_data))
    
    def save_pattern(self, pattern_data: Dict[str, Any]) -> bool:
        """
        Save pattern with retry logic
        
        Wrapper around insert_pattern with transaction retry support
        """
        return self.execute_with_retry(lambda: self.insert_pattern(pattern_data))
    
    def save_performance(self, perf_data: Dict[str, Any]) -> bool:
        """
        Save performance metrics with retry logic
        
        Wrapper around insert_performance with transaction retry support
        """
        return self.execute_with_retry(lambda: self.insert_performance(perf_data))
    
    def save_levels(self, levels_data: Dict[str, Any]) -> bool:
        """
        Save levels with retry logic
        
        Wrapper around insert_levels with transaction retry support
        """
        return self.execute_with_retry(lambda: self.insert_levels(levels_data))
    
    def save_position(self, position_data: Dict[str, Any]) -> bool:
        """
        Save position with retry logic
        
        Wrapper around insert_position with transaction retry support
        """
        return self.execute_with_retry(lambda: self.insert_position(position_data))
    
    def save_config(self, key: str, value: Any, type_: str, 
                    description: Optional[str] = None) -> bool:
        """
        Save configuration with retry logic
        
        Wrapper around set_config with transaction retry support
        """
        return self.execute_with_retry(
            lambda: self.set_config(key, value, type_, description)
        )
