"""
Unit tests for ML Engine.
Tests pattern recognition, ML model training, and AUTO SENSE v2.0.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.ml_engine import PatternRecognizer, MLModelTrainer, AutoSenseV2
from src.main import AutoSenseEngine


class TestPatternRecognizer:
    """Test Pattern Recognizer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.mock_db.save_pattern = Mock(return_value=True)
        self.recognizer = PatternRecognizer(self.mock_db)
    
    def test_record_pattern_success(self):
        """Test successful pattern recording."""
        price_action = [100.0, 101.0, 102.0, 101.5]
        volume = [1000, 1100, 1200, 1050]
        
        result = self.recognizer.record_pattern(
            price_action=price_action,
            volume=volume,
            level='bu1',
            outcome='success'
        )
        
        assert result['recorded'] is True
        assert 'pattern_id' in result
        assert 'features' in result
        assert result['features']['momentum'] > 0  # Upward momentum
    
    def test_record_pattern_insufficient_data(self):
        """Test pattern recording with insufficient data."""
        result = self.recognizer.record_pattern(
            price_action=[100.0],
            volume=[1000],
            level='bu1',
            outcome='success'
        )
        
        assert result['recorded'] is False
        assert 'Insufficient' in result['reason']
    
    def test_record_pattern_mismatched_lengths(self):
        """Test pattern recording with mismatched data lengths."""
        result = self.recognizer.record_pattern(
            price_action=[100.0, 101.0],
            volume=[1000],
            level='bu1',
            outcome='success'
        )
        
        assert result['recorded'] is False
        assert 'must match' in result['reason']
    
    def test_analyze_patterns_empty(self):
        """Test pattern analysis with no patterns."""
        result = self.recognizer.analyze_patterns()
        
        assert result['total_patterns'] == 0
        assert result['success_rate'] == 0.0
    
    def test_analyze_patterns_with_data(self):
        """Test pattern analysis with recorded patterns."""
        # Record some patterns
        for i in range(10):
            outcome = 'success' if i < 7 else 'failure'
            self.recognizer.record_pattern(
                price_action=[100.0 + i, 101.0 + i],
                volume=[1000, 1100],
                level='bu1',
                outcome=outcome
            )
        
        result = self.recognizer.analyze_patterns(level='bu1')
        
        assert result['total_patterns'] == 10
        assert result['successes'] == 7
        assert result['failures'] == 3
        assert result['success_rate'] == 0.7
    
    def test_analyze_patterns_filtered_by_level(self):
        """Test pattern analysis filtered by level."""
        # Record patterns at different levels
        self.recognizer.record_pattern(
            price_action=[100.0, 101.0],
            volume=[1000, 1100],
            level='bu1',
            outcome='success'
        )
        self.recognizer.record_pattern(
            price_action=[100.0, 99.0],
            volume=[1000, 1100],
            level='be1',
            outcome='success'
        )
        
        result_bu1 = self.recognizer.analyze_patterns(level='bu1')
        result_be1 = self.recognizer.analyze_patterns(level='be1')
        
        assert result_bu1['total_patterns'] == 1
        assert result_be1['total_patterns'] == 1
    
    def test_find_similar_patterns_empty(self):
        """Test finding similar patterns with no historical data."""
        current_pattern = {
            'momentum': 0.5,
            'volume_strength': 1.2,
            'volatility': 0.3,
            'level': 'bu1'
        }
        
        result = self.recognizer.find_similar_patterns(current_pattern)
        
        assert len(result) == 0
    
    def test_find_similar_patterns_with_data(self):
        """Test finding similar patterns with historical data."""
        # Record some patterns
        for i in range(5):
            self.recognizer.record_pattern(
                price_action=[100.0 + i * 0.5, 101.0 + i * 0.5],
                volume=[1000, 1100],
                level='bu1',
                outcome='success'
            )
        
        current_pattern = {
            'momentum': 0.5,
            'volume_strength': 1.1,
            'volatility': 0.5,
            'level': 'bu1'
        }
        
        result = self.recognizer.find_similar_patterns(current_pattern, top_n=3)
        
        assert len(result) <= 3
        assert all('similarity' in p for p in result)
        assert all('pattern' in p for p in result)
        # Similarities should be in descending order
        if len(result) > 1:
            assert result[0]['similarity'] >= result[1]['similarity']


