"""
测试估值数据获取器 V2
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from scripts.data_fetcher_v2 import ValuationDataFetcher
from scripts.models import ValuationData


class TestValuationDataFetcher:
    """估值数据获取器测试类"""

    @pytest.fixture
    def fetcher(self):
        """创建获取器实例"""
        return ValuationDataFetcher()

    @pytest.fixture
    def mock_api_response(self):
        """模拟API响应"""
        return {
            'data': {
                'items': [
                    {
                        'code': '000300',
                        'name': '沪深300',
                        'pe': 12.5,
                        'pb': 1.35,
                        'pe_percentile': 0.25,
                        'pb_percentile': 0.30,
                        'eva_type': 'low',
                        'update_date': '2025-05-10'
                    },
                    {
                        'code': '000905',
                        'name': '中证500',
                        'pe': 15.2,
                        'pb': 1.68,
                        'pe_percentile': 0.45,
                        'pb_percentile': 0.50,
                        'eva_type': 'mid',
                        'update_date': '2025-05-10'
                    },
                    {
                        'code': '399006',
                        'name': '创业板指',
                        'pe': 25.8,
                        'pb': 2.45,
                        'pe_percentile': 0.75,
                        'pb_percentile': 0.80,
                        'eva_type': 'high',
                        'update_date': '2025-05-10'
                    }
                ]
            }
        }

    def test_fetch_index_valuation_success(self, fetcher, mock_api_response):
        """测试成功获取指数估值数据"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000300')

            assert result is not None
            assert isinstance(result, ValuationData)
            assert result.pe_ttm == 12.5
            assert result.pb == 1.35
            assert result.pe_percentile == 25.0  # 0.25 * 100
            assert result.pb_percentile == 30.0  # 0.30 * 100
            assert result.status == '低估'

    def test_fetch_index_valuation_mid_status(self, fetcher, mock_api_response):
        """测试中证500估值状态为合理"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000905')

            assert result is not None
            assert result.pe_ttm == 15.2
            assert result.status == '合理'

    def test_fetch_index_valuation_high_status(self, fetcher, mock_api_response):
        """测试创业板指估值状态为高估"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('399006')

            assert result is not None
            assert result.status == '高估'

    def test_risk_premium_calculation(self, fetcher, mock_api_response):
        """测试风险溢价计算"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000300')

            # 风险溢价 = (1/12.5 * 100) - 2.5 = 8.0 - 2.5 = 5.5
            assert result is not None
            assert result.risk_premium == pytest.approx(5.5, rel=0.01)

    def test_fetch_index_valuation_not_found(self, fetcher, mock_api_response):
        """测试指数代码不存在"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('999999')

            assert result is None

    def test_fetch_index_valuation_network_error(self, fetcher):
        """测试网络请求失败"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_get.side_effect = Exception("网络错误")

            result = fetcher.fetch_index_valuation('000300')

            assert result is None

    def test_fetch_index_valuation_empty_response(self, fetcher):
        """测试API返回空数据"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {}
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000300')

            assert result is None

    def test_fetch_index_valuation_empty_items(self, fetcher):
        """测试API返回空项目列表"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'data': {'items': []}}
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000300')

            assert result is None

    def test_to_float_valid(self, fetcher):
        """测试浮点数转换 - 有效值"""
        assert fetcher._to_float('12.5') == 12.5
        assert fetcher._to_float(12.5) == 12.5
        assert fetcher._to_float('25%') == 25.0

    def test_to_float_invalid(self, fetcher):
        """测试浮点数转换 - 无效值"""
        assert fetcher._to_float(None) is None
        assert fetcher._to_float('') is None
        assert fetcher._to_float('--') is None
        assert fetcher._to_float('abc') is None

    def test_cache_mechanism(self, fetcher, mock_api_response):
        """测试缓存机制"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            # 第一次调用
            result1 = fetcher.fetch_index_valuation('000300')
            call_count_1 = mock_get.call_count

            # 第二次调用应该使用缓存
            result2 = fetcher.fetch_index_valuation('000300')
            call_count_2 = mock_get.call_count

            assert result1 == result2
            assert call_count_2 == call_count_1  # 没有新的HTTP请求

    def test_get_common_index_mapping(self, fetcher):
        """测试常见指数映射"""
        mapping = fetcher.get_common_index_mapping()

        assert '沪深300' in mapping
        assert mapping['沪深300'] == '000300'
        assert mapping['中证500'] == '000905'
        assert mapping['创业板指'] == '399006'
        assert mapping['上证50'] == '000016'
        assert mapping['科创50'] == '000688'
        assert mapping['中证1000'] == '000852'
        assert mapping['恒生指数'] == 'HSI'
        assert mapping['纳斯达克100'] == 'NDX'

    def test_fetch_multiple_indices(self, fetcher, mock_api_response):
        """测试批量获取多个指数估值数据"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_multiple_indices(['000300', '000905', '399006'])

            assert len(result) == 3
            assert '000300' in result
            assert '000905' in result
            assert '399006' in result
            assert result['000300'].status == '低估'
            assert result['000905'].status == '合理'
            assert result['399006'].status == '高估'

    def test_parse_valuation_item_with_all_fields(self, fetcher):
        """测试解析包含所有字段的估值数据"""
        item = {
            'code': '000300',
            'pe': 12.5,
            'pb': 1.35,
            'pe_percentile': 0.25,
            'pb_percentile': 0.30,
            'eva_type': 'low',
            'update_date': '2025-05-10'
        }

        result = fetcher._parse_valuation_item(item)

        assert result is not None
        assert result.pe_ttm == 12.5
        assert result.pb == 1.35
        assert result.pe_percentile == 25.0
        assert result.pb_percentile == 30.0
        assert result.status == '低估'
        assert result.update_date == '2025-05-10'

    def test_parse_valuation_item_with_missing_fields(self, fetcher):
        """测试解析缺少某些字段的估值数据"""
        item = {
            'code': '000300',
            'pe': 12.5,
            # pb、percentile等缺失
        }

        result = fetcher._parse_valuation_item(item)

        assert result is not None
        assert result.pe_ttm == 12.5
        assert result.pb is None
        assert result.pe_percentile is None
        assert result.pb_percentile is None

    def test_parse_valuation_item_with_integer_date(self, fetcher):
        """测试解析整数时间戳"""
        item = {
            'code': '000300',
            'pe': 12.5,
            'update_date': 1715299200000  # 时间戳毫秒
        }

        result = fetcher._parse_valuation_item(item)

        assert result is not None
        assert result.update_date is not None
        # 应该是日期字符串格式

    def test_valuation_data_model_validation(self):
        """测试ValuationData模型验证"""
        data = ValuationData(
            pe_ttm=12.5,
            pb=1.35,
            pe_percentile=25.0,
            pb_percentile=30.0,
            risk_premium=5.5,
            status='低估',
            update_date='2025-05-10'
        )

        assert data.pe_ttm == 12.5
        assert data.status == '低估'

    def test_valuation_data_default_status(self):
        """测试ValuationData默认状态"""
        data = ValuationData()

        assert data.status == '未知'
        assert data.pe_ttm is None
        assert data.pb is None

    def test_fetch_with_empty_index_code(self, fetcher):
        """测试空指数代码"""
        result = fetcher.fetch_index_valuation('')

        assert result is None

    def test_fetch_with_none_index_code(self, fetcher):
        """测试None指数代码"""
        result = fetcher.fetch_index_valuation(None)

        assert result is None

    def test_risk_premium_with_zero_pe(self, fetcher):
        """测试PE为0时风险溢价计算"""
        item = {
            'code': '000300',
            'pe': 0,  # PE为0，无法计算
        }

        result = fetcher._parse_valuation_item(item)

        assert result is not None
        assert result.risk_premium is None  # 应该无法计算

    def test_eva_type_case_insensitive(self, fetcher):
        """测试eva_type大小写不敏感"""
        item_low = {'eva_type': 'LOW', 'pe': 10}
        item_mid = {'eva_type': 'MID', 'pe': 10}
        item_high = {'eva_type': 'HIGH', 'pe': 10}

        result_low = fetcher._parse_valuation_item(item_low)
        result_mid = fetcher._parse_valuation_item(item_mid)
        result_high = fetcher._parse_valuation_item(item_high)

        assert result_low.status == '低估'
        assert result_mid.status == '合理'
        assert result_high.status == '高估'

    def test_unknown_eva_type(self, fetcher):
        """测试未知eva_type映射"""
        item = {
            'code': '000300',
            'eva_type': 'unknown',
            'pe': 10
        }

        result = fetcher._parse_valuation_item(item)

        assert result.status == '未知'

    def test_percentile_multiplication(self, fetcher, mock_api_response):
        """测试百分位数自动乘以100"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_index_valuation('000300')

            # API返回0.25，应该转换为25.0
            assert result.pe_percentile == 25.0
            assert result.pb_percentile == 30.0

    def test_timeout_parameter(self):
        """测试超时参数"""
        fetcher_custom = ValuationDataFetcher(timeout=5)
        assert fetcher_custom.timeout == 5

        fetcher_default = ValuationDataFetcher()
        assert fetcher_default.timeout == 10
