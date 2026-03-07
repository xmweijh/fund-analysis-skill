# 基金分析技能 (Fund Analysis)

智能基金分析系统，支持单基金深度分析、持仓管理（CRUD）和批量持仓组合分析，生成包含操作建议卡片、重仓股实时行情、真实舆情的专业 Markdown 报告。

## 功能特性

- 📋 **顶部操作建议卡片**：综合评分后给出 加仓/建仓/定投/持有/减仓/清仓 等明确操作建议
- 📊 **多维度分析**：技术面（MA均线/趋势/信号）、基本面（业绩/经理/持仓）、舆情面三位一体
- 📈 **重仓股实时行情**：前十大重仓股含最新价和涨跌幅（东财 push2his 接口，支持 A 股 + 港股）
- 🗞️ **真实舆情接入**：东方财富基金公告接口，自动过滤季报/年报/运营例行公告，只展示实质性利空/利好信号
- 📂 **持仓管理**：支持增删改查，跨会话持久化存储（`data/portfolio.json`）
- 📦 **批量持仓分析**：一键分析所有持仓基金，生成组合汇总报告
- 💾 **报告自动保存**：所有报告统一存入 `reports/` 目录

## 数据源

| 数据 | 来源 |
|------|------|
| 基金基本信息、净值历史、持仓、业绩、经理 | 蛋卷基金 API（pysnowball） |
| 基金公告/舆情 | 东方财富 `/f10/jjgg` 接口 |
| 重仓股实时行情 | 东方财富 `push2his` 日K接口 |

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 单基金分析

```python
from scripts.fund_analyzer import FundAnalyzer

analyzer = FundAnalyzer()

# 分析单只基金（报告自动保存到 reports/ 目录）
report = analyzer.analyze("017043")
print(report)
```

或直接命令行运行：

```bash
python scripts/fund_analyzer.py 017043
```

### 持仓管理

```python
# 新增/更新持仓
analyzer.portfolio_add("008975", fund_name="易方达蓝筹精选混合",
                        shares=100000, cost_nav=1.52, cost_amount=152000)

# 查看持仓列表
print(analyzer.portfolio_list())

# 删除持仓
analyzer.portfolio_remove("008975")
```

### 批量持仓分析

```python
# 一键分析所有持仓，报告保存到 reports/portfolio_analysis_{ts}.md
report = analyzer.portfolio_analyze_all()
```

## 报告结构

每份报告包含以下章节（顺序如下）：

1. **📋 综合操作建议**（顶部卡片，含操作建议/近1年收益/回撤/舆情/买卖点位）
2. **📊 基金基本信息**
3. **📈 实时行情**
4. **📉 技术面分析**（MA均线/趋势/信号/近期收益率）
5. **🏢 持仓分析**（前十大重仓股含实时涨跌幅 + 行业分布）
6. **👨‍💼 基金经理分析**
7. **📊 业绩分析**（逐年业绩 & 同类排名对比表）
8. **📰 舆情分析**（已过滤例行公告，只展示实质信号）
9. **💼 详细投资建议**（买卖点位 + 操作检查清单）

## 项目结构

```
fund-analysis/
├── SKILL.md                    # 技能文档（Agent 触发描述）
├── README.md                   # 项目说明（本文件）
├── requirements.txt            # Python 依赖
├── data/
│   └── portfolio.json          # 用户持仓数据（持久化）
├── reports/                    # 生成的分析报告
│   ├── fund_analysis_{code}_{ts}.md
│   └── portfolio_analysis_{ts}.md
├── scripts/
│   ├── fund_analyzer.py        # 主控制器（入口）
│   ├── data_fetcher.py         # 数据获取（蛋卷 + 东财）
│   ├── technical_analysis.py   # 技术面分析
│   ├── holding_analysis.py     # 持仓分析
│   ├── manager_analysis.py     # 基金经理分析
│   ├── performance_analysis.py # 业绩分析
│   ├── sentiment_analysis.py   # 舆情分析（真实公告接入）
│   ├── investment_advisor.py   # 投资建议生成
│   ├── report_generator.py     # 报告渲染
│   ├── portfolio_manager.py    # 持仓 CRUD 管理
│   ├── models.py               # Pydantic 数据模型
│   └── logger.py               # 日志模块
├── references/                 # 参考文档
└── examples/                   # 示例报告
```

## 分析维度说明

| 维度 | 核心指标 |
|------|---------|
| 技术面 | MA5/10/20/60、多空排列、趋势（上升/下降/震荡）、偏离度 |
| 持仓 | 前10重仓股（含实时价格涨跌）、集中度、行业分布、持仓风格 |
| 基金经理 | 从业年限、管理年限、平均收益率、最大回撤 |
| 业绩 | 近1/3/6月、1/3年收益率、逐年超额收益、同类排名百分位 |
| 舆情 | 东财公告情绪评分（0-100）、实质性利空/利好公告（过滤季报/年报） |
| 综合 | 技术面40% + 基本面40% + 舆情20% 加权评分 |

## 许可证

MIT License
