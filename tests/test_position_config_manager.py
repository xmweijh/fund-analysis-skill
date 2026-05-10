"""
测试仓位配置管理器
"""

import pytest
import os
import json
import tempfile
import shutil
from scripts.position_config_manager import (
    PositionConfigManager,
    get_position_config_manager,
)
from scripts.models import PositionConfig


class TestPositionConfigManager:
    """仓位配置管理器测试类"""

    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def manager(self, temp_config_dir):
        """创建配置管理器实例"""
        return PositionConfigManager(config_dir=temp_config_dir)

    # ─────────────────────────────── 优先级系统测试 ───────────────────────────────

    def test_get_config_system_recommended(self, manager):
        """测试获取系统推荐配置（最低优先级）"""
        config = manager.get_config("001234", "宽基指数")

        assert config.fund_type == "宽基指数"
        assert config.target_pct == 15
        assert config.min_pct == 8
        assert config.max_pct == 20
        assert config.is_default is True
        assert config.fund_code is None

    def test_get_config_type_default(self, manager, temp_config_dir):
        """测试优先级：类型默认配置 > 系统推荐"""
        # 设置类型默认配置
        manager.set_default_config("宽基指数", target_pct=18, min_pct=10, max_pct=25)

        config = manager.get_config("001234", "宽基指数")

        assert config.target_pct == 18
        assert config.min_pct == 10
        assert config.max_pct == 25
        assert config.is_default is True

    def test_get_config_fund_specific(self, manager, temp_config_dir):
        """测试优先级：基金专属配置 > 类型默认 > 系统推荐"""
        # 先设置类型默认配置
        manager.set_default_config("宽基指数", target_pct=18, min_pct=10, max_pct=25)

        # 再设置基金专属配置
        manager.set_fund_config("001234", "宽基指数", target_pct=20, min_pct=12, max_pct=28)

        config = manager.get_config("001234", "宽基指数")

        assert config.target_pct == 20
        assert config.min_pct == 12
        assert config.max_pct == 28
        assert config.is_default is False
        assert config.fund_code == "001234"

    # ─────────────────────────────── 设置配置测试 ───────────────────────────────

    def test_set_fund_config(self, manager):
        """测试设置基金专属配置"""
        config = manager.set_fund_config(
            "110022", "主动混合", target_pct=15, min_pct=8, max_pct=22
        )

        assert config.fund_code == "110022"
        assert config.fund_type == "主动混合"
        assert config.target_pct == 15
        assert config.min_pct == 8
        assert config.max_pct == 22
        assert config.is_default is False

    def test_set_default_config(self, manager):
        """测试设置类型默认配置"""
        config = manager.set_default_config(
            "行业指数", target_pct=12, min_pct=6, max_pct=18
        )

        assert config.fund_code is None
        assert config.fund_type == "行业指数"
        assert config.target_pct == 12
        assert config.min_pct == 6
        assert config.max_pct == 18
        assert config.is_default is True

    def test_set_config_validation_min_greater_than_target(self, manager):
        """测试配置验证：最低仓位不能高于目标仓位"""
        with pytest.raises(ValueError):
            manager.set_fund_config(
                "001234", "宽基指数", target_pct=10, min_pct=15, max_pct=20
            )

    def test_set_config_validation_max_less_than_target(self, manager):
        """测试配置验证：最高仓位不能低于目标仓位"""
        with pytest.raises(ValueError):
            manager.set_fund_config(
                "001234", "宽基指数", target_pct=15, min_pct=8, max_pct=12
            )

    def test_set_config_validation_range_out_of_bounds(self, manager):
        """测试配置验证：仓位范围不能超出0-100"""
        with pytest.raises(ValueError):
            manager.set_fund_config(
                "001234", "宽基指数", target_pct=105, min_pct=100, max_pct=110
            )

    # ─────────────────────────────── 建议推荐测试 ───────────────────────────────

    def test_get_recommendation_system_recommended(self, manager):
        """测试获取系统推荐的建议"""
        rec = manager.get_recommendation("001234", "债券基金")

        assert rec["source"] == "system_recommended"
        assert rec["target_pct"] == 20
        assert rec["min_pct"] == 10
        assert rec["max_pct"] == 30
        assert "系统推荐配置" in rec["explanation"]

    def test_get_recommendation_type_default(self, manager):
        """测试获取类型默认的建议"""
        manager.set_default_config("货币基金", target_pct=8, min_pct=2, max_pct=12)

        rec = manager.get_recommendation("100000", "货币基金")

        assert rec["source"] == "type_default"
        assert rec["target_pct"] == 8
        assert rec["min_pct"] == 2
        assert rec["max_pct"] == 12
        assert "默认配置" in rec["explanation"]

    def test_get_recommendation_fund_specific(self, manager):
        """测试获取基金专属的建议"""
        manager.set_fund_config("110022", "主动混合", target_pct=16, min_pct=10, max_pct=22)

        rec = manager.get_recommendation("110022", "主动混合")

        assert rec["source"] == "fund_specific"
        assert rec["target_pct"] == 16
        assert rec["min_pct"] == 10
        assert rec["max_pct"] == 22
        assert "专属配置" in rec["explanation"]

    # ─────────────────────────────── 持久化测试 ───────────────────────────────

    def test_persistence_fund_configs(self, temp_config_dir):
        """测试基金专属配置的持久化"""
        # 创建第一个管理器实例并设置配置
        manager1 = PositionConfigManager(config_dir=temp_config_dir)
        manager1.set_fund_config("001234", "宽基指数", target_pct=18, min_pct=10, max_pct=25)

        # 创建第二个管理器实例，应该能加载到之前保存的配置
        manager2 = PositionConfigManager(config_dir=temp_config_dir)
        config = manager2.get_config("001234", "宽基指数")

        assert config.target_pct == 18
        assert config.min_pct == 10
        assert config.max_pct == 25

    def test_persistence_default_configs(self, temp_config_dir):
        """测试类型默认配置的持久化"""
        # 创建第一个管理器实例并设置配置
        manager1 = PositionConfigManager(config_dir=temp_config_dir)
        manager1.set_default_config("宽基指数", target_pct=17, min_pct=9, max_pct=24)

        # 创建第二个管理器实例，应该能加载到之前保存的配置
        manager2 = PositionConfigManager(config_dir=temp_config_dir)
        config = manager2.get_config("999999", "宽基指数")

        assert config.target_pct == 17
        assert config.min_pct == 9
        assert config.max_pct == 24

    def test_json_file_format(self, temp_config_dir):
        """测试 JSON 文件格式正确性"""
        manager = PositionConfigManager(config_dir=temp_config_dir)

        # 设置一些配置
        manager.set_fund_config("001234", "宽基指数", target_pct=18, min_pct=10, max_pct=25)
        manager.set_default_config("行业指数", target_pct=12, min_pct=6, max_pct=18)

        # 检查文件是否存在
        fund_config_file = os.path.join(temp_config_dir, "fund_configs.json")
        default_config_file = os.path.join(temp_config_dir, "default_configs.json")

        assert os.path.exists(fund_config_file)
        assert os.path.exists(default_config_file)

        # 验证 JSON 格式
        with open(fund_config_file, "r", encoding="utf-8") as f:
            fund_data = json.load(f)
            assert "001234" in fund_data
            assert fund_data["001234"]["target_pct"] == 18

        with open(default_config_file, "r", encoding="utf-8") as f:
            default_data = json.load(f)
            assert "行业指数" in default_data
            assert default_data["行业指数"]["target_pct"] == 12

    # ─────────────────────────────── 管理方法测试 ───────────────────────────────

    def test_list_default_configs(self, manager):
        """测试列出所有类型默认配置"""
        manager.set_default_config("行业指数", target_pct=12, min_pct=6, max_pct=18)
        manager.set_default_config("债券基金", target_pct=22, min_pct=12, max_pct=32)

        configs = manager.list_default_configs()

        # 应该包含系统推荐配置和自定义配置
        assert "宽基指数" in configs
        assert "行业指数" in configs
        assert "债券基金" in configs
        assert "主动混合" in configs
        assert "货币基金" in configs

        # 验证自定义配置覆盖了系统推荐
        assert configs["行业指数"]["target_pct"] == 12
        assert configs["债券基金"]["target_pct"] == 22

    def test_list_fund_configs(self, manager):
        """测试列出所有基金专属配置"""
        manager.set_fund_config("001234", "宽基指数", target_pct=18, min_pct=10, max_pct=25)
        manager.set_fund_config("110022", "主动混合", target_pct=14, min_pct=7, max_pct=21)

        configs = manager.list_fund_configs()

        assert len(configs) == 2
        assert "001234" in configs
        assert "110022" in configs
        assert configs["001234"]["target_pct"] == 18
        assert configs["110022"]["target_pct"] == 14

    def test_remove_fund_config(self, manager):
        """测试移除基金专属配置"""
        manager.set_fund_config("001234", "宽基指数", target_pct=18, min_pct=10, max_pct=25)

        # 移除前，应该返回基金专属配置
        config1 = manager.get_config("001234", "宽基指数")
        assert config1.target_pct == 18
        assert config1.is_default is False

        # 移除配置
        result = manager.remove_fund_config("001234")
        assert result is True

        # 移除后，应该返回系统推荐配置
        config2 = manager.get_config("001234", "宽基指数")
        assert config2.target_pct == 15
        assert config2.is_default is True

    def test_remove_fund_config_not_exists(self, manager):
        """测试移除不存在的基金专属配置"""
        result = manager.remove_fund_config("999999")
        assert result is False

    def test_remove_default_config(self, manager):
        """测试移除类型默认配置"""
        manager.set_default_config("宽基指数", target_pct=17, min_pct=9, max_pct=24)

        # 移除前，应该返回自定义默认配置
        config1 = manager.get_config("001234", "宽基指数")
        assert config1.target_pct == 17

        # 移除配置
        result = manager.remove_default_config("宽基指数")
        assert result is True

        # 移除后，应该返回系统推荐配置
        config2 = manager.get_config("001234", "宽基指数")
        assert config2.target_pct == 15

    def test_remove_default_config_not_exists(self, manager):
        """测试移除不存在的类型默认配置"""
        result = manager.remove_default_config("不存在的基金类型")
        assert result is False

    # ─────────────────────────────── 初始化测试 ───────────────────────────────

    def test_init_default_configs_file(self, temp_config_dir):
        """测试初始化默认配置文件"""
        manager = PositionConfigManager(config_dir=temp_config_dir)
        manager.init_default_configs_file()

        default_config_file = os.path.join(temp_config_dir, "default_configs.json")
        assert os.path.exists(default_config_file)

        with open(default_config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "宽基指数" in data
            assert data["宽基指数"]["target_pct"] == 15

    # ─────────────────────────────── 全局单例测试 ───────────────────────────────

    def test_global_singleton(self):
        """测试全局单例获取"""
        manager1 = get_position_config_manager()
        manager2 = get_position_config_manager()

        # 应该是同一个实例
        assert manager1 is manager2

    # ─────────────────────────────── 默认配置测试 ───────────────────────────────

    def test_all_default_configs_exist(self, manager):
        """测试所有系统推荐配置都存在"""
        fund_types = ["宽基指数", "行业指数", "主动混合", "债券基金", "货币基金"]

        for fund_type in fund_types:
            config = manager.get_config("000001", fund_type)
            assert config.fund_type == fund_type
            assert config.target_pct > 0
            assert config.min_pct < config.target_pct
            assert config.max_pct > config.target_pct
            assert config.is_default is True

    def test_unknown_fund_type_default_fallback(self, manager):
        """测试未知基金类型的默认配置回退"""
        config = manager.get_config("000001", "未知基金类型")

        assert config.fund_type == "未知基金类型"
        # 应该返回通用默认配置
        assert config.target_pct == 12
        assert config.min_pct == 5
        assert config.max_pct == 20
        assert config.is_default is True

    # ─────────────────────────────── 边界条件测试 ───────────────────────────────

    def test_edge_case_zero_min_pct(self, manager):
        """测试最低仓位为0的情况"""
        config = manager.get_config("000001", "货币基金")
        assert config.min_pct == 0

    def test_edge_case_full_allocation(self, manager):
        """测试满仓配置（max_pct=100）"""
        manager.set_fund_config("001234", "宽基指数", target_pct=100, min_pct=90, max_pct=100)
        config = manager.get_config("001234", "宽基指数")

        assert config.target_pct == 100
        assert config.max_pct == 100

    def test_multiple_operations_consistency(self, manager):
        """测试多个操作的一致性"""
        # 设置多个配置
        manager.set_fund_config("001234", "宽基指数", target_pct=18, min_pct=10, max_pct=25)
        manager.set_fund_config("110022", "主动混合", target_pct=14, min_pct=7, max_pct=21)
        manager.set_default_config("行业指数", target_pct=12, min_pct=6, max_pct=18)

        # 验证所有配置都能正确获取
        config1 = manager.get_config("001234", "宽基指数")
        config2 = manager.get_config("110022", "主动混合")
        config3 = manager.get_config("999999", "行业指数")

        assert config1.target_pct == 18
        assert config2.target_pct == 14
        assert config3.target_pct == 12
