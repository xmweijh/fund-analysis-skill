---
name: travel-guide
description: 当用户询问"帮我制定旅行攻略"、"create a travel itinerary"、"plan a trip"、"规划路线"、"make travel攻略"或讨论"旅行攻略"、"旅游计划"、"景点推荐"、"travel planning"、"itinerary creation"时使用此技能。自动从小红书收集旅行信息并整合Google Maps数据生成全面的旅行指南。⚠️ 必须为每个景点获取 Google Maps 链接、评分、地址信息、支付方式和地点图片。
version: 1.4.0
---

# 旅行攻略生成器

通过从小红书提取真实的旅行信息并整合Google Maps数据，生成全面的旅行行程。

## 概述

此技能通过以下方式自动创建详细的旅行指南：
- 搜索并提取小红书的旅行笔记
- ⚠️ **从 Google Maps 收集每个景点的详细信息（必需）**
  - Google Maps 链接
  - 评分和评论数
  - 完整地址
  - 营业时间
  - 📸 **地点图片截图（必需）**
- 生成路线地图和地点快照
- 🗺️ **完整路线图截图（必需）**
- 将所有内容编译成结构化的 Markdown 行程

**核心质量保证**：
- ✅ 每个景点都必须有 Google Maps 数据支撑
- ✅ 每个景点都必须有地点图片
- ✅ 每个餐厅/景点都标注了支付方式（刷卡/现金）
- ✅ 用户可以直接点击链接导航
- ✅ 评分数据帮助决策
- ✅ 地址信息确保可到达性
- ✅ 完整路线图方便概览整个行程

**依赖要求**:
- Chrome DevTools MCP 服务器（推荐，用于浏览器自动化）
- 或 Web Search + Web Reader MCP 工具（替代方案）

## 收集旅行参数

首先从用户那里收集基本信息。

### 必需参数
- **目的地** (Destination): 要访问的城市或地区
- **旅行天数** (Duration): 旅行天数

### 可选参数
- **旅行类型** (Trip Type): 美食之旅、文化探索、自然探险等
- **预算范围** (Budget): 总预算估算
- **出行时间** (Travel Time): 旅行计划时间

**示例对话**:
```
用户: "帮我制定一个5天的成都美食之旅"
收集信息: destination=成都, days=5, type=美食之旅
```

## 搜索小红书

从小红书提取真实的旅行体验和推荐。

### 步骤1: 访问小红书
使用 `navigate_page` 访问 xiaohongshu.com 并等待页面加载:
```
navigate_page("https://www.xiaohongshu.com")
wait_for(".search-input", 5000)
```

### 步骤2: 搜索旅行笔记
在搜索框中填入目的地和旅行类型:
```
fill(".search-input", "{destination} {trip_type} 攻略")
press_key("Enter")
wait_for(".note-item", 10000)
```

### 步骤3: 提取笔记内容
使用 `evaluate_script` 从搜索结果中提取结构化数据:
- 标题、作者、内容文本
- 点赞数、收藏数
- 提到的景点、餐厅、酒店
- 旅行提示和实用信息

详细的提取模式，请参考 `references/xiaohongshu-selectors.md`。

### 步骤4: 加载更多结果
向下滚动加载更多笔记:
```
for i in range(3):
    press_key("End")
    wait_for(2000)
```

### 步骤5: 浏览至少10篇笔记 (必需)
**关键**: 你必须浏览并提取至少10篇相关旅行笔记的内容。不要跳过此步骤或匆忙完成。

1. **点击每篇笔记**在搜索结果中
2. **提取完整内容**从每篇笔记中:
   - 完整的旅行行程/路线
   - 所有提到的景点、餐厅、酒店
   - 价格和预算信息
   - 实用提示和警告
   - 营业时间和联系信息
   - 个人经验和推荐

3. **返回并继续**下一篇笔记:
   ```
   navigate_page("back")
   wait for page load
   click next note link
   ```

