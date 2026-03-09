"""
推荐引擎单元测试
验证评分算法、排序和推荐逻辑
"""

import sys
import os

# 添加脚本目录到路径
_scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, os.path.dirname(_scripts_dir))

import unittest
from scripts.models import (
    TechnicalIndicators, HoldingAnalysis, ManagerInfo,
    PerformanceData, SentimentData, FundRealtimeQuote
)
from scripts.recommendation_engine import (
    FundScorer, FundRanker, FundRecommendationInput, FundScore
)
from scripts.recommendation_advisor import RecommendationCardGenerator, RecommendationReportGenerator


class TestFundScorer(unittest.TestCase):
    """测试基金评分器"""
    
    def setUp(self):
        """设置测试环境"""
        self.scorer = FundScorer()
    
    def test_score_technical_uptrend(self):
        """测试技术面评分：上升趋势"""
        technical = TechnicalIndicators(
            trend="上升",
            signals=["金叉", "突破"],
            price=10.5,
            ma_20=10.2,
            ma_50=9.8
        )
        score = self.scorer._score_technical(technical)
        self.assertGreater(score, 60)  # 上升趋势应该得分较高
    
    def test_score_technical_downtrend(self):
        """测试技术面评分：下降趋势"""
        technical = TechnicalIndicators(
            trend="下降",
            signals=[],
            price=9.5,
            ma_20=10.2,
            ma_50=10.8
        )
        score = self.scorer._score_technical(technical)
        self.assertLess(score, 50)  # 下降趋势应该得分较低
    
    def test_score_technical_no_data(self):
        """测试技术面评分：无数据"""
        score = self.scorer._score_technical(None)
        self.assertEqual(score, 50.0)  # 无数据返回默认分数
    
    def test_score_fundamental_high_return(self):
        """测试基本面评分：高收益"""
        performance = PerformanceData(
            return_1y=25.0,
            return_3y=60.0,
            return_5y=100.0,
            max_drawdown=-15.0,
            rank_percentile=85.0
        )
        manager = ManagerInfo(
            manager_name="资深经理",
            manage_years=10,
            is_senior=True
        )
        holding = HoldingAnalysis(
            holding_concentration=35.0,
            top_10_concentration=45.0,
            top_10_holdings=[]
        )
        
        score = self.scorer._score_fundamental(holding, manager, performance)
        self.assertGreater(score, 80)  # 高收益和资深经理应该得分高
    
    def test_score_sentiment(self):
        """测试舆情评分"""
        sentiment = SentimentData(
            score=75.0,
            level="正面",
            keywords=["分红", "优秀"]
        )
        score = self.scorer._score_sentiment(sentiment)
        self.assertEqual(score, 75.0)
    
    def test_determine_risk_level_high(self):
        """测试风险等级判断：高风险"""
        performance = PerformanceData(
            max_drawdown=-30.0,  # 最大回撤 > 25%
            return_1y=15.0,
            return_3y=40.0
        )
        technical = TechnicalIndicators(
            trend="下降",
            signals=[],
            price=9.5
        )
        
        risk_level = self.scorer._determine_risk_level(performance, technical)
        self.assertEqual(risk_level, "高")
    
    def test_determine_risk_level_low(self):
        """测试风险等级判断：低风险"""
        performance = PerformanceData(
            max_drawdown=-8.0,
            return_1y=5.0,
            return_3y=15.0
        )
        technical = TechnicalIndicators(
            trend="上升",
            signals=["金叉"],
            price=10.5
        )
        
        risk_level = self.scorer._determine_risk_level(performance, technical)
        self.assertEqual(risk_level, "低")
    
    def test_complete_scoring(self):
        """测试完整的基金评分流程"""
        fund_data = FundRecommendationInput(
            fund_code="007751",
            fund_name="测试基金",
            technical=TechnicalIndicators(
                trend="上升",
                signals=["金叉", "突破"],
                price=10.5,
                ma_20=10.0,
                ma_50=9.5
            ),
            holding=HoldingAnalysis(
                holding_concentration=35.0,
                top_10_concentration=45.0,
                top_10_holdings=[]
            ),
            manager=ManagerInfo(
                manager_name="资深经理",
                manage_years=10,
                is_senior=True
            ),
            performance=PerformanceData(
                return_1y=15.0,
                return_3y=50.0,
                max_drawdown=-10.0,
                rank_percentile=80.0,
                return_5y=100.0
            ),
            sentiment=SentimentData(
                score=70.0,
                level="正面",
                keywords=["优秀"]
            ),
            quote=FundRealtimeQuote(
                fund_code="007751",
                price=10.5,
                change_percent=2.5
            )
        )
        
        score = self.scorer.score(fund_data)
        
        # 验证评分对象
        self.assertEqual(score.fund_code, "007751")
        self.assertEqual(score.fund_name, "测试基金")
        self.assertGreater(score.total_score, 0)
        self.assertLessEqual(score.total_score, 100)
        self.assertIn(score.risk_level, ["低", "中", "高"])
        self.assertTrue(len(score.reason) > 0)


