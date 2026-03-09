"""
基金推荐器 - 主推荐类
整合评分、排序、报告生成
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from scripts.data_fetcher import DanjuanDataFetcher
from scripts.technical_analysis import TechnicalAnalyzer
from scripts.holding_analysis import HoldingAnalyzer
from scripts.manager_analysis import ManagerAnalyzer
from scripts.performance_analysis import PerformanceAnalyzer
from scripts.sentiment_analysis import SentimentAnalyzer
from scripts.recommendation_engine import FundScorer, FundRanker, FundRecommendationInput, FundScore
from scripts.recommendation_advisor import RecommendationReportGenerator, RecommendationCardGenerator
from scripts.report_generator import ReportGenerator
from scripts.logger import logger


class FundRecommender:
    """基金推荐器"""
    
    def __init__(self):
        """初始化推荐器"""
        self.data_fetcher = DanjuanDataFetcher()
        self.technical_analyzer = TechnicalAnalyzer()
        self.holding_analyzer = HoldingAnalyzer()
        self.manager_analyzer = ManagerAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.scorer = FundScorer()
        self.report_generator = ReportGenerator()
        logger.info("FundRecommender initialized")
    
    def recommend(
        self,
        risk_level: Optional[str] = None,
        investment_period: Optional[str] = None,
        top_n: int = 10,
        fund_codes: Optional[List[str]] = None,
        max_workers: int = 5
    ) -> str:
        """
        推荐基金
        
        Args:
            risk_level: 风险等级 (低/中/高, None表示不筛选)
            investment_period: 投资期限 (short/medium/long)
            top_n: 返回前N个推荐基金
            fund_codes: 基金代码列表，如果不提供则获取热门基金
            max_workers: 并发线程数
            
        Returns:
            推荐报告 (Markdown格式)
        """
        try:
            logger.info(f"开始推荐基金: risk_level={risk_level}, period={investment_period}, top_n={top_n}")
            
            # 获取基金列表
            if not fund_codes:
                fund_codes = self._get_popular_funds()
                logger.info(f"获取热门基金列表: {len(fund_codes)}只")
            
            # 并发分析基金
            fund_scores = self._analyze_funds_parallel(fund_codes, max_workers)
            logger.info(f"完成分析: {len(fund_scores)}只基金")
            
            # 排序筛选
            ranked_funds = FundRanker.rank(
                fund_scores,
                risk_level=risk_level,
                investment_period=investment_period,
                top_n=top_n
            )
            logger.info(f"排序后推荐: {len(ranked_funds)}只")
            
            # 生成报告
            report = RecommendationReportGenerator.generate_report(
                ranked_funds,
                risk_level=risk_level,
                investment_period=investment_period,
                scan_count=len(fund_codes)
            )
            
            return report
        
        except Exception as e:
            logger.error(f"推荐失败: {e}", exc_info=True)
            return f"# 推荐失败\n\n错误: {str(e)}\n"
    
    def _get_popular_funds(self, limit: int = 500) -> List[str]:
        """
        获取热门基金列表
        
        目前使用蛋卷基金的热门基金列表
        后续可扩展为多个来源
        """
        try:
            # 这里可以调用蛋卷 API 获取热门基金列表
            # 目前先返回一个预设列表
            popular_funds = [
                "007751",  # 景顺长城沪港深红利成长低波指数A
                "008975",  # 易方达蓝筹精选混合
                "003095",  # 中欧医疗健康混合A
                "017043",  # 南方平衡配置混合
                "110022",  # 易方达消费行业
                "420018",  # 兴全趋势投资混合
                "470018",  # 汇添富均衡增长混合
                "519674",  # 银河创新成长混合
                "163402",  # 兴全趋势投资混合
                "000968",  # 广发行业领先混合
                # 更多热门基金可根据需要添加
            ]
            return popular_funds[:limit]
        except Exception as e:
            logger.warning(f"获取热门基金列表失败: {e}")
            return []
    
    def _analyze_funds_parallel(
        self,
        fund_codes: List[str],
        max_workers: int = 5
    ) -> List[FundScore]:
        """并发分析多只基金并评分"""
        fund_scores = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._analyze_and_score_fund, code): code
                for code in fund_codes
            }
            
            for future in as_completed(futures):
                try:
                    score = future.result()
                    if score:
                        fund_scores.append(score)
                except Exception as e:
                    code = futures[future]
                    logger.warning(f"分析基金 {code} 失败: {e}")
        
        return fund_scores
    
    def _analyze_and_score_fund(self, fund_code: str) -> Optional[FundScore]:
        """分析单只基金并评分"""
        try:
            # 并发获取各种数据
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    'basic': executor.submit(self.data_fetcher.fetch_basic_info, fund_code),
                    'quote': executor.submit(self.data_fetcher.fetch_realtime_quote, fund_code),
                    'nav': executor.submit(self.data_fetcher.fetch_nav_history, fund_code, 365),
                    'holding': executor.submit(self.data_fetcher.fetch_holdings, fund_code),
                    'manager': executor.submit(self.data_fetcher.fetch_manager_info, fund_code),
                    'performance': executor.submit(self.data_fetcher.fetch_performance, fund_code),
                }
                
                data = {}
                for key, future in futures.items():
                    try:
                        data[key] = future.result()
                    except Exception as e:
                        logger.debug(f"获取 {fund_code} {key} 失败: {e}")
                        data[key] = None
            
            basic_info = data.get('basic')
            if not basic_info:
                return None
            
            # 执行分析
            nav_history = data.get('nav')
            quote = data.get('quote')
            holding = data.get('holding')
            manager = data.get('manager')
            performance = data.get('performance')
            
            technical = None
            if nav_history and quote:
                technical = self.technical_analyzer.analyze(nav_history, quote)
            
            if holding:
                holding = self.holding_analyzer.analyze(holding)
            
            if manager and performance:
                manager = self.manager_analyzer.analyze(manager, performance)
            
            if performance:
                performance = self.performance_analyzer.analyze(performance)
            
            sentiment = None
            try:
                sentiment = self.sentiment_analyzer.analyze(fund_code, basic_info.fund_name, False, self.data_fetcher)
            except Exception as e:
                logger.debug(f"舆情分析失败 {fund_code}: {e}")
            
            # 评分
            fund_input = FundRecommendationInput(
                fund_code=fund_code,
                fund_name=basic_info.fund_name,
                technical=technical,
                holding=holding,
                manager=manager,
                performance=performance,
                sentiment=sentiment,
                quote=quote
            )
            
            score = self.scorer.score(fund_input)
            return score
        
        except Exception as e:
            logger.error(f"分析并评分基金 {fund_code} 失败: {e}")
            return None
    
    def save_recommendation_report(self, report: str, risk_level: Optional[str] = None) -> str:
        """保存推荐报告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            risk_label = risk_level or "all"
            filename = f"recommend_{risk_label}_{timestamp}.md"
            
            # 保存到按日期分目录的结构
            date_str = datetime.now().strftime("%Y%m%d")
            reports_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "reports",
                date_str
            )
            os.makedirs(reports_dir, exist_ok=True)
            
            file_path = os.path.join(reports_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"推荐报告已保存: {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"保存推荐报告失败: {e}")
            return ""