4. **重复直到浏览了至少10篇笔记**:
   - 重点关注互动量高的笔记（点赞/收藏）
   - 优先选择最近的帖子（最近6个月内）
   - 包含不同视角（美食、文化、预算、奢华）
   - 花时间仔细阅读 - 质量优于速度

5. **追踪你的进度**:
   - 记录浏览的笔记数量
   - 记录提到的独特地点
   - 记录多篇文章中的共同推荐
   - 识别价格范围和预算提示

**重要提示**:
- ⚠️ 在浏览至少10篇笔记之前不要生成行程
- ⚠️ 即使笔记看起来相似也不要跳过 - 每篇都可能有独特见解
- ⚠️ 最终行程的质量取决于充分的研究
- 时间投入: 浏览最少需要10-15分钟

### 步骤6: 处理提取的数据
- 按标题和内容相似性去重笔记
- 按点赞数和收藏数排序
- 提取关键地点（景点、餐厅、酒店）
- 识别共同主题和推荐
- 创建所有提到地点的汇总列表

## 整合Google Maps (必需步骤)

**⚠️ 重要**: 每个景点和餐厅都必须通过 Google Maps MCP 搜索获取详细信息。这是生成高质量攻略的必需步骤，不可跳过。

从Google Maps获取详细信息以丰富提取的地点。

### 对于每个地点 (必须执行)

1. **在Google Maps上搜索**
   ```
   navigate_page("https://www.google.com/maps")
   wait_for(".searchbox", 5000)
   fill(".searchbox", "{location_name}")
   press_key("Enter")
   wait_for(".place-info", 10000)
   ```

2. **提取地点详情 (必需)**
   使用 `evaluate_script` 检索以下所有信息:
   - ✅ 完整地址 (必需)
   - ✅ Google Maps直接链接 (必需)
   - ✅ 评分和评论数 (必需)
   - 营业时间
   - 电话号码
   - 网站URL
   - **💳 支付方式** (是否接受信用卡/借记卡，这是必需信息)

3. **保存地点图片截图 (必需)**
   ```
   take_screenshot("./maps/{location_id}.png", fullPage=False)
   ```

   **截图要求**:
   - ⚠️ 使用Chrome DevTools MCP的`take_screenshot`工具
   - 截图应包含地点的街景视图、地图标记或地点照片
   - 确保截图清晰可见,能识别地点特征
   - 图片将嵌入到最终攻略中
   - 文件命名格式: `{地点名称英文名或拼音}.png`

**重要提示**:
- ⚠️ 每个提到的景点都必须在 Google Maps 上搜索
- ⚠️ 必须提取完整的 Google Maps 链接
- ⚠️ 必须提取评分和评论数
- ⚠️ 这些信息必须出现在最终生成的攻略中

详细的Google Maps工作流程，请参考 `references/google-maps-workflows.md`。

### 使用 MCP 工具的替代方法

如果 Chrome DevTools MCP 服务器不可用，可以使用以下 MCP 工具：

**Web Search + Web Reader 组合**:
1. 使用 `mcp__web-search-prime__webSearchPrime` 搜索地点信息
2. 使用 `mcp__web_reader__webReader` 获取详细地址和评分信息

**示例流程**:
```python
# 搜索景点信息
search_result = mcp__web-search-prime__webSearchPrime(
    search_query="Tan Dinh Church 胡志明市 评分 地址",
    location="cn"
)

# 从搜索结果中提取 Google Maps 链接
maps_link = extract_google_maps_link(search_result)

# 获取详细信息
details = mcp__web_reader__webReader(
    url=maps_link,
    return_format="markdown"
)
```

### 生成路线地图

在多个地点之间创建导航路线:

1. **打开Google Maps并规划路线**
   ```
   navigate_page("https://www.google.com/maps/dir/")
   wait_for(".searchbox", 5000)
   ```

