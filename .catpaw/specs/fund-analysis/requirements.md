# 基金分析技能需求文档

## 介绍

本需求文档定义了"基金分析技能"的功能需求。该技能是一个智能基金分析系统,能够对用户指定的基金进行多维度深度分析,包括技术面、基本面、舆情和实时行情等方面,并生成专业的投资建议报告。

## 术语表

- **基金代码**: 用于唯一标识基金的代码(如: 008975)
- **基金名称**: 基金的全称(如: 易方达蓝筹精选混合)
- **净值**: 基金每份单位的资产净值
- **MA均线**: 移动平均线,用于判断价格趋势
- **多头排列**: 短期均线在上,长期均线在下的技术形态
- **筹码分布**: 基金持仓的结构和分布情况
- **舆情情报**: 与基金相关的新闻报道和市场情绪
- **买点**: 建议买入的价格区间
- **卖点**: 建议卖出的价格区间
- **止盈位**: 建议止盈的价格目标
- **止损位**: 建议止损的价格底线

## 需求

### 需求 1: 基金数据获取

**用户故事**: 作为投资者,我希望能够获取基金的基础信息和实时数据,以便了解基金的当前状态。

#### 验收标准

1. WHEN 用户输入有效的基金代码,THE Fund_Data_Fetcher SHALL 从蛋卷基金API获取基金基础信息,包括基金名称、基金类型、基金规模、成立日期
2. WHEN 用户输入有效的基金代码,THE Fund_Data_Fetcher SHALL 从蛋卷基金API获取基金的实时行情数据,包括当前净值、日涨跌幅、近7日年化收益率
3. WHEN 用户输入有效的基金代码,THE Fund_Data_Fetcher SHALL 从蛋卷基金API获取基金的净值历史数据,至少包含最近一年的每日净值
4. WHEN 用户输入无效的基金代码,THE Fund_Data_Fetcher SHALL 返回清晰的错误信息,提示用户基金代码不存在
5. WHEN 数据获取失败,THE Fund_Data_Fetcher SHALL 记录详细的错误日志,包括失败原因和时间戳

### 需求 2: 技术面分析

**用户故事**: 作为投资者,我希望了解基金的技术指标和趋势,以便判断买卖时机。

#### 验收标准

1. WHEN 基金净值历史数据可用,THE Technical_Analyzer SHALL 计算并分析5日、10日、20日、60日移动平均线(MA5、MA10、MA20、MA60)
2. WHEN MA5 > MA10 > MA20 > MA60,THE Technical_Analyzer SHALL 判定为多头排列,标记为看涨信号
3. WHEN MA5 < MA10 < MA20 < MA60,THE Technical_Analyzer SHALL 判定为空头排列,标记为看跌信号
4. WHEN 当前净值突破MA20,THE Technical_Analyzer SHALL 标记为技术突破信号
5. WHEN 当前净值跌破MA20,THE Technical_Analyzer SHALL 标记为技术破位信号
6. THE Technical_Analyzer SHALL 计算并显示最近30天、60天、90天的净值涨跌幅
7. THE Technical_Analyzer SHALL 判断并标注当前的上升/下降/震荡趋势

### 需求 3: 基金持仓分析

**用户故事**: 作为投资者,我希望了解基金的持仓结构,以便评估基金的风险和投资方向。

#### 验收标准

1. WHEN 基金持仓数据可用,THE Fund_Analyzer SHALL 获取前十大重仓股票列表,包括股票名称、持仓比例、持仓市值
2. WHEN 基金持仓数据可用,THE Fund_Analyzer SHALL 计算行业集中度,显示基金主要投资的前三大行业及其占比
3. WHEN 基金持仓数据可用,THE Fund_Analyzer SHALL 计算持仓集中度,即前十大重仓股的合计占比
4. WHEN 基金持仓数据可用,THE Fund_Analyzer SHALL 分析持仓风格,标记为价值型/成长型/平衡型
5. WHEN 基金持仓数据不可用,THE Fund_Analyzer SHALL 在报告中明确标注"持仓数据暂不可用"

