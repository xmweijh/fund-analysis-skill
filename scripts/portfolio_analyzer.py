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
from scripts.fund_analyzer_v2 import FundAnalyzerV2


@dataclass
class FundHoldingAnalysis:
    """单个基金持仓分析"""
    fund_code: str
    fund_name: str
    fund_type: str
    cost_amount: Optional[float]
    current_nav: Optional[float]
    current_value: Optional[float]
    return_pct: Optional[float]
    target_pct: float
    min_pct: float
    max_pct: float
    action: str
    total_score: float
    tech_score: float
    v2_score: Optional[float] = None  # V2五维评分
    dimensions: Optional[Dict[str, Any]] = None  # 五维详情
    stored_profit: Optional[float] = None        # 持仓盈亏（来自portfolio.json）
    stored_return_rate: Optional[float] = None   # 持仓收益率%（来自portfolio.json）


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
        self.v2_analyzer = FundAnalyzerV2()

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
            cost_amount = entry.cost_amount  # 保留 None，不做 or 0
            total_cost += cost_amount or 0

            # 获取基金信息
            basic_info = self._safe_fetch(
                self.data_fetcher.fetch_basic_info, fund_code
            )
            quote = self._safe_fetch(
                self.data_fetcher.fetch_realtime_quote, fund_code
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
                if cost_amount and cost_amount > 0:
                    return_pct = (current_value - cost_amount) / cost_amount * 100
            elif current_nav and cost_amount and cost_amount > 0:
                # 估算市值
                avg_cost = entry.cost_nav or current_nav
                current_value = cost_amount * (current_nav / avg_cost)
                total_value += current_value
                return_pct = (current_nav / avg_cost - 1) * 100

            # 使用 FundAnalyzerV2 进行完整分析
            v2_result = self._analyze_with_v2(fund_code)

            # 汇总统计（使用V2评分）
            fund_score = v2_result['total_score']
            tech_score = v2_result['tech_score']
            action = v2_result['action']
            risk_level = v2_result['risk_level']

            total_score += fund_score
            action_dist[action] = action_dist.get(action, 0) + 1
            risk_dist[risk_level] = risk_dist.get(risk_level, 0) + (cost_amount or 0)

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
                total_score=fund_score,
                tech_score=tech_score,
                v2_score=fund_score,
                dimensions=v2_result.get('dimensions'),
                stored_profit=entry.current_profit,
                stored_return_rate=entry.current_return_rate,
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

    def _analyze_with_v2(self, fund_code: str) -> Dict[str, Any]:
        """
        使用 FundAnalyzerV2 进行完整分析，从生成的JSON报告读取结果
        """
        try:
            # 运行分析生成报告
            html_path, json_path = self.v2_analyzer.analyze(fund_code)

            # 从JSON报告读取结果
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    result = json.load(f)

                scores = result.get('scores')
                if not scores or any(scores.get(key) is None for key in
                    ('total', 'technical', 'fundamental', 'valuation', 'capital_flow', 'sentiment')):
                    raise ValueError('评分不可用，需核实基金类型及数据')
                if result.get('action') == '不可评价':
                    raise ValueError('仓位建议不可用，需核实配置及数据')
                action = result.get('action', '持有')
                position_advice = result.get('position_advice', {})

                # 提取五维评分
                total_score = scores.get('total', 50.0)
                tech_score = scores.get('technical', 50.0)
                dimensions = {
                    'technical': scores.get('technical', 50.0),
                    'fundamental': scores.get('fundamental', 50.0),
                    'valuation': scores.get('valuation', 50.0),
                    'capital_flow': scores.get('capital_flow', 50.0),
                    'sentiment': scores.get('sentiment', 50.0),
                }

                # 获取操作建议
                if not action:
                    action = position_advice.get('action', '持有')
                if not action:
                    action = self._score_to_action(total_score)

                # 获取风险等级（根据评分计算）
                risk_level = '待核实'

                return {
                    'total_score': total_score,
                    'tech_score': tech_score,
                    'action': action,
                    'risk_level': risk_level,
                    'dimensions': dimensions
                }
            else:
                logger.warning(f"JSON报告不存在: {json_path}")
                raise FileNotFoundError(f"Report not found: {json_path}")

        except Exception as e:
            raise ValueError(f"基金 {fund_code} 分析不可用，组合报告已停止：{e}") from e

    def _score_to_action(self, score: float) -> str:
        """根据评分确定操作建议"""
        if score >= 70:
            return "加仓"
        elif score >= 55:
            return "持有"
        elif score >= 40:
            return "观望"
        else:
            return "减仓"

    def _score_to_risk(self, score: float) -> str:
        """吸引力评分不能决定产品风险等级。"""
        return "待核实"

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
        # 用 portfolio.json 存储的盈亏数据汇总总收益（比实时计算更可靠）
        stored_profits = [h.stored_profit for h in fund_analyses if h.stored_profit is not None]
        stored_total_profit = round(sum(stored_profits), 2) if stored_profits else None
        stored_total_profit_pct = (
            round(stored_total_profit / summary.total_cost * 100, 2)
            if stored_total_profit is not None and summary.total_cost > 0
            else None
        )

        return {
            "report_type": "portfolio_summary",
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "summary": {
                "total_cost": round(summary.total_cost, 2),
                "total_value": round(summary.total_value, 2) if summary.total_value else None,
                # 优先用 stored_total_profit（来自用户录入的实际盈亏数据）；
                # 仅当有精确 shares 数据时才用实时计算值
                "total_return": stored_total_profit if stored_total_profit is not None else summary.total_return,
                "total_return_pct": stored_total_profit_pct if stored_total_profit_pct is not None else summary.total_return_pct,
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
                    "cost_amount": round(h.cost_amount, 2) if h.cost_amount is not None else None,
                    "current_nav": h.current_nav,
                    "current_value": round(h.current_value, 2) if h.current_value else None,
                    "return_pct": round(h.return_pct, 2) if h.return_pct else None,
                    "stored_profit": h.stored_profit,
                    "stored_return_rate": h.stored_return_rate,
                    "weight_pct": round((h.cost_amount or 0) / summary.total_cost * 100, 1) if summary.total_cost > 0 else 0,
                    "target_pct": h.target_pct,
                    "min_pct": h.min_pct,
                    "max_pct": h.max_pct,
                    "action": h.action,
                    "total_score": h.total_score,
                    "tech_score": h.tech_score,
                    "dimensions": h.dimensions,
                    "report_file": self._find_fund_report_file(h.fund_code)
                }
                for h in fund_analyses
            ]
        }

    def _find_fund_report_file(self, fund_code: str) -> Optional[str]:
        """查找基金的最新报告文件"""
        import glob
        import os

        # 获取报告目录
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'reports',
            datetime.now().strftime('%Y%m%d')
        )

        # 查找匹配的文件
        pattern = os.path.join(output_dir, f"report_{fund_code}_*.html")
        files = glob.glob(pattern)

        if files:
            # 按修改时间排序，返回最新的
            files.sort(key=os.path.getmtime, reverse=True)
            return os.path.basename(files[0])
        return None

    def _generate_html(self, data: Dict[str, Any], report_timestamp: str) -> str:
        """生成HTML报告"""
        summary = data['summary']
        holdings = data['holdings']

        # 计算仓位分布
        cost_by_type = {}
        for h in holdings:
            ft = h['fund_type']
            cost_by_type[ft] = cost_by_type.get(ft, 0) + (h['cost_amount'] or 0)

        total_cost = summary['total_cost']

        # 处理可能的None值
        total_value_str = f"¥{summary['total_value']:,.0f}" if summary.get('total_value') else "¥-"
        total_return = summary.get('total_return')
        total_return_pct = summary.get('total_return_pct')
        if total_return is not None:
            return_str = f"{total_return:+,.0f}"
        else:
            return_str = "-"
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
        .dimension-bar {{
            display: flex;
            height: 4px;
            border-radius: 2px;
            overflow: hidden;
            margin-top: 4px;
        }}
        .dimension-bar > div {{ height: 100%; }}
        .dim-tech {{ background: #667eea; }}
        .dim-fund {{ background: #764ba2; }}
        .dim-val {{ background: #f093fb; }}
        .dim-cap {{ background: #f5576c; }}
        .dim-sen {{ background: #4facfe; }}
        td.positive {{ color: #16a34a; font-weight: 600; }}
        td.negative {{ color: #dc2626; font-weight: 600; }}
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
                        <th>浮动盈亏</th>
                        <th>收益率</th>
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

            # 优先用 portfolio.json 存储的盈亏值（来自用户截图）
            stored_profit = h.get('stored_profit')
            stored_return_rate = h.get('stored_return_rate')
            if stored_profit is not None:
                profit_str = f"{stored_profit:+,.2f}"
                profit_class = "positive" if stored_profit > 0 else ("negative" if stored_profit < 0 else "")
            else:
                profit_str = "-"
                profit_class = ""
            if stored_return_rate is not None:
                rate_str = f"{stored_return_rate:+.2f}%"
                rate_class = "positive" if stored_return_rate > 0 else ("negative" if stored_return_rate < 0 else "")
            else:
                rate_str = "-"
                rate_class = ""

            # 构建基金详情链接（使用查找的报告文件）
            fund_code = h['fund_code']
            report_file = h.get('report_file')
            report_link = f"./{report_file}" if report_file else f"./report_{fund_code}_latest.html"

            fund_display_name = h['fund_name']
            if len(fund_display_name) > 12:
                fund_display_name = fund_display_name[:12] + '…'

            html += f'''
                    <tr>
                        <td><a class="fund-link" href="{report_link}" target="_blank">{fund_code}</a></td>
                        <td>{fund_display_name}</td>
                        <td>{h['fund_type']}</td>
                        <td>{"¥{:,.0f}".format(h['cost_amount']) if h['cost_amount'] else "—"}</td>
                        <td>{h['weight_pct']:.1f}%</td>
                        <td class="{profit_class}">{profit_str}</td>
                        <td class="{rate_class}">{rate_str}</td>
                        <td class="score {score_class}">{h['total_score']:.1f}</td>
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