2. **添加所有途经点并优化路线 (必需)**
   - 输入起点位置
   - 点击"添加目的地"
   - **按地理位置顺序依次添加每个景点,而非随意添加**
   - **使用Google Maps的"优化路线"功能 (如可用)**
   - **确保路线最短,避免走回头路**
   - **考虑景点开放时间,合理安排游览顺序**

   **路线优化原则**:
   - ⚠️ **必须按地理位置相近的原则分组景点**
   - ⚠️ **同区域的景点安排在同一天/同一时段**
   - ⚠️ **使用Google Maps查看实际距离,避免绕路**
   - ⚠️ **优先考虑步行可达的路线顺序**
   - ⚠️ **必要时调整景点顺序以减少往返**
   - 检查总距离和预计时间,确保行程合理

3. **捕获完整路线图截图 (必需)**
   ```
   take_screenshot("./routes/complete-route-map.png", fullPage=True)
   ```

   **路线图截图要求**:
   - ⚠️ **必须使用Chrome DevTools MCP的`take_screenshot`工具**
   - 使用`fullPage=True`捕获完整的路线图
   - 确保所有景点标记都在截图中可见
   - 路线应清晰显示游览顺序
   - 包含预计时间信息
   - 此截图将作为攻略的路线概览图

4. **提取路线信息**
   - 总距离
   - 预计游览时间
   - 步行 vs 开车建议

### 查找附近地点

对于每个景点，搜索附近的:
- 餐厅 (美食)
- 酒店 (酒店)
- 交通枢纽 (交通)

提取并在行程中包含顶级推荐。

## 生成Markdown行程

将所有收集的信息编译成结构化的Markdown指南。

### 行程结构

```markdown
# {目的地} {旅行天数}日行程

## 📋 行程概览
- **目的地**: {destination}
- **天数**: {days} 天
- **旅行类型**: {trip_type}
- **预估预算**: {budget}

## 🗓️ 每日行程

### 第1天

#### 上午
**{景点名称}**
- 📍 [在Google Maps上查看]({maps_link})
- 📍 地址: {full_address}
- ⭐ 评分: {rating}/5 ({review_count} 条评论)
- 💳 支付方式: {payment_method} (刷卡/现金)
- 🎫 门票: {ticket_price} (如适用)
- 📸 地点图片:
  ![{景点名称}](./maps/{location_id}.png)
- 💡 推荐: {xiaohongshu_summary}
- 📝 备注: {practical_tips}

#### 下午
**{景点名称}**
- ... (相同结构,包含地点图片)

#### 晚上
**{餐厅名称}**
- 📍 [在Google Maps上查看]({maps_link})
- 📍 地址: {full_address}
- 🍽️ 推荐菜品: {dishes}
- 💰 人均消费: {price}
- ⭐ 评分: {rating}/5 ({review_count} 条评论)
- 💳 支付方式: {payment_method} (刷卡/现金/电子支付)
- 📸 地点图片:
  ![{餐厅名称}](./maps/{restaurant_id}.png)

### 第2天
... (重复结构)

## 🗺️ 完整路线地图
![完整路线图](./routes/complete-route-map.png)

## 💰 预算明细
- **景点门票**: {total_tickets}
- **餐饮**: {total_food}
- **住宿**: {total_hotel}
- **交通**: {total_transport}
- **总计**: {grand_total}

## 📌 实用提示
- {从小红书笔记提取}
- 交通建议
- 最佳游览时间
- 打包建议
- 当地风俗须知

## 📚 参考资料
- **小红书搜索关键词**: {search_terms}
- **来源笔记**: {note_count} 篇社区帖子
- **生成时间**: {date}
```

### 步骤7: 保存到飞书 (必需)
生成Markdown行程后，你必须将其保存到飞书云文档。

**前提条件**:
- 飞书MCP工具必须可用
- 用户应具有适当权限

**保存到飞书的步骤**:

1. **将Markdown导入飞书**:
   ```python
   # 使用 docx_builtin_import 工具
   mcp__mcp-router__docx_builtin_import(
       data={
           "markdown": markdown_content,
           "file_name": "{destination}_{duration}day_itinerary"
       }
   )
   ```