### 需求 4: 基金经理分析

**用户故事**: 作为投资者,我希望了解基金经理的经验和业绩,以便评估基金的管理水平。

#### 验收标准

1. WHEN 基金经理数据可用,THE Fund_Analyzer SHALL 获取基金经理的姓名、从业年限、管理该基金的年限
2. WHEN 基金经理数据可用,THE Fund_Analyzer SHALL 获取基金经理管理的其他基金数量
3. WHEN 基金经理数据可用,THE Fund_Analyzer SHALL 计算基金经理的历史平均收益率和最大回撤
4. WHEN 基金经理管理该基金超过3年,THE Fund_Analyzer SHALL 标记为资深基金经理
5. WHEN 基金经理数据不可用,THE Fund_Analyzer SHALL 在报告中明确标注"基金经理信息暂不可用"

### 需求 5: 基金业绩分析

**用户故事**: 作为投资者,我希望了解基金的历史业绩,以便评估基金的投资价值。

#### 验收标准

1. WHEN 基金业绩数据可用,THE Fund_Analyzer SHALL 获取近1月、3月、6月、1年、3年、5年的收益率数据
2. WHEN 基金业绩数据可用,THE Fund_Analyzer SHALL 计算并显示年化收益率
3. WHEN 基金业绩数据可用,THE Fund_Analyzer SHALL 计算并显示最大回撤
4. WHEN 基金业绩数据可用,THE Fund_Analyzer SHALL 将基金业绩与同类基金平均值进行对比,计算相对排名
5. WHEN 基金业绩数据可用,THE Fund_Analyzer SHALL 将基金业绩与基准指数进行对比,计算超额收益
6. WHEN 基金业绩数据不可用,THE Fund_Analyzer SHALL 在报告中明确标注"业绩数据暂不可用"

### 需求 6: 舆情情报分析

**用户故事**: 作为投资者,我希望了解与基金相关的新闻和市场情绪,以便辅助投资决策。

#### 验收标准

1. WHEN 基金代码输入后,THE Sentiment_Analyzer SHALL 搜索并提取与基金相关的最新新闻标题和摘要,至少5条
2. WHEN 新闻数据获取成功,THE Sentiment_Analyzer SHALL 分析每条新闻的情绪倾向,标记为正面/负面/中性
3. WHEN 新闻数据获取成功,THE Sentiment_Analyzer SHALL 计算综合舆情得分(0-100分),90以上为强烈正面,60-90为正面,40-60为中性,20-40为负面,20以下为强烈负面
4. WHEN 新闻数据获取成功,THE Sentiment_Analyzer SHALL 提取关键词,如"业绩优异"、"持仓调整"、"市场波动"等
5. WHEN 新闻数据不可用,THE Sentiment_Analyzer SHALL 在报告中明确标注"舆情数据暂不可用,建议手动查询相关新闻"

### 需求 7: 买卖点建议

**用户故事**: 作为投资者,我希望获得精确的买卖点位建议,以便把握投资时机。

#### 验收标准

1. WHEN 技术分析、基本面分析和舆情分析完成,THE Investment_Advisor SHALL 基于综合分析生成一句话核心结论
2. WHEN 技术面显示多头排列且基本面稳健,THE Investment_Advisor SHALL 建议买入,并给出理想买点区间(如:当前净值±2%)
3. WHEN 技术面显示空头排列或基本面恶化,THE Investment_Advisor SHALL 建议谨慎持有或卖出
4. THE Investment_Advisor SHALL 根据近期波动幅度计算并显示止盈位(建议止盈价格目标)
5. THE Investment_Advisor SHALL 根据近期低点和风险偏好计算并显示止损位(建议止损价格底线)
6. THE Investment_Advisor SHALL 提供次要买点(补仓机会)的价格区间,如果当前价格不适合买入
7. THE Investment_Advisor SHALL 明确标注买入、持有、卖出、观望的操作建议

### 需求 8: 操作检查清单

**用户故事**: 作为投资者,我希望获得操作前的检查清单,以便避免盲目决策。

#### 验收标准

