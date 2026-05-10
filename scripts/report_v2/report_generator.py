"""
HTML报告生成器
将分析结果字典序列化为 JSON，并生成对应的 HTML 报告文件。
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .html_template import HTMLTemplate


class ReportGenerator:
    """
    将分析结果字典持久化为 JSON + HTML 报告对。

    用法::

        gen = ReportGenerator()
        html_path, json_path = gen.generate(data, "/tmp/reports")
    """

    # ── 默认输出目录（相对于项目根的 reports/ 下按日期分组） ──────────────

    DEFAULT_BASE_DIR: str = os.path.join(
        os.path.dirname(__file__), "..", "..", "reports"
    )

    # ── 公开 API ────────────────────────────────────────────────────────────

    def generate(
        self,
        data: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        保存 JSON 数据文件，生成并保存 HTML 报告文件。

        参数
        ----
        data : dict
            分析结果字典，应包含以下键（均为可选，缺失时忽略）：

            - ``fund_code``       : str  基金代码
            - ``fund_name``       : str  基金名称
            - ``generated_at``    : str  生成时间（未提供时自动填充）
            - ``scores``          : dict 五维评分 {technical, fundamental,
                                         valuation, capital_flow, sentiment, total}
            - ``technical``       : dict 技术指标
            - ``valuation``       : dict 估值数据
            - ``position_advice`` : dict 仓位建议
            - ``sip_enabled``     : bool 是否启用定投
            - ``sip_advice``      : dict 定投建议
            - ``action``          : str  操作建议
            - ``conclusion``      : str  核心结论

        output_dir : str, optional
            输出目录路径。若为 None，则自动使用
            ``<项目根>/reports/<YYYYMMDD>/`` 目录。

        返回
        ----
        Tuple[str, str]
            ``(html_path, json_path)`` 两个绝对路径。
        """
        # 1. 确定输出目录
        if output_dir is None:
            date_str = datetime.now().strftime("%Y%m%d")
            output_dir = os.path.join(self.DEFAULT_BASE_DIR, date_str)

        os.makedirs(output_dir, exist_ok=True)

        # 2. 注入生成时间（如果调用方未提供）
        if "generated_at" not in data or not data["generated_at"]:
            data = dict(data)  # 浅拷贝，避免修改原始对象
            data["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. 构造文件名
        fund_code = data.get("fund_code", "unknown")
        timestamp = datetime.now().strftime("%H%M%S")
        base_name = f"report_{fund_code}_{timestamp}"

        json_path = os.path.join(output_dir, base_name + ".json")
        html_path = os.path.join(output_dir, base_name + ".html")

        # 4. 保存 JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=self._json_default)

        # 5. 生成并保存 HTML
        html_content = HTMLTemplate.render(json_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_path, json_path

    # ── 辅助方法 ────────────────────────────────────────────────────────────

    @staticmethod
    def _json_default(obj: Any) -> Any:
        """JSON 序列化的默认处理器，支持 Pydantic BaseModel 等对象。"""
        # Pydantic v1
        if hasattr(obj, "dict"):
            return obj.dict()
        # Pydantic v2 / dataclasses
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # dataclasses
        try:
            import dataclasses
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
        except ImportError:
            pass
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
