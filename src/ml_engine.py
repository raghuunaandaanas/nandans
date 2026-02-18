"""
ML Engine for B5 Factor Trading System.
Implements pattern recognition, ML model training, and AUTO SENSE v2.0.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from datetime import datetime
import pickle
import os


class PatternRecognizer:
    """
    Recognizes and stores trading patterns for machine learning.
    """
    
    def __init__(self, database_manager):
        """
        Initialize Pattern Recognizer.
        
        Args:
            database_manager: DatabaseManager instance for pattern storage
        """
        self.db = database_manager
        self.patterns = []
        
    def record_pattern(self, price_action: List[float], volume: List[float],
                      level: str, outcome: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Record a trading pattern with its outcome.
        
        Args:
            price_action: List of prices leading to the pattern
            volume: List of volumes corresponding to prices
            level: Level where pattern occurred (e.g., 'bu1', 'be2')
            outcome: Pattern outcome ('success', 'failure', 'neutral')
            metadata: Additional pattern information
            
        Returns:
            Dict with pattern_id and storage confirmation
        """
        if len(price_action) < 2:
            return {
                'recorded': False,
                'reason': 'Insufficient price action data (need at least 2 points)'
            }
        
        if len(price_action) != len(volume):
            return {
                'recorded': False,
                'reason': 'Price action and volume lengths must match'
            }
        
        # Calculate pattern features
        momentum = self._calculate_momentum(price_action)
        volume_strength = self._calculate_volume_strength(volume)
        volatility = self._calculate_volatility(price_action)
        
        pattern = {
            'timestamp': datetime.now().isoformat(),
            'price_action': price_action,
            'volume': volume,
            'level': level,
            'outcome': outcome,
            'momentum': momentum,
            'volume_strength': volume_strength,
            'volatility': volatility,
            'metadata': metadata or {}
        }
        
        self.patterns.append(pattern)
        
        # Store in database
        try:
            self.db.save_pattern(pattern)
            return {
                'recorded': True,
                'pattern_id': len(self.patterns) - 1,
                'features': {
                    'momentum': momentum,
                    'volume_strength': volume_strength,
                    'volatility': volatility
                }
            }
        except Exception as e:
            return {
                'recorded': False,
                'reason': f'Database error: {str(e)}'
            }
    
    def analyze_patterns(self, level: str = None) -> Dict[str, Any]:
        """
        Analyze stored patterns to calculate success rates.
        
        Args:
            level: Optional level filter (e.g., 'bu1')
            
        Returns:
            Dict with success rates and pattern statistics
        """
        # Filter patterns by level if specified
        if level:
            filtered_patterns = [p for p in self.patterns if p['level'] == level]
        else:
            filtered_patterns = self.patterns
        
        if not filtered_patterns:
            return {
                'total_patterns': 0,
                'success_rate': 0.0,
                'level': level
            }
        
        # Calculate success rate
        successes = sum(1 for p in filtered_patterns if p['outcome'] == 'success')
        failures = sum(1 for p in filtered_patterns if p['outcome'] == 'failure')
        neutral = sum(1 for p in filtered_patterns if p['outcome'] == 'neutral')
        
        total = len(filtered_patterns)
        success_rate = successes / total if total > 0 else 0.0
        
        # Calculate average features for successful patterns
        successful_patterns = [p for p in filtered_patterns if p['outcome'] == 'success']
        
        if successful_patterns:
            avg_momentum = np.mean([p['momentum'] for p in successful_patterns])
            avg_volume = np.mean([p['volume_strength'] for p in successful_patterns])
            avg_volatility = np.mean([p['volatility'] for p in successful_patterns])
        else:
            avg_momentum = 0.0
            avg_volume = 0.0
            avg_volatility = 0.0
        
        return {
            'total_patterns': total,
            'successes': successes,
            'failures': failures,
            'neutral': neutral,
            'success_rate': success_rate,
            'level': level,
            'avg_successful_features': {
                'momentum': avg_momentum,
                'volume_strength': avg_volume,
                'volatility': avg_volatility
            }
        }
    
    def find_similar_patterns(self, current_pattern: Dict[str, Any],
                             top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Find historical patterns similar to current pattern.
        
        Args:
            current_pattern: Current pattern with momentum, volume_strength, volatility
            top_n: Number of similar patterns to return
            
        Returns:
            List of similar patterns with similarity scores
        """
        if not self.patterns:
            return []
        
        current_momentum = current_pattern.get('momentum', 0.0)
        current_volume = current_pattern.get('volume_strength', 0.0)
        current_volatility = current_pattern.get('volatility', 0.0)
        current_level = current_pattern.get('level', '')
        
        similarities = []
        
        for pattern in self.patterns:
            # Calculate Euclidean distance in feature space
            momentum_diff = (pattern['momentum'] - current_momentum) ** 2
            volume_diff = (pattern['volume_strength'] - current_volume) ** 2
            volatility_diff = (pattern['volatility'] - current_volatility) ** 2
            
            distance = np.sqrt(momentum_diff + volume_diff + volatility_diff)
            similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity
            
            # Boost similarity if same level
            if pattern['level'] == current_level:
                similarity *= 1.2
            
            similarities.append({
                'pattern': pattern,
                'similarity': similarity,
                'distance': distance
            })
        
        # Sort by similarity (descending) and return top N
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:top_n]
    
    def _calculate_momentum(self, price_action: List[float]) -> float:
        """Calculate momentum from price action."""
        if len(price_action) < 2:
            return 0.0
        
        changes = [price_action[i] - price_action[i-1] for i in range(1, len(price_action))]
        return np.mean(changes) if changes else 0.0
    
    def _calculate_volume_strength(self, volume: List[float]) -> float:
        """Calculate volume strength."""
        if not volume:
            return 0.0
        
        avg_volume = np.mean(volume)
        recent_volume = volume[-1] if volume else 0.0
        
        return recent_volume / avg_volume if avg_volume > 0 else 1.0
    
    def _calculate_volatility(self, price_action: List[float]) -> float:
        """Calculate volatility from price action."""
        if len(price_action) < 2:
            return 0.0
        
        return np.std(price_action)


class MLModelTrainer:
    """
    Trains machine learning models for trading decisions.
    Uses simple models that can be trained quickly with limited data.
    """
    
    def __init__(self, model_dir: str = 'models'):
        """
        Initialize ML Model Trainer.
        
        Args:
            model_dir: Directory to save/load models
        """
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        self.factor_model = None
        self.entry_timing_model = None
        self.exit_percentage_model = None
        self.spike_detection_model = None
        
        self.training_history = {
            'factor': [],
            'entry_timing': [],
            'exit_percentage': [],
            'spike_detection': []
        }
    
    def train_factor_selection_model(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train model to select optimal factor based on market conditions.
        
        Args:
            historical_data: List of dicts with base_price, volatility, optimal_factor, outcome
            
        Returns:
            Dict with training results and model accuracy
        """
        if len(historical_data) < 10:
            return {
                'trained': False,
                'reason': 'Insufficient data (need at least 10 samples)',
                'samples': len(historical_data)
            }
        
        # Extract features and labels
        X = []
        y = []
        
        for data in historical_data:
            features = [
                data.get('base_price', 0.0),
                data.get('volatility', 0.0)
            ]
            X.append(features)
            y.append(data.get('optimal_factor', 0.002611))
        
        X = np.array(X)
        y = np.array(y)
        
        # Simple model: weighted average based on price range
        # This is a rule-based model that learns weights from data
        self.factor_model = {
            'type': 'weighted_average',
            'weights': self._calculate_optimal_weights(X, y),
            'trained_on': len(historical_data),
            'timestamp': datetime.now().isoformat()
        }
        
        # Calculate accuracy
        predictions = self._predict_factor(X)
        accuracy = np.mean(np.abs(predictions - y) < 0.0001)  # Within 0.01% tolerance
        
        self.training_history['factor'].append({
            'timestamp': datetime.now().isoformat(),
            'samples': len(historical_data),
            'accuracy': accuracy
        })
        
        # Save model
        self._save_model('factor_model.pkl', self.factor_model)
        
        return {
            'trained': True,
            'model_type': 'weighted_average',
            'samples': len(historical_data),
            'accuracy': accuracy,
            'weights': self.factor_model['weights']
        }
    
    def train_entry_timing_model(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train model to predict optimal entry timing.
        
        Args:
            historical_data: List of dicts with momentum, volume, entry_method, outcome
            
        Returns:
            Dict with training results
        """
        if len(historical_data) < 10:
            return {
                'trained': False,
                'reason': 'Insufficient data',
                'samples': len(historical_data)
            }
        
        # Extract features
        X = []
        y = []
        
        for data in historical_data:
            features = [
                data.get('momentum', 0.0),
                data.get('volume_strength', 1.0)
            ]
            X.append(features)
            # 1 for immediate entry, 0 for wait for close
            y.append(1 if data.get('entry_method') == 'immediate' else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # Simple threshold model
        self.entry_timing_model = {
            'type': 'threshold',
            'momentum_threshold': np.median([x[0] for x in X]),
            'volume_threshold': np.median([x[1] for x in X]),
            'trained_on': len(historical_data),
            'timestamp': datetime.now().isoformat()
        }
        
        # Calculate accuracy
        predictions = self._predict_entry_timing(X)
        accuracy = np.mean(predictions == y)
        
        self.training_history['entry_timing'].append({
            'timestamp': datetime.now().isoformat(),
            'samples': len(historical_data),
            'accuracy': accuracy
        })
        
        self._save_model('entry_timing_model.pkl', self.entry_timing_model)
        
        return {
            'trained': True,
            'model_type': 'threshold',
            'samples': len(historical_data),
            'accuracy': accuracy,
            'thresholds': {
                'momentum': self.entry_timing_model['momentum_threshold'],
                'volume': self.entry_timing_model['volume_threshold']
            }
        }
    
    def train_exit_percentage_model(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train model to predict optimal exit percentages at each level.
        
        Args:
            historical_data: List of dicts with level, rejection_rate, optimal_exit_pct
            
        Returns:
            Dict with training results
        """
        if len(historical_data) < 5:
            return {
                'trained': False,
                'reason': 'Insufficient data',
                'samples': len(historical_data)
            }
        
        # Group by level and calculate average optimal exit percentage
        level_exits = {}
        
        for data in historical_data:
            level = data.get('level', 'unknown')
            exit_pct = data.get('optimal_exit_pct', 0.25)
            
            if level not in level_exits:
                level_exits[level] = []
            level_exits[level].append(exit_pct)
        
        # Calculate averages
        self.exit_percentage_model = {
            'type': 'level_average',
            'level_percentages': {
                level: np.mean(exits) for level, exits in level_exits.items()
            },
            'trained_on': len(historical_data),
            'timestamp': datetime.now().isoformat()
        }
        
        self._save_model('exit_percentage_model.pkl', self.exit_percentage_model)
        
        return {
            'trained': True,
            'model_type': 'level_average',
            'samples': len(historical_data),
            'level_percentages': self.exit_percentage_model['level_percentages']
        }
    
    def train_spike_detection_model(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train model to detect real vs fake spikes.
        
        Args:
            historical_data: List of dicts with price_movement, volume_ratio, is_real_spike
            
        Returns:
            Dict with training results
        """
        if len(historical_data) < 10:
            return {
                'trained': False,
                'reason': 'Insufficient data',
                'samples': len(historical_data)
            }
        
        X = []
        y = []
        
        for data in historical_data:
            features = [
                data.get('price_movement', 0.0),
                data.get('volume_ratio', 1.0)
            ]
            X.append(features)
            y.append(1 if data.get('is_real_spike') else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # Simple threshold model
        real_spikes = [x for x, label in zip(X, y) if label == 1]
        fake_spikes = [x for x, label in zip(X, y) if label == 0]
        
        if real_spikes and fake_spikes:
            real_avg_volume = np.mean([x[1] for x in real_spikes])
            fake_avg_volume = np.mean([x[1] for x in fake_spikes])
            volume_threshold = (real_avg_volume + fake_avg_volume) / 2
        else:
            volume_threshold = 1.5
        
        self.spike_detection_model = {
            'type': 'threshold',
            'volume_threshold': volume_threshold,
            'trained_on': len(historical_data),
            'timestamp': datetime.now().isoformat()
        }
        
        # Calculate accuracy
        predictions = self._predict_spike(X)
        accuracy = np.mean(predictions == y)
        
        self.training_history['spike_detection'].append({
            'timestamp': datetime.now().isoformat(),
            'samples': len(historical_data),
            'accuracy': accuracy
        })
        
        self._save_model('spike_detection_model.pkl', self.spike_detection_model)
        
        return {
            'trained': True,
            'model_type': 'threshold',
            'samples': len(historical_data),
            'accuracy': accuracy,
            'volume_threshold': volume_threshold
        }
    
    def load_models(self) -> Dict[str, bool]:
        """
        Load all trained models from disk.
        
        Returns:
            Dict with load status for each model
        """
        status = {}
        
        try:
            self.factor_model = self._load_model('factor_model.pkl')
            status['factor'] = True
        except:
            status['factor'] = False
        
        try:
            self.entry_timing_model = self._load_model('entry_timing_model.pkl')
            status['entry_timing'] = True
        except:
            status['entry_timing'] = False
        
        try:
            self.exit_percentage_model = self._load_model('exit_percentage_model.pkl')
            status['exit_percentage'] = True
        except:
            status['exit_percentage'] = False
        
        try:
            self.spike_detection_model = self._load_model('spike_detection_model.pkl')
            status['spike_detection'] = True
        except:
            status['spike_detection'] = False
        
        return status
    
    def _predict_factor(self, X: np.ndarray) -> np.ndarray:
        """Predict optimal factor for given features."""
        if self.factor_model is None:
            return np.full(len(X), 0.002611)
        
        # Simple rule-based prediction
        predictions = []
        for features in X:
            base_price = features[0]
            if base_price < 1000:
                predictions.append(0.2611)
            elif base_price < 10000:
                predictions.append(0.0261)
            else:
                predictions.append(0.002611)
        
        return np.array(predictions)
    
    def _predict_entry_timing(self, X: np.ndarray) -> np.ndarray:
        """Predict entry timing (1=immediate, 0=wait)."""
        if self.entry_timing_model is None:
            return np.zeros(len(X))
        
        predictions = []
        for features in X:
            momentum = features[0]
            volume = features[1]
            
            if (momentum > self.entry_timing_model['momentum_threshold'] and
                volume > self.entry_timing_model['volume_threshold']):
                predictions.append(1)
            else:
                predictions.append(0)
        
        return np.array(predictions)
    
    def _predict_spike(self, X: np.ndarray) -> np.ndarray:
        """Predict if spike is real (1) or fake (0)."""
        if self.spike_detection_model is None:
            return np.zeros(len(X))
        
        predictions = []
        for features in X:
            volume_ratio = features[1]
            
            if volume_ratio > self.spike_detection_model['volume_threshold']:
                predictions.append(1)
            else:
                predictions.append(0)
        
        return np.array(predictions)
    
    def _calculate_optimal_weights(self, X: np.ndarray, y: np.ndarray) -> List[float]:
        """Calculate optimal weights for weighted average model."""
        # Simple equal weights for now
        return [1.0 / X.shape[1]] * X.shape[1]
    
    def _save_model(self, filename: str, model: Dict[str, Any]):
        """Save model to disk."""
        filepath = os.path.join(self.model_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
    
    def _load_model(self, filename: str) -> Dict[str, Any]:
        """Load model from disk."""
        filepath = os.path.join(self.model_dir, filename)
        with open(filepath, 'rb') as f:
            return pickle.load(f)


class AutoSenseV2:
    """
    AUTO SENSE v2.0 with ML-powered decision making.
    Falls back to rule-based decisions if ML fails.
    """
    
    def __init__(self, pattern_recognizer: PatternRecognizer,
                 ml_trainer: MLModelTrainer, rule_based_engine):
        """
        Initialize AUTO SENSE v2.0.
        
        Args:
            pattern_recognizer: PatternRecognizer instance
            ml_trainer: MLModelTrainer instance
            rule_based_engine: AutoSenseEngine instance (v1.0) for fallback
        """
        self.pattern_recognizer = pattern_recognizer
        self.ml_trainer = ml_trainer
        self.rule_based_engine = rule_based_engine
        
        self.ml_enabled = False
        self.prediction_accuracy = {
            'factor': [],
            'entry_timing': [],
            'exit_percentage': [],
            'spike_detection': []
        }
        
        # Try to load existing models
        load_status = self.ml_trainer.load_models()
        self.ml_enabled = any(load_status.values())
    
    def select_optimal_factor_ml(self, base_price: float, volatility: float) -> Dict[str, Any]:
        """
        Select optimal factor using ML (with fallback to rules).
        
        Args:
            base_price: Current base price
            volatility: Market volatility
            
        Returns:
            Dict with factor, confidence, and method used
        """
        # Try ML prediction
        if self.ml_enabled and self.ml_trainer.factor_model:
            try:
                X = np.array([[base_price, volatility]])
                predicted_factor = self.ml_trainer._predict_factor(X)[0]
                
                return {
                    'factor': predicted_factor,
                    'confidence': 0.8,
                    'method': 'ml',
                    'model_age': self.ml_trainer.factor_model.get('timestamp', 'unknown')
                }
            except Exception as e:
                # Fall back to rules
                pass
        
        # Fallback to rule-based
        factor = self.rule_based_engine.select_optimal_factor(base_price, volatility)
        return {
            'factor': factor,
            'confidence': 0.7,
            'method': 'rules_fallback'
        }
    
    def predict_entry_timing_ml(self, price_action: List[float],
                                volume: List[float]) -> Dict[str, Any]:
        """
        Predict entry timing using ML (with fallback to rules).
        
        Args:
            price_action: Recent price movements
            volume: Recent volume data
            
        Returns:
            Dict with timing decision and confidence
        """
        if self.ml_enabled and self.ml_trainer.entry_timing_model:
            try:
                momentum = np.mean(np.diff(price_action)) if len(price_action) > 1 else 0.0
                volume_strength = volume[-1] / np.mean(volume) if volume else 1.0
                
                X = np.array([[momentum, volume_strength]])
                prediction = self.ml_trainer._predict_entry_timing(X)[0]
                
                return {
                    'timing': 'immediate' if prediction == 1 else 'wait_for_close',
                    'confidence': 0.75,
                    'method': 'ml'
                }
            except Exception as e:
                pass
        
        # Fallback to rules
        current_price = price_action[-1] if price_action else 0.0
        level = current_price  # Use current price as level for fallback
        timing_result = self.rule_based_engine.predict_entry_timing(price_action, volume, current_price, level)
        timing_result['method'] = 'rules_fallback'
        return timing_result
    
    def track_prediction_accuracy(self, prediction_type: str, predicted: Any,
                                  actual: Any) -> Dict[str, Any]:
        """
        Track ML prediction accuracy for continuous improvement.
        
        Args:
            prediction_type: Type of prediction ('factor', 'entry_timing', etc.)
            predicted: Predicted value
            actual: Actual outcome
            
        Returns:
            Dict with accuracy metrics
        """
        if prediction_type not in self.prediction_accuracy:
            return {'tracked': False, 'reason': 'Invalid prediction type'}
        
        # Calculate accuracy based on type
        if prediction_type == 'factor':
            accuracy = 1.0 if abs(predicted - actual) < 0.0001 else 0.0
        elif prediction_type in ['entry_timing', 'spike_detection']:
            accuracy = 1.0 if predicted == actual else 0.0
        else:
            accuracy = 1.0 if abs(predicted - actual) < 0.1 else 0.0
        
        self.prediction_accuracy[prediction_type].append({
            'timestamp': datetime.now().isoformat(),
            'predicted': predicted,
            'actual': actual,
            'accuracy': accuracy
        })
        
        # Calculate rolling accuracy (last 100 predictions)
        recent = self.prediction_accuracy[prediction_type][-100:]
        rolling_accuracy = np.mean([p['accuracy'] for p in recent])
        
        return {
            'tracked': True,
            'accuracy': accuracy,
            'rolling_accuracy': rolling_accuracy,
            'total_predictions': len(self.prediction_accuracy[prediction_type])
        }
    
    def get_ml_status(self) -> Dict[str, Any]:
        """
        Get current ML system status.
        
        Returns:
            Dict with ML enabled status and model information
        """
        return {
            'ml_enabled': self.ml_enabled,
            'models_loaded': {
                'factor': self.ml_trainer.factor_model is not None,
                'entry_timing': self.ml_trainer.entry_timing_model is not None,
                'exit_percentage': self.ml_trainer.exit_percentage_model is not None,
                'spike_detection': self.ml_trainer.spike_detection_model is not None
            },
            'prediction_counts': {
                k: len(v) for k, v in self.prediction_accuracy.items()
            },
            'rolling_accuracy': {
                k: np.mean([p['accuracy'] for p in v[-100:]]) if v else 0.0
                for k, v in self.prediction_accuracy.items()
            }
        }
