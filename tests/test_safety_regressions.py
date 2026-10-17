"""用合成数据验证评分和风险指标的证据边界，不调用网络。"""
import json
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import Mock

import numpy as np
import pytest

from scripts.analysis_v2.strategies import IndexFundStrategy, ActiveFundStrategy, StrategyRouter
from scripts.analysis_v2.risk_analyzer import RiskAnalyzer
from scripts.models import FundBasicInfo, FundNavHistory, PerformanceData
from scripts.fund_analyzer_v2 import FundAnalyzerV2
from scripts.portfolio_analyzer import PortfolioAnalyzer
from scripts.technical_analysis import TechnicalAnalyzer


@pytest.mark.parametrize('strategy', [IndexFundStrategy(), ActiveFundStrategy()])
def test_zero_is_not_missing(strategy):
    scores = strategy.calculate_scores(technical=0, fundamental=0, valuation=0, capital_flow=0, sentiment=0)
    assert scores.total == 0
    assert scores.valuation == 0


@pytest.mark.parametrize('kind', ['债券型', '债券指数', '货币型', '混合型FOF', '目标日期', '目标风险', '偏债混合', '', None, '未知'])
def test_unsupported_type_never_uses_equity_strategy(kind):
    with pytest.raises(ValueError):
        StrategyRouter().route(FundBasicInfo(fund_code='000001', fund_name='合成基金', fund_type=kind))


def test_missing_benchmark_never_generates_relative_metrics():
    risk = RiskAnalyzer()
    returns = np.array([0.01, -0.02, 0.005, 0.01] * 20)
    assert risk._calculate_alpha_beta(returns) == (None, None)
    assert risk._calculate_info_ratio(returns) is None
    assert risk._calculate_alpha_beta(returns, returns[:-1]) == (None, None)


def test_beta_uses_same_sample_variance_as_covariance():
    risk = RiskAnalyzer()
    market = np.array([0.01, -0.02, 0.005, 0.004] * 20)
    _, beta = risk._calculate_alpha_beta(2 * market, market)
    assert beta == pytest.approx(2)
    assert risk._calculate_alpha_beta(market, np.ones(80)) == (None, None)


def test_downside_uses_full_sample_and_no_artificial_epsilon():
    risk = RiskAnalyzer()
    returns = np.array([-0.02, 0.02] * 40)
    assert risk._calculate_downside_deviation(returns) == pytest.approx(np.sqrt(0.0002 * 252))
    assert risk._calculate_downside_deviation(np.ones(80) * .001) == 0
    assert risk._calculate_sortino_ratio(np.ones(80) * .001) is None


def test_zero_volatility_survives_serialization():
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(80)]
    risk = RiskAnalyzer().analyze(FundNavHistory(fund_code='000001', dates=dates, navs=[1.] * 80))
    assert risk.volatility == 0
    assert risk.downside_deviation == 0
    assert risk.alpha is None and risk.beta is None and risk.info_ratio is None


def test_benchmark_requires_identical_dates():
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(80)]
    prices = np.cumprod(1 + np.array([.01, -.005] * 40)).tolist()
    fund = FundNavHistory(fund_code='000001', dates=dates, navs=prices)
    benchmark = FundNavHistory(fund_code='000002', dates=dates, navs=prices)
    assert RiskAnalyzer().analyze(fund, benchmark).beta == pytest.approx(1)
    benchmark.dates = list(reversed(dates))
    assert RiskAnalyzer().analyze(fund, benchmark).beta is None


def test_one_period_return_needs_two_observations():
    tech = TechnicalAnalyzer()
    assert tech.calculate_return([1., 1.1], 1) == pytest.approx(10)
    assert tech.calculate_return([1.], 1) is None
    assert tech.calculate_return([1., 1.1], 0) is None


def test_missing_valuation_cannot_be_replaced_with_price_performance():
    analyzer = FundAnalyzerV2()
    assert analyzer._calc_valuation_score(None, PerformanceData(return_1y=50)) is None


def test_all_missing_data_produces_explicit_unavailable_report(tmp_path):
    analyzer = FundAnalyzerV2()
    for name in ('fetch_basic_info', 'fetch_nav_history', 'fetch_realtime_quote', 'fetch_performance', 'fetch_manager_info'):
        setattr(analyzer.data_fetcher, name, Mock(return_value=None))
    analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=None)
    analyzer.report_generator.DEFAULT_BASE_DIR = str(tmp_path)
    html, path = analyzer.analyze('000001', enable_sip=True)
    data = json.loads(open(path, encoding='utf-8').read())
    assert data['scores'] is None
    assert data['valuation'] is None
    assert data['action'] == '不可评价'
    assert data['position_advice']['target_amount'] is None
    assert data['sip_advice']['recommended_amount'] is None
    assert data['data_quality']['score_available'] is False
    assert Path(html).is_file()


@pytest.mark.parametrize('payload', [None, {'total': None}, {'total': 50}])
def test_portfolio_does_not_turn_unavailable_scores_into_hold(tmp_path, payload):
    path = tmp_path/'report.json'
    path.write_text(json.dumps({'scores': payload}), encoding='utf-8')
    analyzer = PortfolioAnalyzer()
    analyzer.v2_analyzer.analyze = Mock(return_value=('unused.html', str(path)))
    with pytest.raises(ValueError, match='组合报告已停止'):
        analyzer._analyze_with_v2('000001')


def test_portfolio_does_not_infer_risk_level_from_attractiveness():
    analyzer = PortfolioAnalyzer()
    assert analyzer._score_to_risk(100) == analyzer._score_to_risk(0) == '待核实'


def test_configuration_failure_does_not_invent_target_allocation():
    analyzer = FundAnalyzerV2()
    analyzer.position_manager.get_config = Mock(side_effect=OSError('合成配置读取失败'))
    scores = IndexFundStrategy().calculate_scores(
        technical=80, fundamental=80, valuation=80, capital_flow=80, sentiment=80)
    advice = analyzer._generate_position_advice('000001', None, scores)
    assert advice['action'] == '不可评价'
    assert advice['target_pct'] is None
    assert advice['target_amount'] is None
