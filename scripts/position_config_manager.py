"""
仓位配置管理模块
支持用户基金仓位配置的增删改查，数据持久化存储到 JSON 文件
实现优先级系统：基金专属 > 类型默认 > 系统推荐
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime

from .models import PositionConfig
from .logger import logger

# 配置文件默认路径
_DEFAULT_CONFIG_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "position_configs"
)
_DEFAULT_CONFIGS_FILE = os.path.join(_DEFAULT_CONFIG_DIR, "default_configs.json")
_FUND_CONFIGS_FILE = os.path.join(_DEFAULT_CONFIG_DIR, "fund_configs.json")


class PositionConfigManager:
    """
    仓位配置管理器
    负责用户基金仓位配置的管理和优先级查询

    优先级系统：
    1. 基金专属配置 (fund_configs.json)
    2. 基金类型默认配置 (default_configs.json)
    3. 系统推荐配置 (DEFAULT_CONFIGS常量)
    """

    # 系统推荐配置（最低优先级）
    DEFAULT_CONFIGS = {
        "宽基指数": {
            "target_pct": 15,
            "min_pct": 8,
            "max_pct": 20,
        },
        "行业指数": {
            "target_pct": 10,
            "min_pct": 5,
            "max_pct": 15,
        },
        "主动混合": {
            "target_pct": 12,
            "min_pct": 6,
            "max_pct": 18,
        },
        "债券基金": {
            "target_pct": 20,
            "min_pct": 10,
            "max_pct": 30,
        },
        "货币基金": {
            "target_pct": 5,
            "min_pct": 0,
            "max_pct": 10,
        },
    }

    def __init__(self, config_dir: str = _DEFAULT_CONFIG_DIR):
        """
        初始化配置管理器

        Args:
            config_dir: 配置目录路径
        """
        self._config_dir = config_dir
        os.makedirs(self._config_dir, exist_ok=True)

        self._default_configs_file = os.path.join(config_dir, "default_configs.json")
        self._fund_configs_file = os.path.join(config_dir, "fund_configs.json")

        # 内存缓存
        self._default_configs: Dict[str, Dict] = {}  # 类型默认配置缓存
        self._fund_configs: Dict[str, Dict] = {}  # 基金专属配置缓存

        self._load()

    # ─────────────────────────────── 持久化 ───────────────────────────────

    def _load(self):
        """从 JSON 文件加载配置"""
        self._load_default_configs()
        self._load_fund_configs()

    def _load_default_configs(self):
        """加载类型默认配置"""
        if not os.path.exists(self._default_configs_file):
            logger.info("类型默认配置文件不存在，将使用系统推荐配置")
            self._default_configs = {}
            return

        try:
            with open(self._default_configs_file, "r", encoding="utf-8") as f:
                self._default_configs = json.load(f)
            logger.info(f"已加载 {len(self._default_configs)} 个类型默认配置")
        except Exception as e:
            logger.error(f"加载类型默认配置失败: {e}")
            self._default_configs = {}

    def _load_fund_configs(self):
        """加载基金专属配置"""
        if not os.path.exists(self._fund_configs_file):
            logger.info("基金专属配置文件不存在")
            self._fund_configs = {}
            return

        try:
            with open(self._fund_configs_file, "r", encoding="utf-8") as f:
                self._fund_configs = json.load(f)
            logger.info(f"已加载 {len(self._fund_configs)} 个基金专属配置")
        except Exception as e:
            logger.error(f"加载基金专属配置失败: {e}")
            self._fund_configs = {}

    def _save_default_configs(self):
        """保存类型默认配置到文件"""
        try:
            with open(self._default_configs_file, "w", encoding="utf-8") as f:
                json.dump(self._default_configs, f, ensure_ascii=False, indent=2)
            logger.info("类型默认配置已保存")
        except Exception as e:
            logger.error(f"保存类型默认配置失败: {e}")

    def _save_fund_configs(self):
        """保存基金专属配置到文件"""
        try:
            with open(self._fund_configs_file, "w", encoding="utf-8") as f:
                json.dump(self._fund_configs, f, ensure_ascii=False, indent=2)
            logger.info("基金专属配置已保存")
        except Exception as e:
            logger.error(f"保存基金专属配置失败: {e}")

    # ─────────────────────────────── 查询配置 ───────────────────────────────

    def get_config(
        self, fund_code: str, fund_type: str
    ) -> PositionConfig:
        """
        获取基金的仓位配置，遵循优先级系统

        优先级：
        1. 基金专属配置 (fund_code作为key)
        2. 类型默认配置 (fund_type作为key)
        3. 系统推荐配置

        Args:
            fund_code: 基金代码
            fund_type: 基金类型

        Returns:
            PositionConfig: 该基金的仓位配置
        """
        # 优先级 1: 检查基金专属配置
        if fund_code in self._fund_configs:
            config_dict = self._fund_configs[fund_code]
            return PositionConfig(
                fund_code=fund_code,
                fund_type=fund_type,
                target_pct=config_dict["target_pct"],
                min_pct=config_dict["min_pct"],
                max_pct=config_dict["max_pct"],
                is_default=False,
            )

        # 优先级 2: 检查类型默认配置
        if fund_type in self._default_configs:
            config_dict = self._default_configs[fund_type]
            return PositionConfig(
                fund_code=None,
                fund_type=fund_type,
                target_pct=config_dict["target_pct"],
                min_pct=config_dict["min_pct"],
                max_pct=config_dict["max_pct"],
                is_default=True,
            )

        # 优先级 3: 使用系统推荐配置
        if fund_type in self.DEFAULT_CONFIGS:
            config_dict = self.DEFAULT_CONFIGS[fund_type]
            return PositionConfig(
                fund_code=None,
                fund_type=fund_type,
                target_pct=config_dict["target_pct"],
                min_pct=config_dict["min_pct"],
                max_pct=config_dict["max_pct"],
                is_default=True,
            )

        # 如果基金类型不存在，返回一个通用默认配置
        logger.warning(f"未找到基金类型 {fund_type} 的配置，使用通用默认配置")
        return PositionConfig(
            fund_code=None,
            fund_type=fund_type,
            target_pct=12,
            min_pct=5,
            max_pct=20,
            is_default=True,
        )

    def set_fund_config(
        self,
        fund_code: str,
        fund_type: str,
        target_pct: float,
        min_pct: float,
        max_pct: float,
    ) -> PositionConfig:
        """
        设置基金专属仓位配置

        Args:
            fund_code: 基金代码
            fund_type: 基金类型
            target_pct: 目标仓位(%)
            min_pct: 最低仓位线(%)
            max_pct: 最高仓位线(%)

        Returns:
            PositionConfig: 创建的配置对象

        Raises:
            ValueError: 如果仓位参数不合理
        """
        # 验证配置
        config = PositionConfig(
            fund_code=fund_code,
            fund_type=fund_type,
            target_pct=target_pct,
            min_pct=min_pct,
            max_pct=max_pct,
            is_default=False,
        )

        # 保存到内存和文件
        self._fund_configs[fund_code] = {
            "target_pct": target_pct,
            "min_pct": min_pct,
            "max_pct": max_pct,
        }
        self._save_fund_configs()

        logger.info(
            f"已设置基金 {fund_code} 的专属配置: target={target_pct}%, min={min_pct}%, max={max_pct}%"
        )
        return config

    def set_default_config(
        self,
        fund_type: str,
        target_pct: float,
        min_pct: float,
        max_pct: float,
    ) -> PositionConfig:
        """
        设置基金类型的默认仓位配置

        Args:
            fund_type: 基金类型（如"宽基指数"）
            target_pct: 目标仓位(%)
            min_pct: 最低仓位线(%)
            max_pct: 最高仓位线(%)

        Returns:
            PositionConfig: 创建的配置对象

        Raises:
            ValueError: 如果仓位参数不合理
        """
        # 验证配置
        config = PositionConfig(
            fund_code=None,
            fund_type=fund_type,
            target_pct=target_pct,
            min_pct=min_pct,
            max_pct=max_pct,
            is_default=True,
        )

        # 保存到内存和文件
        self._default_configs[fund_type] = {
            "target_pct": target_pct,
            "min_pct": min_pct,
            "max_pct": max_pct,
        }
        self._save_default_configs()

        logger.info(
            f"已设置类型 {fund_type} 的默认配置: target={target_pct}%, min={min_pct}%, max={max_pct}%"
        )
        return config

    def get_recommendation(
        self, fund_code: str, fund_type: str
    ) -> Dict:
        """
        获取基金的仓位建议（推荐配置信息）

        Args:
            fund_code: 基金代码
            fund_type: 基金类型

        Returns:
            Dict: 包含以下信息的推荐字典
                - config: PositionConfig对象
                - source: 配置来源 ("fund_specific" / "type_default" / "system_recommended")
                - explanation: 配置说明
        """
        config = self.get_config(fund_code, fund_type)

        # 判断配置来源
        if fund_code in self._fund_configs:
            source = "fund_specific"
            explanation = f"基金 {fund_code} 专属配置"
        elif fund_type in self._default_configs:
            source = "type_default"
            explanation = f"基金类型 {fund_type} 默认配置"
        else:
            source = "system_recommended"
            explanation = f"系统推荐配置（基金类型: {fund_type}）"

        return {
            "config": config,
            "source": source,
            "explanation": explanation,
            "target_pct": config.target_pct,
            "min_pct": config.min_pct,
            "max_pct": config.max_pct,
        }

    # ─────────────────────────────── 管理方法 ───────────────────────────────

    def list_default_configs(self) -> Dict[str, Dict]:
        """
        列出所有类型默认配置

        Returns:
            Dict: 类型 -> 配置映射
        """
        # 合并默认配置和自定义配置
        result = {}
        for fund_type, config in self.DEFAULT_CONFIGS.items():
            result[fund_type] = config.copy()

        # 覆盖自定义配置
        for fund_type, config in self._default_configs.items():
            result[fund_type] = config.copy()

        return result

    def list_fund_configs(self) -> Dict[str, Dict]:
        """
        列出所有基金专属配置

        Returns:
            Dict: 基金代码 -> 配置映射
        """
        return self._fund_configs.copy()

    def remove_fund_config(self, fund_code: str) -> bool:
        """
        移除基金专属配置，恢复为默认配置

        Args:
            fund_code: 基金代码

        Returns:
            bool: 是否成功移除
        """
        if fund_code in self._fund_configs:
            del self._fund_configs[fund_code]
            self._save_fund_configs()
            logger.info(f"已移除基金 {fund_code} 的专属配置")
            return True
        else:
            logger.warning(f"基金 {fund_code} 没有专属配置")
            return False

    def remove_default_config(self, fund_type: str) -> bool:
        """
        移除类型默认配置，恢复为系统推荐

        Args:
            fund_type: 基金类型

        Returns:
            bool: 是否成功移除
        """
        if fund_type in self._default_configs:
            del self._default_configs[fund_type]
            self._save_default_configs()
            logger.info(f"已移除类型 {fund_type} 的默认配置")
            return True
        else:
            logger.warning(f"类型 {fund_type} 没有自定义默认配置")
            return False

    def init_default_configs_file(self):
        """初始化默认配置文件（用于首次设置）"""
        if not os.path.exists(self._default_configs_file):
            try:
                with open(self._default_configs_file, "w", encoding="utf-8") as f:
                    json.dump(self.DEFAULT_CONFIGS, f, ensure_ascii=False, indent=2)
                logger.info("已初始化类型默认配置文件")
            except Exception as e:
                logger.error(f"初始化默认配置文件失败: {e}")


# 全局单例
_position_config_manager: Optional[PositionConfigManager] = None


def get_position_config_manager() -> PositionConfigManager:
    """
    获取全局单例的PositionConfigManager

    Returns:
        PositionConfigManager: 全局配置管理器实例
    """
    global _position_config_manager
    if _position_config_manager is None:
        _position_config_manager = PositionConfigManager()
    return _position_config_manager