2. **必需参数**:
   - `markdown`: 行程的完整markdown内容
   - `file_name`: 描述性文件名（如"胡志明市一日游citywalk攻略"）
   - 最大文件名长度: 27个字符

3. **处理响应**:
   - 成功: 文档将在用户的飞书中创建
   - 保存文档URL/令牌以供将来参考
   - 通知用户文档位置

4. **最佳实践**:
   - 使用包含目的地和天数的描述性文件名
   - 在文件名中包含emoji以提高可见性（🇻🇳, 🍜等）
   - 保持文件名在27个字符以内
   - 根据用户偏好使用中文或英文

**示例**:
```python
# 生成markdown内容后
response = mcp__mcp-router__docx_builtin_import(
    data={
        "markdown": itinerary_markdown,
        "file_name": "胡志明市一日游citywalk攻略"
    }
)

# 向用户确认
print(f"✅ 攻略已保存到飞书云文档")
print(f"📄 文件名: 胡志明市一日游citywalk攻略")
```

**重要提示**:
- ⚠️ 此步骤是必需的 - 不要跳过
- ⚠️ 在完成任务前务必保存到飞书
- ⚠️ 最大markdown文件大小: 20MB
- ⚠️ 图片可以嵌入但需要单独上传
- 💡 提示: 同时保存本地副本作为备份

不同的旅行类型模板和特殊格式情况，请参考 `references/markdown-templates.md`。

## 数据处理最佳实践

### 处理名称匹配
- 小红书使用中文名称，Google Maps可能显示英文
- 搜索地点时使用模糊匹配
- ⚠️ **必须通过 Google Maps 验证每个地点的准确性**
- 通过交叉引用地址和评分进行验证
- 不确定时，向用户提供多个选项

### 去重逻辑
- 按名称相似性对相似地点进行分组
- 合并来自多篇小红书笔记的信息
- 优先考虑互动量高的地点（点赞/收藏）
- 删除低质量或不相关的条目
- ⚠️ **确保每个地点都有 Google Maps 数据支撑**

### 路线优化算法 (必需)
为了确保整体路程最短,必须应用以下优化策略:

**地理聚类**:
- 将景点按地理位置分组 (例如: 按行政区、街道或区域)
- 同一区域的景点安排在同一时段游览
- 使用Google Maps计算景点之间的实际距离

**最短路径规划**:
- 使用"旅行商问题"(TSP)的近似算法
- 优先访问地理上相邻的景点
- 避免在同一区域往返多次
- 考虑单行道或交通限制

**时间窗口约束**:
- 考虑景点的开放时间
- 高优先级景点安排在黄金时间
- 避免在景点关闭时间到达
- 为交通和游览留出缓冲时间

**优化检查清单**:
- ✅ 路线总距离是否最短?
- ✅ 是否避免了走回头路?
- ✅ 景点之间的衔接是否合理?
- ✅ 步行距离是否在可接受范围内?
- ✅ 是否考虑了交通高峰期?

### 预算估算
- 提取小红书笔记中提到的价格
- 从多个来源计算平均值
- 为意外费用增加10-20%的缓冲
- 以清晰的类别呈现预算

### Google Maps 数据要求 (必需)
- ✅ 每个景点必须有 Google Maps 链接
- ✅ 每个景点必须有评分和评论数
- ✅ 每个景点必须有完整地址
- ✅ 每个景点必须有地点图片
- ✅ **💳 每个餐厅/景点必须标注支付方式（是否可刷卡）**
- ✅ 必须有完整的路线图截图
- ✅ 如果 Google Maps 找不到信息，必须在文档中标注

**支付方式标注说明**：
- 对于餐厅：必须标注是否接受信用卡/借记卡、Alipay、WeChat Pay 等
- 对于景点：必须标注是否可以刷卡购买门票，或是否只收现金
- 如果 Google Maps 没有支付方式信息，需标注"建议备现金"或"支付方式请现场确认"

完整的数据处理模式，请参考 `references/data-extraction-patterns.md`。

## 错误处理

### 常见场景

