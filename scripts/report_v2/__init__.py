"""
report_v2 包 - HTML报告生成模块
"""

from .html_template import HTMLTemplate
from .report_generator import ReportGenerator

__all__ = [
    "HTMLTemplate",
    "ReportGenerator",
]
