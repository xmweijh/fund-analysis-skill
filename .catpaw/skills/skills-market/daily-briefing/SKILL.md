---
name: daily-briefing
description: 每日早报推送 — 聚合股市行情、AI前沿资讯、GitHub开源趋势三大板块，生成结构化 Markdown 报告。适用于定时任务（cron）或手动触发。当用户提到：每日早报、每日推送、今日资讯、AI新闻、GitHub趋势、股市行情汇总、morning briefing 时激活。
---

# 每日早报 (Daily Briefing)

聚合三大板块信息，生成一份精炼的每日早报：
1. **📊 股市行情** — 港股/A股主要指数及个股实时数据（腾讯财经接口）
2. **🤖 AI 前沿动态** — HackerNews AI 相关热帖 Top 5
3. **🔥 GitHub 今日趋势** — GitHub Trending Top 5 项目

## 快速使用

### 全量早报
```bash
bash <skill_dir>/scripts/fetch_briefing.sh
```

### 单板块
```bash
bash <skill_dir>/scripts/fetch_briefing.sh --section stock
bash <skill_dir>/scripts/fetch_briefing.sh --section ai
bash <skill_dir>/scripts/fetch_briefing.sh --section github
```

### 自定义股票标的
```bash
bash <skill_dir>/scripts/fetch_briefing.sh --stock-symbols "r_hk03690,sh000001,r_hk00700,r_hkHSI,sh600519"
```

股票代码格式：港股 `r_hkXXXXX`，沪市 `shXXXXXX`，深市 `szXXXXXX`。

## 数据源

| 板块 | 来源 | 接口 |
|------|------|------|
| 股市行情 | 腾讯财经 | `https://qt.gtimg.cn/q=<symbols>` |
| AI 资讯 | HackerNews API | `https://hacker-news.firebaseio.com/v0/topstories.json` |
| GitHub 趋势 | GitHub Trending | `https://github.com/trending?since=daily` |

## 配合 Cron 定时推送

在 OpenClaw 中创建 cron 任务，每日定时执行并通过 agent 润色后发送到大象/Telegram 等渠道：

```
schedule: 0 10 * * 1-5 (工作日 10:00)
message: 执行 daily-briefing skill，运行 fetch_briefing.sh 获取数据，对结果做简要点评和摘要润色，然后以文本形式回复。
delivery: announce → daxiang
```

## Agent 整合建议

脚本输出为原始 Markdown。Agent 收到后应：
1. 检查是否有板块数据获取失败（⚠️ 标记），失败时用 web_search / catclaw-search 补充
2. 对 AI 资讯和 GitHub 项目做一句话中文点评
3. 根据目标平台调整格式（大象支持表格，Discord/WhatsApp 用列表）
4. 控制总长度在一屏以内

## 依赖

- curl, python3（系统内置即可）
- 无需额外 npm/pip 包
