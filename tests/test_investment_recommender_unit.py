"""
Unit tests for InvestmentRecommender class.
Tests BE5 reversal detection and stock categorization.
"""

import pytest
from src.main import InvestmentRecommender, LevelCalculator


class TestBE5ReversalScanning:
    """Test BE5 reversal opportunity scanning."""
    
    def test_scan_finds_be5_opportunities(self):
        """Test scanning finds stocks near BE5."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        stocks = [
            {'symbol': 'STOCK1', 'current_price': 100.0, 'first_close': 120.0},
            {'symbol': 'STOCK2', 'current_price': 200.0, 'first_close': 200.0},
        ]
        
        candidates = recommender.scan_nfo_stocks_for_be5_reversals(stocks, 'monthly')
        
        assert isinstance(candidates, list)
        for candidate in candidates:
            assert 'symbol' in candidate
            assert 'be5_level' in candidate
            assert 'distance_percent' in candidate
    
    def test_scan_includes_timeframe(self):
        """Test scan includes timeframe in results."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        stocks = [
            {'symbol': 'STOCK1', 'current_price': 100.0, 'first_close': 105.0},
        ]
        
        candidates = recommender.scan_nfo_stocks_for_be5_reversals(stocks, 'yearly')
        
        for candidate in candidates:
            assert candidate['timeframe'] == 'yearly'


class TestCandidateRanking:
    """Test investment candidate ranking."""
    
    def test_rank_by_distance(self):
        """Test candidates ranked by distance to BE5."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        candidates = [
            {'symbol': 'A', 'distance_percent': 1.0, 'score': 0},
            {'symbol': 'B', 'distance_percent': 0.5, 'score': 0},
            {'symbol': 'C', 'distance_percent': 1.5, 'score': 0},
        ]
        
        ranked = recommender.rank_investment_candidates(candidates)
        
        # Closer to BE5 should rank higher
        assert ranked[0]['symbol'] == 'B'
        assert ranked[0]['score'] > ranked[1]['score']
    
    def test_rank_includes_score(self):
        """Test ranking adds score to candidates."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        candidates = [
            {'symbol': 'A', 'distance_percent': 1.0},
        ]
        
        ranked = recommender.rank_investment_candidates(candidates)
        
        assert 'score' in ranked[0]
        assert ranked[0]['score'] > 0


class TestStockCategorization:
    """Test stock categorization as Good/Bad/Ugly."""
    
    def test_categorize_good_stocks(self):
        """Test stocks above BU3 categorized as Good."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        # Calculate levels first to know BU3
        levels_data = calc.calculate_levels(100.0, '1d')
        bu3_price = levels_data['bu3']
        
        stocks = [
            {'symbol': 'GOOD1', 'current_price': bu3_price + 1.0},  # Above BU3
        ]
        
        levels = {
            'GOOD1': levels_data
        }
        
        categories = recommender.categorize_stocks(stocks, levels)
        
        assert 'GOOD1' in categories['good']
    
    def test_categorize_ugly_stocks(self):
        """Test stocks below BE3 categorized as Ugly."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        # Calculate levels first to know BE3
        levels_data = calc.calculate_levels(100.0, '1d')
        be3_price = levels_data['be3']
        
        stocks = [
            {'symbol': 'UGLY1', 'current_price': be3_price - 1.0},  # Below BE3
        ]
        
        levels = {
            'UGLY1': levels_data
        }
        
        categories = recommender.categorize_stocks(stocks, levels)
        
        assert 'UGLY1' in categories['ugly']
    
    def test_categorize_bad_stocks(self):
        """Test stocks between BE1 and BU1 categorized as Bad."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        stocks = [
            {'symbol': 'BAD1', 'current_price': 100.0},
        ]
        
        levels = {
            'BAD1': calc.calculate_levels(100.0, '1d')
        }
        
        categories = recommender.categorize_stocks(stocks, levels)
        
        assert 'BAD1' in categories['bad']


class TestDailyReviewSheet:
    """Test daily investment review sheet generation."""
    
    def test_generate_review_sheet(self):
        """Test review sheet generation."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        stocks = [
            {'symbol': 'STOCK1', 'current_price': 100.0, 'first_close': 100.0},
            {'symbol': 'STOCK2', 'current_price': 200.0, 'first_close': 200.0},
        ]
        
        review = recommender.generate_daily_review_sheet(stocks, '2026-02-18')
        
        assert review['date'] == '2026-02-18'
        assert review['total_stocks'] == 2
        assert 'categories' in review
        assert 'be5_opportunities' in review
    
    def test_review_includes_top_recommendation(self):
        """Test review includes top recommendation."""
        calc = LevelCalculator()
        recommender = InvestmentRecommender(calc)
        
        stocks = [
            {'symbol': 'STOCK1', 'current_price': 100.0, 'first_close': 105.0},
        ]
        
        review = recommender.generate_daily_review_sheet(stocks, '2026-02-18')
        
        if review['be5_opportunities']:
            assert review['top_recommendation'] is not None
