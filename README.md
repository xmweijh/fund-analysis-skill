# 基金分析技能

面向公开基金产品研究和本地持仓分析，提供公开数据采集、来源核验、分类型基础参考及离线报告。操作判断由具体研究提供，不由分数自动生成交易。

## 默认能力

- 采集公开费率、资产配置及管理人定期报告，保留原文、日期和失败状态。
- 从完整报告核对总资产/净资产、实际股票和转债配置、符合条件的完整权益集中度。
- 接入已有产品缓存的阶段业绩与现任团队任期。
- 默认`public-core-v2.0`，输出有限维度的基础参考分及基础证据覆盖。支持六类产品，规则为启发式，未经收益预测验证。
- 完整操作分析生成一个独立HTML；单独评分入口生成HTML及可复算JSON。

## 字段和评分范围

| 类型 | 默认基础维度 |
| --- | --- |
| 债券 | 一年回撤、名义费用、披露杠杆、转债比例 |
| 增强债/偏债配置 | 一年回撤、费用、杠杆、股票/转债比例 |
| 主动权益 | 一年回撤、费用、完整股票集中度、现任团队连续性 |
| 指数/联接 | 一年回撤、费用；不评价跟踪质量与估值 |
| 货币 | 费用、注明渠道的常规到账；不评价信用安全 |

信用细分、组合久期、三年合同基准超额、真实日频跟踪误差和长期估值百分位不再是默认必填评分。它们有条件获取，但不能保证每只基金都有免费、同口径数据。证据有效时作为扩展研究展示，不显示一排没有数据的必填项，也不影响基础覆盖率。渠道及当前接入状态见[数据源说明](references/fund-data-sources.md)。

基础维度100%仅代表本模型资料齐全，不能称为基金综合评级或完整风险覆盖。新版缩小了评分范围，不能将其覆盖率与旧模型直接比较。历史`research-v1.0`仍可显式复算。

## 使用

```bash
pip install -r requirements.txt
python scripts/public_data_sources.py --codes <六位代码> --as-of <YYYY-MM-DD> --cache-dir <本地缓存>
python scripts/operation_report.py --input <本地研究JSON> --supplemental-data-dir <本地缓存> --output <本地报告.html>
python scripts/research_report.py --input <本地证据JSON> --supplemental-data-dir <本地缓存> --output-dir <本地输出目录>
python -m pytest tests -q
```

可选采集代理用`--proxy`指定，显式刷新用`--refresh`。离线报告不联网；公开报告采集需要`pypdf`，原V1/V2功能另使用原依赖。实际持仓、报告、缓存只在本地私密/忽略目录保存，外部接口只接收公开基金代码。

输入字段、版本选择和权重见[评分契约](references/research-scoring.md)，完整研究判断见[操作报告契约](references/operation-report.md)。技能入口见[SKILL.md](SKILL.md)。

[历史V1/V2接口和示例](references/legacy-usage.md)保留供兼容查阅；其中旧版自动操作、舆情或推荐器的描述不代表默认基础入口具备相同能力。旧算法边界见[计算边界](references/analysis-boundaries.md)。