**小红书需要登录**
- 通知用户可能需要登录
- 考虑现有缓存数据是否足够
- 如需要，使用替代数据源

**Google Maps上找不到地点**
- ⚠️ 这是关键步骤，必须尝试多种方法
- 尝试简化的搜索词
- 如果城市名称多余则删除
- 按景点类别+地标搜索
- 使用中英文混合搜索
- 如果仍然找不到，使用 Web Search + Web Reader 替代方案
- ⚠️ 在最终文档中明确标注"Google Maps 信息未找到"

**无法提取评分或链接**
- 检查网络连接
- 尝试刷新页面重新搜索
- 使用替代的 Google Maps 搜索工具
- 如果持续失败，记录并在文档中说明

**页面加载缓慢**
- 增加wait_for超时值
- 使用take_snapshot验证页面状态
- 如果性能关键，考虑提取较少数据
- 对于 Google Maps，确保等待 .place-info 元素加载完成

**访问频率限制**
- 在搜索之间添加延迟（2-3秒）
- 限制滚动迭代
- 缓存结果以避免重复搜索
- 对于 Google Maps，避免短时间内多次搜索相同地点

## 完整工作流程示例

```
1. 收集参数: destination="成都", days=5, type="美食之旅"

2. 搜索小红书:
   navigate_page("https://www.xiaohongshu.com")
   fill(".search-input", "成都 美食之旅 攻略")
   press_key("Enter")
   wait for search results

3. 浏览至少10篇笔记 (必需):
   For i in range(10):
     click note i
     extract full content
     navigate back
   → Extracted 20 relevant posts (minimum 10)

4. 处理数据:
   Extract 15 restaurants, 8 attractions
   Sort by popularity
   **Group by geographical location (关键步骤)**
   **Cluster nearby attractions together**
   **Plan route to minimize backtracking**

5. 整合Google Maps (必需 - 每个地点都要搜索):
   For each of 23 locations:
     search on maps.google.com (必需步骤)
     extract full address (必需)
     extract Google Maps link (必需)
     extract rating and review count (必需)
     extract opening hours
     **extract payment methods** (是否接受信用卡/电子支付，必需)
     **record coordinates for route optimization**
     save location screenshot using take_screenshot (必需)
     → All locations have Google Maps data, payment info, and images

6. 生成最优路线 (必需 - 路线优化):
   **Group attractions by geographical proximity**
   **Create day-by-day routes minimizing travel distance**
   **Use Google Maps to verify shortest path**
   **Check total walking distance and time**
   **Adjust order if backtracking detected**
   Create complete route map on Google Maps with optimized order
   take_screenshot with fullPage=True (必需)
     → Complete route overview image saved with optimal route

7. 编译Markdown:
     Format into 5-day itinerary
     Add budget estimates
     Include practical tips
     Embed all location images
     Embed complete route map
     Save to local file

8. 保存到飞书 (必需):
     Use docx_builtin_import tool
     Upload markdown content
     File name: "成都5日美食攻略"
     ✅ Confirm saved to Feishu
     ✅ Inform user of document location
```

## 附加资源

### 参考文件
详细的实施指导:

- **`references/xiaohongshu-selectors.md`** - 完整的DOM选择器、JavaScript提取模式和处理小红书的动态内容加载
- **`references/google-maps-workflows.md`** - Google Maps导航、地点数据提取、路线生成和截图捕获方法
- **`references/data-extraction-patterns.md`** - 数据清理、去重、模糊名称匹配和预算计算算法
- **`references/markdown-templates.md`** - 不同旅行类型的详细模板（美食、文化、自然）、特殊格式和丰富内容嵌入

### 示例文件
生成的行程示例:
- **`examples/tokyo-itinerary.md`** - 完整的东京5日行程，包含Google Maps集成
- **`examples/sichuan-food-tour.md`** - 四川美食之旅示例，突出餐厅发现

### 脚本
自动化实用脚本:
- **`scripts/extract-xiaohongshu.js`** - 通过evaluate_script提取小红书笔记数据的JavaScript
- **`scripts/format-itinerary.py`** - 用于格式化和美化Markdown输出的Python脚本