class TestMLModelTrainer:
    """Test ML Model Trainer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.trainer = MLModelTrainer(model_dir='test_models')
    
    def test_train_factor_model_insufficient_data(self):
        """Test factor model training with insufficient data."""
        historical_data = [
            {'base_price': 50000.0, 'volatility': 0.02, 'optimal_factor': 0.002611, 'outcome': 'success'}
        ]
        
        result = self.trainer.train_factor_selection_model(historical_data)
        
        assert result['trained'] is False
        assert 'Insufficient' in result['reason']
    
    def test_train_factor_model_success(self):
        """Test successful factor model training."""
        historical_data = []
        for i in range(20):
            historical_data.append({
                'base_price': 50000.0 + i * 100,
                'volatility': 0.02 + i * 0.001,
                'optimal_factor': 0.002611,
                'outcome': 'success'
            })
        
        result = self.trainer.train_factor_selection_model(historical_data)
        
        assert result['trained'] is True
        assert result['model_type'] == 'weighted_average'
        assert result['samples'] == 20
        assert 'accuracy' in result
    
    def test_train_entry_timing_model_insufficient_data(self):
        """Test entry timing model training with insufficient data."""
        historical_data = [
            {'momentum': 0.5, 'volume_strength': 1.2, 'entry_method': 'immediate', 'outcome': 'success'}
        ]
        
        result = self.trainer.train_entry_timing_model(historical_data)
        
        assert result['trained'] is False
    
    def test_train_entry_timing_model_success(self):
        """Test successful entry timing model training."""
        historical_data = []
        for i in range(15):
            historical_data.append({
                'momentum': 0.5 + i * 0.1,
                'volume_strength': 1.0 + i * 0.1,
                'entry_method': 'immediate' if i % 2 == 0 else 'wait',
                'outcome': 'success'
            })
        
        result = self.trainer.train_entry_timing_model(historical_data)
        
        assert result['trained'] is True
        assert result['model_type'] == 'threshold'
        assert result['samples'] == 15
        assert 'thresholds' in result
    
    def test_train_exit_percentage_model_success(self):
        """Test successful exit percentage model training."""
        historical_data = [
            {'level': 'bu2', 'rejection_rate': 0.3, 'optimal_exit_pct': 0.25},
            {'level': 'bu2', 'rejection_rate': 0.35, 'optimal_exit_pct': 0.30},
            {'level': 'bu3', 'rejection_rate': 0.5, 'optimal_exit_pct': 0.40},
            {'level': 'bu3', 'rejection_rate': 0.55, 'optimal_exit_pct': 0.45},
            {'level': 'bu4', 'rejection_rate': 0.7, 'optimal_exit_pct': 0.50}
        ]
        
        result = self.trainer.train_exit_percentage_model(historical_data)
        
        assert result['trained'] is True
        assert result['model_type'] == 'level_average'
        assert 'level_percentages' in result
        assert 'bu2' in result['level_percentages']
        assert 'bu3' in result['level_percentages']
    
    def test_train_spike_detection_model_success(self):
        """Test successful spike detection model training."""
        historical_data = []
        for i in range(20):
            historical_data.append({
                'price_movement': 2.0 + i * 0.1,
                'volume_ratio': 1.5 + i * 0.1,
                'is_real_spike': i % 2 == 0
            })
        
        result = self.trainer.train_spike_detection_model(historical_data)
        
        assert result['trained'] is True
        assert result['model_type'] == 'threshold'
        assert result['samples'] == 20
        assert 'volume_threshold' in result
    
    def test_load_models_no_files(self):
        """Test loading models when no files exist."""
        result = self.trainer.load_models()
        
        assert isinstance(result, dict)
        assert 'factor' in result
        assert 'entry_timing' in result
        assert 'exit_percentage' in result
        assert 'spike_detection' in result


class TestAutoSenseV2:
    """Test AUTO SENSE v2.0 functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        mock_db = Mock()
        mock_db.save_pattern = Mock(return_value=True)
        
        self.pattern_recognizer = PatternRecognizer(mock_db)
        self.ml_trainer = MLModelTrainer(model_dir='test_models')
        self.rule_based_engine = AutoSenseEngine()
        
        self.auto_sense_v2 = AutoSenseV2(
            self.pattern_recognizer,
            self.ml_trainer,
            self.rule_based_engine
        )
    
    def test_select_optimal_factor_fallback_to_rules(self):
        """Test factor selection falls back to rules when ML not available."""
        # Ensure ML is disabled
        self.auto_sense_v2.ml_enabled = False
        self.auto_sense_v2.ml_trainer.factor_model = None
        
        result = self.auto_sense_v2.select_optimal_factor_ml(50000.0, 0.02)
        
        assert 'factor' in result
        assert result['method'] == 'rules_fallback'
        assert result['factor'] == 0.002611  # For price 50000
    
    def test_select_optimal_factor_with_ml(self):
        """Test factor selection with ML model."""
        # Train a simple model
        historical_data = []
        for i in range(15):
            historical_data.append({
                'base_price': 50000.0 + i * 100,
                'volatility': 0.02,
                'optimal_factor': 0.002611,
                'outcome': 'success'
            })
        
        self.ml_trainer.train_factor_selection_model(historical_data)
        self.auto_sense_v2.ml_enabled = True
        
        result = self.auto_sense_v2.select_optimal_factor_ml(50000.0, 0.02)
        
        assert 'factor' in result
        assert result['method'] == 'ml'
    
    def test_predict_entry_timing_fallback_to_rules(self):
        """Test entry timing prediction falls back to rules."""
        # Ensure ML is disabled
        self.auto_sense_v2.ml_enabled = False
        self.auto_sense_v2.ml_trainer.entry_timing_model = None
        
        price_action = [100.0, 101.0, 102.0]
        volume = [1000, 1100, 1200]
        
        result = self.auto_sense_v2.predict_entry_timing_ml(price_action, volume)
        
        assert 'timing' in result
        assert result['method'] == 'rules_fallback'
    
    def test_track_prediction_accuracy(self):
        """Test tracking prediction accuracy."""
        result = self.auto_sense_v2.track_prediction_accuracy(
            prediction_type='factor',
            predicted=0.002611,
            actual=0.002611
        )
        
        assert result['tracked'] is True
        assert result['accuracy'] == 1.0
        assert 'rolling_accuracy' in result
    
    def test_track_prediction_accuracy_invalid_type(self):
        """Test tracking with invalid prediction type."""
        result = self.auto_sense_v2.track_prediction_accuracy(
            prediction_type='invalid',
            predicted=0.5,
            actual=0.5
        )
        
        assert result['tracked'] is False
    
    def test_get_ml_status(self):
        """Test getting ML system status."""
        result = self.auto_sense_v2.get_ml_status()
        
        assert 'ml_enabled' in result
        assert 'models_loaded' in result
        assert 'prediction_counts' in result
        assert 'rolling_accuracy' in result
        
        assert isinstance(result['models_loaded'], dict)
        assert 'factor' in result['models_loaded']
        assert 'entry_timing' in result['models_loaded']
    
    def test_ml_status_after_training(self):
        """Test ML status after training models."""
        # Train a model
        historical_data = []
        for i in range(15):
            historical_data.append({
                'base_price': 50000.0,
                'volatility': 0.02,
                'optimal_factor': 0.002611,
                'outcome': 'success'
            })
        
        self.ml_trainer.train_factor_selection_model(historical_data)
        self.auto_sense_v2.ml_enabled = True
        
        result = self.auto_sense_v2.get_ml_status()
        
        assert result['ml_enabled'] is True
        assert result['models_loaded']['factor'] is True
    
    def test_rolling_accuracy_calculation(self):
        """Test rolling accuracy calculation over multiple predictions."""
        # Track multiple predictions
        for i in range(10):
            self.auto_sense_v2.track_prediction_accuracy(
                prediction_type='entry_timing',
                predicted=1 if i < 7 else 0,
                actual=1 if i < 7 else 0
            )
        
        status = self.auto_sense_v2.get_ml_status()
        
        assert status['prediction_counts']['entry_timing'] == 10
        assert status['rolling_accuracy']['entry_timing'] == 1.0  # All correct
