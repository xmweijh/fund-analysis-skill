"""
组合持仓分析器
生成整体持仓的综合分析报告
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.portfolio_manager import PortfolioManager
from scripts.position_config_manager import PositionConfigManager
from scripts.data_fetcher import DanjuanDataFetcher
from scripts.logger import logger


@dataclass
class FundHoldingAnalysis:
    """单个基金持仓分析"""
    fund_code: str
    fund_name: str
    fund_type: str
    cost_amount: float
    current_nav: Optional[float]
    current_value: Optional[float]
    return_pct: Optional[float]
    target_pct: float
    min_pct: float
    max_pct: float
    action: str
    total_score: float
    tech_score: float


@dataclass
class PortfolioSummary:
    """组合汇总"""
    total_cost: float
    total_value: Optional[float]
    total_return: Optional[float]
    total_return_pct: Optional[float]
    fund_count: int
    avg_score: float
    risk_distribution: Dict[str, float]
    action_distribution: Dict[str, int]


class PortfolioAnalyzer:
    """组合分析器"""

    def __init__(self):
        self.portfolio = PortfolioManager()
        self.data_fetcher = DanjuanDataFetcher()
        self.position_manager = PositionConfigManager()

    def analyze_all(self) -> Tuple[List[FundHoldingAnalysis], PortfolioSummary]:
        """
        分析所有持仓基金

        Returns:
            (基金分析列表, 组合汇总)
        """
        entries = self.portfolio.list_all()
        if not entries:
            logger.warning("没有持仓数据")
            return [], PortfolioSummary(
                total_cost=0, total_value=None, total_return=None,
                total_return_pct=None, fund_count=0, avg_score=0,
                risk_distribution={}, action_distribution={}
            )

        fund_analyses = []
        total_cost = 0.0
        total_value = 0.0
        total_score = 0.0
        action_dist = {}
        risk_dist = {"低风险": 0, "中风险": 0, "高风险": 0}

        logger.info(f"开始分析组合持仓，共 {len(entries)} 只基金")

        for entry in entries:
            fund_code = entry.fund_code
            cost_amount = entry.cost_amount or 0
            total_cost += cost_amount

            # 获取基金信息
            basic_info = self._safe_fetch(
                self.data_fetcher.fetch_basic_info, fund_code
            )
            quote = self._safe_fetch(
                self.data_fetcher.fetch_realtime_quote, fund_code
            )
            performance = self._safe_fetch(
                self.data_fetcher.fetch_performance, fund_code
            )

            fund_name = basic_info.fund_name if basic_info else fund_code
            fund_type_str = basic_info.fund_type if basic_info else "未知"

            # 确定基金类型分类
            fund_type = self._classify_fund_type(fund_type_str)

            # 获取仓位配置
            config = self.position_manager.get_config(fund_code, fund_type)

            # 计算当前市值和收益
            current_nav = quote.nav if quote else None
            shares = entry.shares
            current_value = None
            return_pct = None

            if current_nav and shares:
                current_value = current_nav * shares
                total_value += current_value
                if cost_amount > 0:
                    return_pct = (current_value - cost_amount) / cost_amount * 100
            elif current_nav and cost_amount > 0:
                # 估算市值
                avg_cost = entry.cost_nav or current_nav
                current_value = cost_amount * (current_nav / avg_cost)
                total_value += current_value
                return_pct = (current_nav / avg_cost - 1) * 100

            # 根据业绩和风险评估确定建议
            total_score, tech_score, action, risk_level = self._evaluate_fund(
                performance, quote
            )

            # 汇总统计
            total_score += total_score
            action_dist[action] = action_dist.get(action, 0) + 1
            risk_dist[risk_level] = risk_dist.get(risk_level, 0) + cost_amount

            analysis = FundHoldingAnalysis(
                fund_code=fund_code,
                fund_name=fund_name,
                fund_type=fund_type,
                cost_amount=cost_amount,
                current_nav=current_nav,
                current_value=current_value,
                return_pct=return_pct,
                target_pct=config.target_pct,
                min_pct=config.min_pct,
                max_pct=config.max_pct,
                action=action,
                total_score=total_score,
                tech_score=tech_score
            )
            fund_analyses.append(analysis)

        # 计算组合汇总
        avg_score = total_score / len(fund_analyses) if fund_analyses else 0
        total_return = total_value - total_cost if total_value > 0 else None
        total_return_pct = (total_return / total_cost * 100) if total_return else None

        # 风险分布转换为百分比
        if total_cost > 0:
            risk_dist = {k: v/total_cost*100 for k, v in risk_dist.items() if v > 0}

        summary = PortfolioSummary(
            total_cost=total_cost,
            total_value=total_value if total_value > 0 else None,
            total_return=total_return,
            total_return_pct=total_return_pct,
            fund_count=len(fund_analyses),
            avg_score=round(avg_score, 1),
            risk_distribution=risk_dist,
            action_distribution=action_dist
        )

        logger.info(f"组合分析完成: {summary.fund_count}只基金, 总成本{summary.total_cost:.0f}元")
        return fund_analyses, summary

    def _classify_fund_type(self, fund_type_str: Optional[str]) -> str:
        """分类基金类型"""
        if not fund_type_str:
            return "宽基指数"

        ft = fund_type_str
        if "债券" in ft or "债" in ft:
            return "债券基金"
        elif "货币" in ft:
            return "货币基金"
        elif "行业" in ft or "主题" in ft:
            return "行业指数"
        elif any(x in ft for x in ["股票型", "混合型", "灵活配置", "偏股"]):
            return "主动混合"
        else:
            return "宽基指数"

    def _evaluate_fund(self, performance: Any, quote: Any) -> Tuple[float, float, str, str]:
        """
        评估基金，返回评分和建议
        Returns: (total_score, tech_score, action, risk_level)
        """
        score = 50.0
        tech_score = 50.0

        # 基于涨跌幅计算技术评分
        if quote and hasattr(quote, 'change_pct') and quote.change_pct is not None:
            cp = quote.change_pct
            if cp > 3:
                tech_score += 20
            elif cp > 1:
                tech_score += 10
            elif cp < -3:
                tech_score -= 20
            elif cp < -1:
                tech_score -= 10

        # 基于业绩计算基本面评分
        if performance:
            if hasattr(performance, 'return_1y') and performance.return_1y is not None:
                r1y = performance.return_1y
                if r1y > 20:
                    score += 15
                elif r1y > 10:
                    score += 10
                elif r1y < -10:
                    score -= 10

            if hasattr(performance, 'max_drawdown') and performance.max_drawdown is not None:
                mdd = abs(performance.max_drawdown)
                if mdd < 15:
                    score += 10
                elif mdd > 30:
                    score -= 10

        score = max(0, min(100, score))
        tech_score = max(0, min(100, tech_score))

        # 确定操作建议
        if score >= 70:
            action = "加仓"
        elif score >= 55:
            action = "持有"
        elif score >= 40:
            action = "观望"
        else:
            action = "减仓"

        # 确定风险等级
        if score >= 60:
            risk = "低风险"
        elif score >= 40:
            risk = "中风险"
        else:
            risk = "高风险"

        return score, tech_score, action, risk

    def _safe_fetch(self, func, *args) -> Any:
        """安全获取数据"""
        try:
            return func(*args)
        except Exception as e:
            logger.debug(f"数据获取失败: {e}")
            return None

    def generate_report(self, output_dir: Optional[str] = None) -> Tuple[str, str]:
        """
        生成组合分析报告

        Returns:
            (html_path, json_path)
        """
        fund_analyses, summary = self.analyze_all()

        # 准备报告数据
        report_data = self._build_report_data(fund_analyses, summary)

        # 保存JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_str = datetime.now().strftime('%Y%m%d')

        if output_dir is None:
            output_dir = os.path.join(_pkg_root, 'reports', date_str)
        os.makedirs(output_dir, exist_ok=True)

        json_path = os.path.join(output_dir, f'portfolio_summary_{timestamp}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成HTML
        html_path = os.path.join(output_dir, f'portfolio_summary_{timestamp}.html')
        html_content = self._generate_html(report_data, timestamp)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"组合报告生成完成: {html_path}")
        return html_path, json_path

    def _build_report_data(self, fund_analyses: List[FundHoldingAnalysis],
                          summary: PortfolioSummary) -> Dict[str, Any]:
        """构建报告数据"""
        return {
            "report_type": "portfolio_summary",
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "summary": {
                "total_cost": round(summary.total_cost, 2),
                "total_value": round(summary.total_value, 2) if summary.total_value else None,
                "total_return": round(summary.total_return, 2) if summary.total_return else None,
                "total_return_pct": round(summary.total_return_pct, 2) if summary.total_return_pct else None,
                "fund_count": summary.fund_count,
                "avg_score": summary.avg_score,
                "risk_distribution": summary.risk_distribution,
                "action_distribution": summary.action_distribution
            },
            "holdings": [
                {
                    "fund_code": h.fund_code,
                    "fund_name": h.fund_name,
                    "fund_type": h.fund_type,
                    "cost_amount": round(h.cost_amount, 2),
                    "current_nav": h.current_nav,
                    "current_value": round(h.current_value, 2) if h.current_value else None,
                    "return_pct": round(h.return_pct, 2) if h.return_pct else None,
                    "weight_pct": round(h.cost_amount / summary.total_cost * 100, 1) if summary.total_cost > 0 else 0,
                    "target_pct": h.target_pct,
                    "min_pct": h.min_pct,
                    "max_pct": h.max_pct,
                    "action": h.action,
                    "total_score": h.total_score,
                    "tech_score": h.tech_score
                }
                for h in fund_analyses
            ]
        }

    def _generate_html(self, data: Dict[str, Any], report_timestamp: str) -> str:
        """生成HTML报告"""
        summary = data['summary']
        holdings = data['holdings']

        # 计算仓位分布
        cost_by_type = {}
        for h in holdings:
            ft = h['fund_type']
            cost_by_type[ft] = cost_by_type.get(ft, 0) + h['cost_amount']

        total_cost = summary['total_cost']

        # 处理可能的None值
        total_value_str = f"¥{summary['total_value']:,.0f}" if summary.get('total_value') else "¥-"
        total_return = summary.get('total_return')
        total_return_pct = summary.get('total_return_pct')
        return_str = f"{total_return:,.0f}" if total_return is not None else "-"
        return_pct_str = f"({total_return_pct:+.1f}%)" if total_return_pct is not None else ""
        return_class = "positive" if total_return and total_return > 0 else ("negative" if total_return and total_return < 0 else "")

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>持仓组合分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .subtitle {{ opacity: 0.9; font-size: 14px; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .summary-card .label {{
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            font-size: 24px;
            font-weight: 700;
            color: #333;
        }}
        .summary-card .positive {{ color: #16a34a; }}
        .summary-card .negative {{ color: #dc2626; }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .card h2 {{
            font-size: 18px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .chart-container {{
            height: 300px;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            font-size: 13px;
            color: #666;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-buy {{ background: #dcfce7; color: #166534; }}
        .badge-hold {{ background: #dbeafe; color: #1e40af; }}
        .badge-watch {{ background: #fef3c7; color: #92400e; }}
        .badge-sell {{ background: #fee2e2; color: #991b1b; }}
        .score {{ font-weight: 700; }}
        .score-high {{ color: #16a34a; }}
        .score-mid {{ color: #ca8a04; }}
        .score-low {{ color: #dc2626; }}
        .fund-link {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            cursor: pointer;
        }}
        .fund-link:hover {{
            color: #764ba2;
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 持仓组合分析报告</h1>
            <div class="subtitle">生成时间: {data['generated_at']}</div>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">持仓基金数</div>
                <div class="value">{summary['fund_count']}只</div>
            </div>
            <div class="summary-card">
                <div class="label">总投入成本</div>
                <div class="value">¥{summary['total_cost']:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">当前市值</div>
                <div class="value">{total_value_str}</div>
            </div>
            <div class="summary-card">
                <div class="label">总收益</div>
                <div class="value {return_class}">
                    {return_str} {return_pct_str}
                </div>
            </div>
            <div class="summary-card">
                <div class="label">平均评分</div>
                <div class="value">{summary['avg_score']:.1f}分</div>
            </div>
        </div>

        <div class="card">
            <h2>📈 资产配置分布</h2>
            <div class="chart-container">
                <canvas id="allocationChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>📋 持仓详情</h2>
            <table>
                <thead>
                    <tr>
                        <th>基金代码</th>
                        <th>基金名称</th>
                        <th>类型</th>
                        <th>成本金额</th>
                        <th>占比</th>
                        <th>收益</th>
                        <th>评分</th>
                        <th>建议</th>
                    </tr>
                </thead>
                <tbody>
'''

        # 添加持仓行
        for h in holdings:
            action_class = {
                '加仓': 'badge-buy',
                '持有': 'badge-hold',
                '观望': 'badge-watch',
                '减仓': 'badge-sell'
            }.get(h['action'], 'badge-hold')

            score_class = 'score-high' if h['total_score'] >= 60 else ('score-mid' if h['total_score'] >= 40 else 'score-low')

            return_str_row = f"{h['return_pct']:+.1f}%" if h['return_pct'] else '-'

            # 构建基金详情链接（查找对应的报告文件）
            fund_code = h['fund_code']

            html += f'''
                    <tr>
                        <td><a class="fund-link" href="./report_{fund_code}_{report_timestamp}.html" target="_blank">{fund_code}</a></td>
                        <td>{h['fund_name'][:15]}...</td>
                        <td>{h['fund_type']}</td>
                        <td>¥{h['cost_amount']:,.0f}</td>
                        <td>{h['weight_pct']:.1f}%</td>
                        <td>{return_str_row}</td>
                        <td class="score {score_class}">{h['total_score']:.0f}</td>
                        <td><span class="badge {action_class}">{h['action']}</span></td>
                    </tr>
'''

        # 准备图表数据
        type_labels = list(cost_by_type.keys())
        type_data = [cost_by_type[t] for t in type_labels]

        html += f'''
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>💡 投资建议</h2>
            <ul style="margin-left: 20px; line-height: 2;">
                <li>组合平均评分 <strong>{summary['avg_score']:.1f}分</strong>，整体{'表现良好' if summary['avg_score'] >= 60 else '表现一般'}</li>
                <li>共有 <strong>{summary['fund_count']}</strong> 只基金，建议保持适度分散</li>
                <li>操作建议分布: {', '.join([f"{k}: {v}只" for k, v in summary['action_distribution'].items()])}</li>
                <li>建议定期检查仓位配置，确保符合目标比例</li>
            </ul>
        </div>
    </div>

    <script>
        // 资产配置饼图
        const ctx = document.getElementById('allocationChart').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(type_labels, ensure_ascii=False)},
                datasets: [{{
                    data: {type_data},
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f093fb', '#f5576c',
                        '#4facfe', '#00f2fe', '#43e97b', '#fa709a'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{ fontSize: 12 }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
'''
        return html


def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description="生成持仓组合分析报告")
    parser.add_argument("--output-dir", help="报告输出目录")
    args = parser.parse_args()

    analyzer = PortfolioAnalyzer()
    html_path, json_path = analyzer.generate_report(args.output_dir)

    print(f"\n✅ 组合分析报告生成完成!")
    print(f"📄 HTML报告: {html_path}")
    print(f"📊 JSON数据: {json_path}")


if __name__ == "__main__":
    main()