1. THE Investment_Advisor SHALL 生成操作检查清单,包含至少5个关键检查项
2. THE Investment_Advisor SHALL 在清单中包含"了解基金投资方向和风险等级"检查项
3. THE Investment_Advisor SHALL 在清单中包含"确认投资期限与基金类型匹配"检查项
4. THE Investment_Advisor SHALL 在清单中包含"评估个人风险承受能力"检查项
5. THE Investment_Advisor SHALL 在清单中包含"确认资金可用性"检查项
6. THE Investment_Advisor SHALL 在清单中包含"了解基金费率结构"检查项
7. THE Investment_Advisor SHALL 为每个检查项提供解释或说明

### 需求 9: 分析报告生成

**用户故事**: 作为投资者,我希望获得一份结构清晰、内容详实的分析报告,以便全面了解基金情况。

#### 验收标准

1. WHEN 所有分析完成,THE Report_Generator SHALL 生成Markdown格式的分析报告
2. THE Report_Generator SHALL 在报告中包含基金基本信息(基金名称、基金代码、基金类型、基金规模)
3. THE Report_Generator SHALL 在报告中包含实时行情(当前净值、日涨跌幅、近7日年化)
4. THE Report_Generator SHALL 在报告中包含技术面分析(MA均线状态、趋势判断、技术信号)
5. THE Report_Generator SHALL 在报告中包含持仓分析(前十大重仓股、行业集中度、持仓风格)
6. THE Report_Generator SHALL 在报告中包含基金经理信息(姓名、从业年限、管理业绩)
7. THE Report_Generator SHALL 在报告中包含业绩分析(各时间段收益率、最大回撤、相对排名)
8. THE Report_Generator SHALL 在报告中包含舆情情报(相关新闻、情绪得分、关键词)
9. THE Report_Generator SHALL 在报告中包含投资建议(核心结论、买卖点位、操作检查清单)
10. THE Report_Generator SHALL 使用清晰的Markdown格式,包含标题层级、列表、表格、加粗等格式化元素

### 需求 10: 支持多种基金类型

**用户故事**: 作为投资者,我希望该技能支持所有类型的基金,以便分析我的所有投资标的。

#### 验收标准

1. WHEN 用户输入股票型基金代码,THE Fund_Analyzer SHALL 能够成功获取并分析股票型基金
2. WHEN 用户输入债券型基金代码,THE Fund_Analyzer SHALL 能够成功获取并分析债券型基金
3. WHEN 用户输入混合型基金代码,THE Fund_Analyzer SHALL 能够成功获取并分析混合型基金
4. WHEN 用户输入指数型基金代码,THE Fund_Analyzer SHALL 能够成功获取并分析指数型基金
5. WHEN 用户输入QDII基金代码,THE Fund_Analyzer SHALL 能够成功获取并分析QDII基金
6. THE Fund_Analyzer SHALL 根据基金类型调整分析指标和分析侧重点

### 需求 11: 错误处理和用户反馈

**用户故事**: 作为用户,我希望系统在遇到问题时能够提供清晰的错误信息和处理建议。

#### 验收标准

1. WHEN 用户输入无效的基金代码,THE System SHALL 返回友好的错误提示"基金代码不存在,请检查后重试"
2. WHEN 数据获取超时,THE System SHALL 返回错误提示"数据获取超时,请稍后重试"
3. WHEN API请求失败,THE System SHALL 记录详细的错误日志,包括错误类型和堆栈信息
4. THE System SHALL 在所有错误情况下提供用户可理解的错误描述
5. THE System SHALL 在错误情况下尽可能提供恢复建议或替代方案

### 需求 12: 性能要求

**用户故事**: 作为用户,我希望分析过程能够快速完成,以便及时获得投资建议。

#### 验收标准

1. WHEN 用户提交分析请求,THE System SHALL 在30秒内完成数据获取和基础分析
2. WHEN 数据量正常,THE System SHALL 在60秒内生成完整的分析报告
3. WHEN 系统负载正常,THE System SHALL 支持并发处理至少3个基金的分析请求