class TestFundRanker(unittest.TestCase):
    """测试基金排序器"""
    
    def setUp(self):
        """设置测试环境"""
        self.fund_scores = [
            FundScore("007751", "基金A", 75.0, 70.0, 80.0, 75.0, "中", "优秀"),
            FundScore("110022", "基金B", 65.0, 60.0, 70.0, 65.0, "中", "良好"),
            FundScore("003095", "基金C", 85.0, 80.0, 90.0, 85.0, "高", "非常优秀"),
            FundScore("017043", "基金D", 55.0, 50.0, 60.0, 55.0, "低", "一般"),
        ]
    
    def test_rank_by_score(self):
        """测试按评分排序"""
        ranked = FundRanker.rank(self.fund_scores)
        
        # 验证排序正确（从高到低）
        self.assertEqual(ranked[0].fund_code, "003095")  # 85分
        self.assertEqual(ranked[1].fund_code, "007751")  # 75分
        self.assertEqual(ranked[2].fund_code, "110022")  # 65分
        self.assertEqual(ranked[3].fund_code, "017043")  # 55分
    
    def test_rank_filter_by_risk(self):
        """测试按风险等级筛选"""
        ranked = FundRanker.rank(self.fund_scores, risk_level="中")
        
        # 验证只有中风险的基金
        self.assertEqual(len(ranked), 2)
        self.assertTrue(all(f.risk_level == "中" for f in ranked))
    
    def test_rank_top_n(self):
        """测试返回前N个"""
        ranked = FundRanker.rank(self.fund_scores, top_n=2)
        
        # 验证只返回前2个
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].fund_code, "003095")
        self.assertEqual(ranked[1].fund_code, "007751")
    
    def test_rank_filter_and_limit(self):
        """测试同时筛选和限制数量"""
        ranked = FundRanker.rank(
            self.fund_scores,
            risk_level="中",
            top_n=1
        )
        
        # 验证筛选和数量限制
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].fund_code, "007751")  # 中风险中评分最高


class TestRecommendationCardGenerator(unittest.TestCase):
    """测试推荐卡片生成器"""
    
    def test_generate_card(self):
        """测试生成推荐卡片"""
        fund_score = FundScore(
            "007751",
            "景顺长城沪港深红利成长低波指数A",
            75.0,
            70.0,
            80.0,
            75.0,
            "中",
            "基金表现优异，技术面良好"
        )
        
        card = RecommendationCardGenerator.generate_card(
            rank=1,
            fund_score=fund_score
        )
        
        # 验证卡片内容
        self.assertIn("景顺长城沪港深红利成长低波指数A", card)
        self.assertIn("007751", card)
        self.assertIn("75.0/100", card)
        self.assertIn("基金表现优异", card)


class TestRecommendationReportGenerator(unittest.TestCase):
    """测试推荐报告生成器"""
    
    def test_generate_report(self):
        """测试生成推荐报告"""
        fund_scores = [
            FundScore("007751", "基金A", 75.0, 70.0, 80.0, 75.0, "中", "优秀"),
            FundScore("110022", "基金B", 65.0, 60.0, 70.0, 65.0, "中", "良好"),
        ]
        
        report = RecommendationReportGenerator.generate_report(
            fund_scores,
            risk_level="中",
            investment_period="long",
            scan_count=5000
        )
        
        # 验证报告内容
        self.assertIn("推荐基金列表", report)
        self.assertIn("中风险", report)
        self.assertIn("长期", report)
        self.assertIn("5000+", report)
        self.assertIn("007751", report)
        self.assertIn("110022", report)
        self.assertIn("免责声明", report)


class TestPropertyBasedTests(unittest.TestCase):
    """属性基础测试 - 验证通用正确性属性"""
    
    def setUp(self):
        """设置测试环境"""
        self.scorer = FundScorer()
        self.ranker = FundRanker()
    
    def test_property_score_bounds(self):
        """属性：评分总是在 0-100 之间"""
        test_cases = [
            TechnicalIndicators(trend="上升", signals=["金叉", "突破"], price=10.5),
            TechnicalIndicators(trend="震荡", signals=[], price=10.0),
            TechnicalIndicators(trend="下降", signals=[], price=9.5),
            None,
        ]
        
        for technical in test_cases:
            score = self.scorer._score_technical(technical)
            self.assertGreaterEqual(score, 0, f"技术面评分 {score} 低于 0")
            self.assertLessEqual(score, 100, f"技术面评分 {score} 高于 100")
    
    def test_property_rank_idempotence(self):
        """属性：排序两次应该得到相同结果"""
        fund_scores = [
            FundScore("001", "基金1", 75.0, 70.0, 80.0, 75.0, "中", "优秀"),
            FundScore("002", "基金2", 65.0, 60.0, 70.0, 65.0, "中", "良好"),
            FundScore("003", "基金3", 85.0, 80.0, 90.0, 85.0, "高", "非常优秀"),
        ]
        
        # 排序一次
        ranked_1 = self.ranker.rank(fund_scores)
        # 排序第二次（使用之前的排序结果）
        ranked_2 = self.ranker.rank(ranked_1)
        
        # 验证两次排序结果相同
        for r1, r2 in zip(ranked_1, ranked_2):
            self.assertEqual(r1.fund_code, r2.fund_code)
            self.assertEqual(r1.total_score, r2.total_score)
    
    def test_property_rank_preserves_best(self):
        """属性：排序后，评分最高的基金应该排在第一位"""
        fund_scores = [
            FundScore("001", "基金1", 75.0, 70.0, 80.0, 75.0, "中", "优秀"),
            FundScore("002", "基金2", 65.0, 60.0, 70.0, 65.0, "中", "良好"),
            FundScore("003", "基金3", 85.0, 80.0, 90.0, 85.0, "高", "非常优秀"),
            FundScore("004", "基金4", 55.0, 50.0, 60.0, 55.0, "低", "一般"),
        ]
        
        ranked = self.ranker.rank(fund_scores)
        
        # 找到原始列表中的最高分
        max_score = max(f.total_score for f in fund_scores)
        
        # 验证排序后第一个是最高分
        self.assertEqual(ranked[0].total_score, max_score)


if __name__ == '__main__':
    unittest.main()
