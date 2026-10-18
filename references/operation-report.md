# 单文件操作分析报告

用户要求操作分析或完整报告时使用`operation_report.py`，不要只交付评分检查表。使用同一证据文档的`funds`/`metrics`（见[参考评分](research-scoring.md)），先完成产品与组合研究，再显式补充操作判断。新入口只输出一个HTML，数据、样式、图表及评分均内嵌，复制该文件即可离线查看。

```bash
python scripts/operation_report.py --input <本地证据JSON> --output <本地私密目录/report.html>
python -m unittest tests.test_operation_report -v
```

输入证据文件可以是已有本地研究输入；不是要求额外给用户交付JSON。可通过Python API `generate(document, output_html)`直接传入内存文档。原始输入、历史报告不因单文件交付而删除。

## 组合部分

顶层`report_date`是本次生成日，`as_of`是持仓/评分研究基准日，不能混为行情日。`portfolio_review`可包含：

- `headline`与`conclusions`：具体组合判断与理由，区分事实/估计/建议。
- `plan`：优先级列表，每项`priority, scope, action, condition`。
- `execution_rules`：操作节奏、费用/流动性及复核规则，不做自动交易承诺。
- `allocation`：列表，每项`label, account_pct`，必须来自已知同口径市值；未知不填0。
- `stress`：列表，每项`label, shocks_pct, loss, loss_account_pct, loss_fund_only_pct`。`stress_note`必须写明分组、人为假设、分母与未覆盖成本，不将其称为预测/历史回测。
- `alternatives`：维持、暂停新增、新资金纠偏、赎回重配的条件比较，每项`name, when, benefit, cost`。
- `data_note, limitations, sources`：各类数据日期、主要未知及可核实公开来源。

没有个人资金用途、风险约束或来源时，不为了完整版面编造这些内容。不同基金评分不平均为组合风险等级。

## 每只基金的操作分析

`operation_analysis`为研究者显式提供的对象，包含：

| 字段 | 内容 |
| --- | --- |
| stance / priority / role | 当前处理倾向、优先级、组合用途 |
| reasons | 支撑判断的具体证据，字符串列表 |
| next_step | 现在可讨论的处理步骤 |
| add_condition | 何种用途、配置、风险与费用条件下才考虑新增 |
| reduce_condition | 何种变化下考虑降低/退出；不机械等待回本 |
| cost_checks | 本人确认日、持有期、实际费用、到账/限购等核对项 |
| alternative | 维持/暂停/新增资金调整等替代路线与代价 |

操作分析是建议而非已批准交易。即使提供建议，也不虚构个人可赎份额或精确下单金额。未提供操作判断时显示“观察，先核用途”，不会把低分自动转成卖出。低分只作调查线索；高分也不能绕过用途和风险预算。

每只基金可带`redemption_fees`（平台列示`name,value`，非本人已适用的费率）和`nav_history`（`date,nav`）。走势图按真实日期间隔绘制抽样单位净值，明确未复权/含分红影响，不据此计算日频RSI、均线或精确点位。已有`context`阶段业绩和经理资料、原始评分依据继续展示并折叠，避免喧宾夺主。

## 验证

检查唯一输出HTML、可独立复制、全部持仓保留、目录/搜索/展开/打印、输入文本转义、内嵌JSON完整性及来源时点。实际报告只放Private/忽略路径。此入口新增操作呈现，不证明研究建议能预测收益。
