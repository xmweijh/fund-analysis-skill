# 推荐基金功能实现计划（方案 B）

## 目标
在现有 fund-analysis skill 基础上，新增**多维度评分推荐**功能，让用户可以：
- 输入风险偏好和投资目标
- 获得 Top 10 推荐基金列表
- 每只基金都包含完整分析报告 + 推荐理由

## 核心设计

### 1. 新增模块

#### `recommendation_engine.py` - 核心推荐引擎
- **`FundScorer`** 类：计算基金综合评分
  - 技术面评分 (40%): 趋势 + 信号 + 偏离度
  - 基本面评分 (40%): 业绩 + 经理 + 持仓
  - 舆情评分 (20%): 情绪分数
  - **总分公式**：`tech_score * 0.4 + fundamental_score * 0.4 + sentiment_score * 0.2`

- **`FundRanker`** 类：排序和筛选
  - 按总分排序
  - 按风险等级筛选（低/中/高）
  - 按投资目标筛选（短期 < 1年、中期 1-3年、长期 > 3年）

- **预留接口**：为方案 C 留好扩展点
  - `score()` 方法签名保持不变，后续可改为机器学习模型

#### `recommendation_advisor.py` - 推荐建议生成
- **`RecommendationCardGenerator`** 类：生成推荐卡片
  - 为每只推荐基金生成"为什么推荐"的理由
  - 示例：`"推荐理由：近3年收益 +47%，超越同类 86%，技术面多头排列，舆情中性稳健"`

#### `fund_recommender.py` - 主推荐器（新的 FundRecommender 类）
- 整合 `FundScorer`、`FundRanker`、`RecommendationCardGenerator`
- 支持多个基金来源（目前只支持蛋卷，后续可扩展）
- 暴露 `recommend(risk_level, investment_period, top_n=10)` 方法

### 2. 新增 CLI 命令

```bash
# 推荐中风险、长期投资的基金，Top 10
python scripts/fund_analyzer.py recommend --risk medium --period long --top 10

# 推荐高收益、短期的基金，Top 5
python scripts/fund_analyzer.py recommend --risk high --period short --top 5
```

### 3. 输出格式

```
# 推荐基金列表（Medium Risk, Long-term Investment）

## 📊 推荐摘要
- 扫描基金数量: 5000+
- 推荐基金数: 10
- 推荐时间: 2026-03-09 16:00:00

---

## 🏆 Top 10 推荐基金

### #1 易方达消费行业 (110022)
**综合评分**: ⭐⭐⭐⭐⭐ 8.7/10
- 📈 技术面评分: 8.5/10 (多头排列，上升趋势)
- 💰 基本面评分: 8.9/10 (3年收益 +62%，超越同类 89%)
- 📢 舆情评分: 8.3/10 (中性偏正面，最近有分红)
**推荐理由**: 基本面扎实，长期表现优异，经理资深。

### #2 中欧医疗健康 (003095)
...（类似卡片）

---

## 📌 使用建议
- 建议定期更新分析
- 根据个人风险承受能力选择
- 优先考虑排名前三的基金
```

## 实现路径

### Phase 1: 核心引擎（2-3 小时）
- [ ] 实现 `FundScorer` 类（评分算法）
- [ ] 实现 `FundRanker` 类（排序筛选）
- [ ] 编写单元测试

### Phase 2: 推荐生成（1-2 小时）
- [ ] 实现 `RecommendationCardGenerator` 类
- [ ] 实现 `FundRecommender` 主类
- [ ] 集成到 `FundAnalyzer`

### Phase 3: CLI 和集成（1 小时）
- [ ] 扩展 CLI 命令处理
- [ ] 更新 SKILL.md 文档
- [ ] 测试端到端流程

### Phase 4: 方案 C 预留（0 小时 - 设计阶段）
- [ ] 在 `FundScorer.score()` 中预留模型切换点
- [ ] 文档中记录升级路径

## 技术细节

### 基金评分算法

**技术面评分** (40%):
- 趋势权重 40%: 上升 = 100, 震荡 = 70, 下降 = 40
- 信号权重 40%: 买入信号数量 × 10（上限 100）
- 偏离度权重 20%: 偏离度 < 10% = 100, 10-20% = 70, > 20% = 40

**基本面评分** (40%):
- 近3年收益权重 50%: 归一化后 (return - min_return) / (max_return - min_return) × 100
- 经理资历权重 30%: 资深 = 90, 中等 = 70, 新手 = 50
- 持仓质量权重 20%: 集中度 < 40% = 100, 40-60% = 70, > 60% = 40

**舆情评分** (20%):
- 直接使用情绪得分 (0-100)

### 风险等级映射

| 等级 | 近1年收益 | 最大回撤 | 波动率 | 适合投资者 |
|------|---------|---------|-------|----------|
| 低   | 5-8%    | < 10%   | < 5%  | 保守型   |
| 中   | 8-15%   | 10-20%  | 5-10% | 平衡型   |
| 高   | > 15%   | 20-30%  | > 10% | 激进型   |

### 投资期限映射

| 期限   | 推荐特性 |
|-------|---------|
| 短期  | 技术面权重↑，近期涨幅优先 |
| 中期  | 技术面+基本面均衡 |
| 长期  | 基本面权重↑，长期收益优先 |

## 预留扩展点（方案 C 升级）

1. **模型接口** (`/scripts/models/recommendation_models.py`)
   ```python
   class RecommendationModel:
       def score(self, fund_analysis_data) -> float:
           """计算基金得分 (0-100)"""
           pass
   
   # 方案B: 规则模型
   class RuleBasedModel(RecommendationModel):
       ...
   
   # 方案C: 机器学习模型
   class MLRecommendationModel(RecommendationModel):
       def __init__(self, model_path):
           self.model = load_pretrained_model(model_path)
       def score(self, fund_data):
           return self.model.predict(fund_data)
   ```

2. **数据收集** (`/scripts/data_collection.py`)
   - 记录用户选择的基金 + 后续收益
   - 为机器学习提供训练数据

3. **动态模型切换**
   ```python
   # 在 RecommendationEngine.__init__ 中
   self.model = MLRecommendationModel() if use_ml else RuleBasedModel()
   ```

## 风险和缓解

| 风险 | 影响 | 缓解方案 |
|------|------|---------|
| 基金数据过多 (5000+) | 逐只分析耗时 | 批量获取基金列表，缓存基础数据 |
| 蛋卷 API 限流 | 推荐慢 | 实现请求队列和退避机制 |
| 评分算法不准 | 推荐质量差 | 验证算法准确性，收集用户反馈迭代 |

## 成功标准

- [ ] 能推荐 Top 10 基金，不出错
- [ ] 推荐耗时 < 2 分钟（包括数据获取和分析）
- [ ] 推荐卡片清晰展示理由
- [ ] 预留方案 C 升级接口清晰文档化
- [ ] 完整的端到端测试通过

## 后续工作

- 上线后收集用户反馈
- 分析推荐命中率和用户实际选择
- 评估方案 C 机器学习推荐的价值
- 如有必要，启动 Phase C 开发

