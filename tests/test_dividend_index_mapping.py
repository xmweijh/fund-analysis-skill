"""防止相似的红利产品名称错误共用指数估值。"""
from unittest.mock import Mock
import pytest
from scripts.fund_analyzer_v2 import FundAnalyzerV2, _DIVIDEND_INDEX_TARGETS
from scripts.models import FundBasicInfo, ValuationData


def test_three_different_targets_remain_distinct():
    assert {r['index_code'] for r in _DIVIDEND_INDEX_TARGETS.values()} == {'H30269', '931157', 'SPCLLHCP'}


def test_csi_dividend_target_requests_matching_valuation():
    analyzer = FundAnalyzerV2()
    value = ValuationData(pe_percentile=50)
    analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=value)
    assert analyzer._fetch_valuation('007466', None) is value
    analyzer.valuation_fetcher.fetch_index_valuation.assert_called_once_with('CSIH30269')


@pytest.mark.parametrize('code,name', [
    ('007751', '景顺长城沪港深红利成长低波指数A'),
    ('008163', '南方标普红利低波50ETF联接A'),
    ('999999', '某中证红利低波动100指数基金'),
    ('999998', '某红利成长LV基金'),
])
def test_unverified_provider_mapping_does_not_borrow_another_index(code, name):
    analyzer = FundAnalyzerV2()
    analyzer.valuation_fetcher.fetch_index_valuation = Mock()
    assert analyzer._fetch_valuation(code, FundBasicInfo(fund_code=code, fund_name=name)) is None
    analyzer.valuation_fetcher.fetch_index_valuation.assert_not_called()
