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
    
    # 风格分类的样本库（用于快速获取相似风格基金）
    STYLE_SAMPLE_LIBRARY = {
        'stock': [
            '110022',  # 易方达消费行业
            '000968',  # 广发行业领先
            '519674',  # 银河创新成长
            '163402',  # 兴全趋势投资
            '420018',  # 兴全趋势投资混合
            '001943',  # 银河沪深300价值指数
            '410001',  # 华夏成长混合
        ],
        'mixed': [
            '008975',  # 易方达蓝筹精选
            '470018',  # 汇添富均衡增长
            '017043',  # 南方平衡配置
            '003095',  # 中欧医疗健康
            '110022',  # 易方达消费行业
            '519674',  # 银河创新成长
            '570002',  # 诺德成长精选
        ],
        'bond': [
            '007562',  # 景顺长城景泰纯利债券
            '110018',  # 易方达增强回报债券B
            '010011',  # 景顺长城景颐招利6个月持有期债券
            '111002',  # 易方达多策略
            '008638',  # 鹏华固收增强债券
            '008846',  # 华泰柏瑞创新升级
            '160607',  # 鹏华丰收债券
        ],
        'index': [
            '007751',  # 景顺长城沪港深红利成长低波指数
            '021707',  # 富国中证红利低波动ETF联接
            '005533',  # 汇添富均衡增长混合
            '005534',  # 汇添富平衡混合
            '005503',  # 景顺长城沪港深红利成长
            '110029',  # 易方达消费行业ETF
            '510010',  # 易方达上证50ETF
        ],
    }
    
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
        self._portfolio_style_cache = None  # 缓存持仓风格分析
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
        获取推荐基金列表 (排除已持仓基金)
        
        数据来源: 蛋卷基金 API - 实时获取热门基金
        获取方式: 智能降级策略
          - 优先级1: 从蛋卷API获取实时热门基金
          - 优先级2: 基于用户本地持仓风格推荐
          - 优先级3: 返回默认热门基金
        
        Args:
            limit: 返回基金数量上限，默认500
            
        Returns:
            基金代码列表 (不包含已持仓基金)
        """
        try:
            # 📌 第一步：获取用户本地持仓代码（需要排除）
            portfolio_codes = set()
            portfolio_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                "portfolio.json"
            )
            
            try:
                import json
                if os.path.exists(portfolio_file):
                    with open(portfolio_file, 'r', encoding='utf-8') as f:
                        portfolio_data = json.load(f)
                        portfolio_codes = {entry['fund_code'] for entry in portfolio_data}
                        logger.info(f"✓ 已读取本地持仓: {len(portfolio_codes)}只基金")
            except Exception as e:
                logger.debug(f"读取本地持仓失败: {e}")
            
            # 📌 第二步：尝试多个数据源获取推荐基金
            recommended_funds = self._get_recommended_funds_with_fallback(portfolio_codes, limit)
            
            logger.info(f"✓ 生成推荐列表: {len(recommended_funds)}只 (已排除持仓:{len(portfolio_codes)}只)")
            
            return recommended_funds
            
        except Exception as e:
            logger.error(f"获取推荐基金列表失败: {e}")
            return []
    
    def _get_recommended_funds_with_fallback(self, portfolio_codes: set, limit: int) -> List[str]:
        """
        使用智能降级策略获取推荐基金
        
        降级优先级：
        1. 蛋卷API热门基金 (需要实现 API 接口)
        2. 基于持仓风格匹配 (已持仓用户)
        3. 默认热门基金库 (通用方案)
        
        Args:
            portfolio_codes: 用户持仓基金代码集合
            limit: 需要的基金数量
            
        Returns:
            推荐基金列表
        """
        # 策略1：尝试从蛋卷 API 获取热门基金
        try:
            logger.info("尝试策略1: 从蛋卷API获取热门基金...")
            api_funds = self._fetch_from_danjuan_api(portfolio_codes, limit)
            if api_funds and len(api_funds) > 0:
                logger.info(f"✓ 策略1成功: 从蛋卷API获取 {len(api_funds)} 只基金")
                return api_funds
        except Exception as e:
            logger.debug(f"策略1失败: {e}")
        
        # 策略2：基于用户持仓风格推荐
        if portfolio_codes:
            try:
                logger.info("尝试策略2: 基于持仓风格匹配...")
                style_matched = self._get_style_matched_funds(portfolio_codes, limit)
                if style_matched and len(style_matched) > 0:
                    logger.info(f"✓ 策略2成功: 基于风格匹配获得 {len(style_matched)} 只基金")
                    return style_matched
            except Exception as e:
                logger.debug(f"策略2失败: {e}")
        
        # 策略3：返回默认热门基金库
        try:
            logger.info("尝试策略3: 使用默认热门基金库...")
            default_funds = self._get_default_popular_funds(portfolio_codes, limit)
            logger.info(f"✓ 策略3成功: 使用默认库获得 {len(default_funds)} 只基金")
            return default_funds
        except Exception as e:
            logger.error(f"策略3失败: {e}")
        
        logger.warning("所有获取策略都失败，返回空列表")
        return []
    
    def _fetch_from_danjuan_api(self, portfolio_codes: set, limit: int) -> List[str]:
        """
        从蛋卷 API 获取热门基金列表
        
        目前为占位符实现，真实实现需要调用蛋卷 API
        
        Args:
            portfolio_codes: 用户持仓基金代码集合
            limit: 需要的基金数量
            
        Returns:
            推荐基金列表
        """
        try:
            # TODO: 实现真实的蛋卷 API 调用
            # 伪代码示例：
            # response = self.data_fetcher.get_popular_funds(limit=limit*2)
            # recommended = [
            #     fund['code'] for fund in response
            #     if fund['code'] not in portfolio_codes
            # ]
            # return recommended[:limit]
            
            logger.debug("蛋卷API热门基金获取尚未实现")
            raise NotImplementedError("API method not yet implemented")
            
        except Exception as e:
            logger.debug(f"蛋卷API获取失败: {e}")
            raise
    
    def _get_style_matched_funds(self, portfolio_codes: set, limit: int) -> List[str]:
        """
        基于用户本地持仓风格，匹配相似风格的推荐基金
        
        实现逻辑：
        1. 获取用户持仓基金的风格分布
        2. 根据风格分布，从蛋卷获取热门基金
        3. 排除已持仓的基金
        
        Args:
            portfolio_codes: 用户持仓基金代码集合
            limit: 需要的推荐数量
            
        Returns:
            推荐基金代码列表
        """
        try:
            if not portfolio_codes:
                logger.warning("未提供持仓基金代码，无法进行风格匹配")
                return []
            
            # 📌 步骤1：分析用户持仓的风格分布
            portfolio_styles = self._analyze_portfolio_style(portfolio_codes)
            logger.info(f"持仓风格分布: {portfolio_styles}")
            
            # 📌 步骤2：根据风格分布获取推荐基金
            recommended_funds = self._fetch_funds_by_style(portfolio_styles, portfolio_codes, limit)
            logger.info(f"获取到 {len(recommended_funds)} 只相似风格的基金")
            
            return recommended_funds
            
        except Exception as e:
            logger.error(f"风格匹配推荐失败: {e}")
            return []
    
    def _analyze_portfolio_style(self, portfolio_codes: set) -> Dict[str, int]:
        """
        分析用户持仓基金的风格分布
        
        通过获取持仓基金的基本信息，分类为：
        - 股票型 (stock)
        - 混合型 (mixed)
        - 债券型 (bond)
        - 指数型 (index)
        
        Args:
            portfolio_codes: 持仓基金代码集合
            
        Returns:
            风格分布字典 {style: count, ...}
        """
        style_distribution = {
            'stock': 0,
            'mixed': 0,
            'bond': 0,
            'index': 0,
            'other': 0
        }
        
        try:
            for code in list(portfolio_codes)[:10]:  # 最多分析前10只持仓基金
                try:
                    basic_info = self.data_fetcher.fetch_basic_info(code)
                    if not basic_info:
                        continue
                    
                    fund_type = basic_info.fund_type if hasattr(basic_info, 'fund_type') else ""
                    style = self._classify_fund_type(fund_type, code)
                    style_distribution[style] += 1
                    logger.debug(f"基金 {code} 分类为: {style} (类型: {fund_type})")
                    
                except Exception as e:
                    logger.debug(f"分析基金 {code} 风格失败: {e}")
                    style_distribution['other'] += 1
            
            return style_distribution
            
        except Exception as e:
            logger.error(f"分析投资组合风格失败: {e}")
            return style_distribution
    
    def _classify_fund_type(self, fund_type: str, fund_code: str) -> str:
        """
        将基金类型分类为标准风格标签
        
        Args:
            fund_type: 基金类型字符串
            fund_code: 基金代码（备用）
            
        Returns:
            分类结果: 'stock', 'mixed', 'bond', 'index', 'other'
        """
        fund_type_lower = fund_type.lower()
        
        # 债券型
        if any(kw in fund_type_lower for kw in ['债券', 'bond', '固定收益']):
            return 'bond'
        
        # 指数型
        if any(kw in fund_type_lower for kw in ['指数', 'index', 'etf', '被动']):
            return 'index'
        
        # 股票型
        if any(kw in fund_type_lower for kw in ['股票', 'stock', '激进']):
            return 'stock'
        
        # 混合型
        if any(kw in fund_type_lower for kw in ['混合', 'mixed', '混']):
            return 'mixed'
        
        return 'other'
    
    def _fetch_funds_by_style(self, style_distribution: Dict[str, int], portfolio_codes: set, limit: int) -> List[str]:
        """
        根据风格分布从蛋卷获取推荐基金
        
        策略：
        1. 按风格权重，从蛋卷热门基金列表中获取对应的基金
        2. 排除用户已持仓的基金
        3. 返回推荐列表
        
        Args:
            style_distribution: 风格分布 {style: count}
            portfolio_codes: 用户持仓基金集合
            limit: 需要的数量
            
        Returns:
            推荐基金代码列表
        """
        recommended_funds = []
        
        try:
            # 计算总数，用于计算权重
            total_style_count = sum(style_distribution.values())
            if total_style_count == 0:
                logger.warning("未找到有效的持仓风格，使用默认推荐")
                return self._get_default_popular_funds(portfolio_codes, limit)
            
            # 📌 根据风格权重分配推荐数量
            style_weights = {
                style: (count / total_style_count) 
                for style, count in style_distribution.items() 
                if count > 0
            }
            
            logger.info(f"风格权重: {style_weights}")
            
            # 📌 为每个风格获取相应数量的基金
            for style, weight in style_weights.items():
                target_count = max(1, int(limit * weight))
                
                try:
                    # 从蛋卷获取该风格的热门基金
                    style_funds = self._get_style_popular_funds(style, target_count * 2)  # 获取2倍数量便于过滤
                    
                    # 排除已持仓基金
                    style_funds_filtered = [
                        code for code in style_funds 
                        if code not in portfolio_codes and code not in recommended_funds
                    ]
                    
                    # 添加到推荐列表
                    recommended_funds.extend(style_funds_filtered[:target_count])
                    logger.info(f"风格 {style}: 添加 {len(style_funds_filtered[:target_count])} 只基金")
                    
                except Exception as e:
                    logger.debug(f"获取风格 {style} 的基金失败: {e}")
            
            # 如果推荐数不足，补充默认热门基金
            if len(recommended_funds) < limit:
                default_funds = self._get_default_popular_funds(portfolio_codes, limit - len(recommended_funds))
                recommended_funds.extend(default_funds)
                logger.info(f"补充默认热门基金: +{len(default_funds)}只")
            
            return recommended_funds[:limit]
            
        except Exception as e:
            logger.error(f"按风格获取基金失败: {e}")
            # 降级：返回默认热门基金
            return self._get_default_popular_funds(portfolio_codes, limit)
    
    def _get_style_popular_funds(self, style: str, limit: int) -> List[str]:
        """
        从蛋卷获取特定风格的热门基金
        
        优先使用蛋卷 API，降级到本地样本库
        
        Args:
            style: 风格类型 ('stock', 'mixed', 'bond', 'index', 'other')
            limit: 需要的数量
            
        Returns:
            基金代码列表
        """
        try:
            # TODO: 调用蛋卷 API 获取特定风格的基金列表
            # 示例实现（需要根据蛋卷API文档调整）：
            # response = self.data_fetcher.get_funds_by_category(style, limit=limit)
            # return [fund['code'] for fund in response]
            
            logger.debug(f"从蛋卷获取风格 {style} 的基金 (limit={limit})")
            
            # 降级方案：使用类级别的样本库
            # 这是一个通用的样本库，包含各风格的热门基金
            funds = self.STYLE_SAMPLE_LIBRARY.get(style, [])
            
            # 如果样本库中没有该风格，返回默认库中的部分基金
            if not funds:
                logger.warning(f"样本库中未找到风格 {style}，使用默认基金")
                funds = [
                    '008975', '110022', '007751',  # 各风格代表性基金
                    '007562', '470018', '519674',
                ]
            
            logger.info(f"返回风格 {style} 的 {len(funds[:limit])} 只基金 (from {len(funds)} available)")
            
            return funds[:limit]
            
        except Exception as e:
            logger.warning(f"获取风格 {style} 的基金失败: {e}")
            # 应急方案：返回最安全的几个基金
            return ['110022', '008975', '007751'][:limit]
    
    def _get_default_popular_funds(self, exclude_codes: set, limit: int) -> List[str]:
        """
        获取默认热门基金（排除指定的基金）
        
        使用一个通用的热门基金库，包含各风格的优质基金
        
        Args:
            exclude_codes: 需要排除的基金代码集合
            limit: 需要的数量
            
        Returns:
            推荐基金代码列表
        """
        # 通用热门基金库（从各风格精选）
        default_popular_funds = [
            # 混合型（均衡）
            '008975', '470018', '017043',
            # 股票型（成长）
            '110022', '519674', '420018', '163402',
            # 医疗健康（行业）
            '003095',
            # 指数型
            '007751', '021707', '005533',
            # 债券型
            '007562', '110018', '010011',
        ]
        
        # 过滤已排除的基金
        filtered_funds = [
            code for code in default_popular_funds
            if code not in exclude_codes
        ]
        
        logger.info(f"返回默认热门基金: {len(filtered_funds[:limit])} 只 (from {len(default_popular_funds)})")
        
        return filtered_funds[:limit]
    
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
