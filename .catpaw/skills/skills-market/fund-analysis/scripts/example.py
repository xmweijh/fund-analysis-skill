"""
使用示例:基金分析
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from scripts.fund_analyzer import FundAnalyzer
from scripts.logger import logger


def example_basic_usage():
    """
    示例1: 基本使用
    """
    print("=" * 80)
    print("示例1: 基本使用 - 分析单只基金")
    print("=" * 80)
    print()

    # 创建分析器
    analyzer = FundAnalyzer()

    # 分析基金
    fund_code = "008975"  # 易方达蓝筹精选混合
    print(f"开始分析基金: {fund_code}")
    print()

    try:
        # 执行分析
        report = analyzer.analyze(fund_code)

        # 打印报告摘要
        print("\n" + "=" * 80)
        print("分析完成!")
        print("=" * 80)

        # 保存报告
        file_path = analyzer.save_report(report, fund_code)
        print(f"\n报告已保存到: {file_path}")
        print(f"\n完整报告:\n")
        print(report)

    except Exception as e:
        print(f"分析失败: {e}")
        logger.error(f"示例执行失败: {e}", exc_info=True)


def example_multiple_funds():
    """
    示例2: 分析多只基金
    """
    print("=" * 80)
    print("示例2: 分析多只基金")
    print("=" * 80)
    print()

    # 创建分析器
    analyzer = FundAnalyzer()

    # 基金代码列表
    fund_codes = ["008975", "110011", "161725"]

    for fund_code in fund_codes:
        print(f"\n正在分析基金: {fund_code}")
        try:
            report = analyzer.analyze(fund_code)
            file_path = analyzer.save_report(report, fund_code)
            print(f"✓ {fund_code} 分析完成,报告已保存: {file_path}")
        except Exception as e:
            print(f"✗ {fund_code} 分析失败: {e}")


def example_error_handling():
    """
    示例3: 错误处理
    """
    print("=" * 80)
    print("示例3: 错误处理")
    print("=" * 80)
    print()

    analyzer = FundAnalyzer()

    # 测试无效基金代码
    print("测试1: 无效基金代码")
    report = analyzer.analyze("999999")  # 不存在的基金代码
    print(report)

    print("\n" + "-" * 80 + "\n")

    # 测试格式错误的基金代码
    print("测试2: 格式错误的基金代码")
    report = analyzer.analyze("abc123")  # 格式错误
    print(report)


def example_custom_analysis():
    """
    示例4: 自定义分析
    """
    print("=" * 80)
    print("示例4: 自定义分析")
    print("=" * 80)
    print()

    from scripts.data_fetcher import DanjuanDataFetcher
    from scripts.models import FundNavHistory, FundRealtimeQuote
    from scripts.technical_analysis import TechnicalAnalyzer

    # 创建数据获取器
    data_fetcher = DanjuanDataFetcher()

    # 获取净值历史
    fund_code = "008975"
    nav_history = data_fetcher.fetch_nav_history(fund_code, days=90)

    # 获取实时行情
    quote = data_fetcher.fetch_realtime_quote(fund_code)

    # 执行技术分析
    tech_analyzer = TechnicalAnalyzer()
    technical = tech_analyzer.analyze(nav_history, quote)

    # 打印结果
    print(f"基金代码: {fund_code}")
    print(f"当前净值: {quote.nav:.4f}")
    print(f"MA5: {technical.ma5:.4f}")
    print(f"MA10: {technical.ma10:.4f}")
    print(f"MA20: {technical.ma20:.4f}")
    print(f"MA60: {technical.ma60:.4f}")
    print(f"趋势: {technical.trend}")
    print(f"形态: {technical.formation}")
    print(f"技术信号: {', '.join(technical.signals)}")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("基金分析技能 - 使用示例")
    print("=" * 80 + "\n")

    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]
    else:
        example = "1"

    if example == "1":
        example_basic_usage()
    elif example == "2":
        example_multiple_funds()
    elif example == "3":
        example_error_handling()
    elif example == "4":
        example_custom_analysis()
    else:
        print("可用的示例:")
        print("1 - 基本使用")
        print("2 - 分析多只基金")
        print("3 - 错误处理")
        print("4 - 自定义分析")
        print("\n使用方法: python example.py <示例编号>")


if __name__ == "__main__":
    main()