验证:
- 技能对旅行相关查询的触发
- 成功导航xiaohongshu.com和maps.google.com
- ⚠️ **浏览至少10篇笔记** - 不要跳过此验证
- 从多个来源提取相关旅行信息
- 生成包含所有部分的格式良好的Markdown
- ⚠️ **每个景点都有 Google Maps 链接和评分** - 不要跳过此验证
- 提供实用的预算估算
- ⚠️ **保存到飞书** - 确认文档已上传
- 向用户提供飞书文档位置

**关键检查**:
- ✅ 至少浏览并提取了10篇笔记
- ✅ 每个景点都有完整的 Google Maps 信息
- ✅ 每个景点都有 Google Maps 链接
- ✅ 每个景点都有评分和评论数
- ✅ **每个餐厅/景点都标注了支付方式（刷卡/现金）**
- ✅ **每个景点都有地点图片截图**
- ✅ **有完整的路线图截图**
- ✅ 文档成功保存到飞书
- ✅ 用户可以访问飞书文档
- ✅ 本地和云端副本都存在

---

## ⚠️ 重要提醒：Google Maps 数据是必需的

为了确保生成的旅行攻略高质量且实用，**必须**为每个景点和餐厅收集 Google Maps 数据：

### 为什么需要 Google Maps 数据？
1. **准确性验证**：确认地点真实存在且可访问
2. **用户体验**：用户可以直接点击链接查看详情和导航
3. **评分参考**：评分和评论数帮助用户判断是否值得前往
4. **地址准确**：避免因地址错误导致的迷路

### 最低要求
对于攻略中的每个地点，必须包含：
- ✅ Google Maps 链接（可点击跳转）
- ✅ 评分（例如：4.5/5）
- ✅ 评论数（例如：1,234 条评论）
- ✅ 完整地址（包含街道、城市、国家）
- ✅ **💳 支付方式**（是否可刷卡、电子支付等）
- ✅ 📸 **地点图片**
- ✅ 🗺️ **完整路线图截图**

### 如果某个地点找不到 Google Maps 信息
1. 尝试使用不同的搜索关键词（中英文、别名等）
2. 使用 Web Search + Web Reader 作为替代方案
3. 如果仍然找不到，在文档中明确标注：
   ```
   ⚠️ 注意：该地点未能在 Google Maps 上找到详细信息，建议在当地核实
   ```

### 质量标准
一个高质量的旅行攻略应该：
- 📍 90% 以上的景点有完整的 Google Maps 信息
- 🔗 所有 Google Maps 链接均可点击访问
- ⭐ 评分数据真实有效（非虚构）
- 📮 地址信息准确完整（可导航）
- 💳 **支付方式信息明确**（标注是否可刷卡、电子支付等）
- 📸 **每个景点都有清晰的地点图片**
- 🗺️ **有完整的路线图概览，包含所有景点标记**
- 🖼️ **图片质量清晰，能够识别地点特征**
- 🎯 **路线经过优化,总路程最短,避免走回头路**
- 📏 **提供总距离和预计游览时间**
- 🚶 **步行路线合理,避免过度疲劳**

**支付方式质量标准**：
- ✅ 餐厅：明确标注是否接受信用卡、借记卡、Alipay、WeChat Pay
- ✅ 景点：标注门票购买方式（现金/刷卡/在线预订）
- ✅ 小店/摊贩：标注"仅收现金"（如适用）
- ✅ 如果支付方式不确定，标注"建议备现金"

**路线优化验证**:
- ✅ 使用Google Maps验证实际路线距离
- ✅ 检查是否有明显的绕路或回头路
- ✅ 同区域景点安排在一起
- ✅ 考虑了景点开放时间和游览时间
- ✅ 提供了交通方式和时间估算

**记住：跳过 Google Maps 搜索或截图步骤会严重降低攻略质量和实用性！未优化的路线会浪费游客大量时间和精力！**
