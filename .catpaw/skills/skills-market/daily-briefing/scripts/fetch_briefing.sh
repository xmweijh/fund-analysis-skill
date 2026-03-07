#!/usr/bin/env bash
# fetch_briefing.sh — 每日早报数据采集脚本
# 用法: bash fetch_briefing.sh [--section stock|ai|github|all] [--stock-symbols SYMBOLS]

set -euo pipefail

SECTION_VAL="all"
STOCK_SYMBOLS="r_hk03690,sh000001,sz399001,sz399006,r_hk00700,r_hkHSI"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --section) SECTION_VAL="$2"; shift 2 ;;
    --stock-symbols) STOCK_SYMBOLS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ====== 股市行情 ======
fetch_stock() {
  echo "## 📊 股市行情"
  echo ""
  local url="https://qt.gtimg.cn/q=${STOCK_SYMBOLS}"
  local raw
  raw=$(curl -sL --max-time 10 "$url" 2>/dev/null || echo "")
  if [[ -z "$raw" ]]; then
    echo "⚠️ 股市数据获取失败"
    echo ""
    return
  fi

  echo "$raw" | python3 -c "
import sys

lines = sys.stdin.read().strip().split(';')
print('| 标的 | 当前价 | 涨跌额 | 涨跌幅 | 趋势 |')
print('|------|--------|--------|--------|------|')

for line in lines:
    line = line.strip()
    if not line or '=' not in line:
        continue
    parts = line.split('~')
    if len(parts) < 33:
        continue
    name = parts[1]
    current = parts[3]
    change = parts[31] if len(parts) > 31 else ''
    change_pct = parts[32] if len(parts) > 32 else ''
    try:
        pct_val = float(change_pct)
        emoji = '📈' if pct_val > 0 else ('📉' if pct_val < 0 else '➖')
        sign = '+' if pct_val > 0 else ''
        print(f'| {name} | {current} | {sign}{change} | {sign}{change_pct}% | {emoji} |')
    except:
        print(f'| {name} | {current} | {change} | {change_pct}% | ➖ |')
" 2>/dev/null || echo "⚠️ 股市数据解析失败"
  echo ""
}

# ====== AI 前沿动态 ======
fetch_ai_news() {
  echo "## 🤖 AI 前沿动态"
  echo ""
  local hn_ids
  hn_ids=$(curl -sL --max-time 10 "https://hacker-news.firebaseio.com/v0/topstories.json" 2>/dev/null \
    | python3 -c "import json,sys; ids=json.load(sys.stdin)[:30]; print(' '.join(str(i) for i in ids))" 2>/dev/null || echo "")

  if [[ -z "$hn_ids" ]]; then
    echo "⚠️ HackerNews 数据获取失败"
    echo ""
    return
  fi

  local count=0
  for id in $hn_ids; do
    [[ $count -ge 5 ]] && break
    local item
    item=$(curl -sL --max-time 5 "https://hacker-news.firebaseio.com/v0/item/${id}.json" 2>/dev/null || echo "{}")
    local title url score
    title=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('title',''))" 2>/dev/null || echo "")
    url=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('url', f'https://news.ycombinator.com/item?id={d.get(\"id\",\"\")}'))" 2>/dev/null || echo "")
    score=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('score',0))" 2>/dev/null || echo "0")

    if [[ -n "$title" ]]; then
      local is_ai
      is_ai=$(echo "$title" | grep -iE "AI|LLM|GPT|Claude|Gemini|OpenAI|Anthropic|DeepSeek|model|neural|machine.learn|deep.learn|transformer|agent|diffusion|Llama|Mistral|token|reasoning|AGI|copilot|Qwen|Grok" || true)
      if [[ -n "$is_ai" ]] || [[ "$score" -gt 300 ]]; then
        count=$((count + 1))
        echo "${count}. **${title}** (🔥${score})"
        echo "   ${url}"
        echo ""
      fi
    fi
  done

  if [[ $count -eq 0 ]]; then
    echo "今日 HackerNews 暂无突出 AI 热帖，以下为综合热门："
    echo ""
    count=0
    for id in $hn_ids; do
      [[ $count -ge 5 ]] && break
      local item
      item=$(curl -sL --max-time 5 "https://hacker-news.firebaseio.com/v0/item/${id}.json" 2>/dev/null || echo "{}")
      local title url score
      title=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('title',''))" 2>/dev/null || echo "")
      url=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('url', f'https://news.ycombinator.com/item?id={d.get(\"id\",\"\")}'))" 2>/dev/null || echo "")
      score=$(echo "$item" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('score',0))" 2>/dev/null || echo "0")
      if [[ -n "$title" ]]; then
        count=$((count + 1))
        echo "${count}. **${title}** (🔥${score})"
        echo "   ${url}"
        echo ""
      fi
    done
  fi
}

# ====== GitHub 趋势项目 ======
fetch_github_trending() {
  echo "## 🔥 GitHub 今日趋势"
  echo ""

  local html
  html=$(curl -sL --max-time 15 "https://github.com/trending?since=daily" 2>/dev/null || echo "")

  if [[ -z "$html" ]]; then
    echo "⚠️ GitHub Trending 数据获取失败"
    echo ""
    return
  fi

  echo "$html" | python3 -c "
import sys, re, html as h, urllib.parse

content = sys.stdin.read()
repos = re.findall(r'<article class=\"Box-row\">(.*?)</article>', content, re.DOTALL)

count = 0
for repo in repos[:5]:
    count += 1
    # Extract repo link
    name_m = re.search(r'href=\"(/[^\"]+)\"', repo)
    name = name_m.group(1).strip('/') if name_m else 'unknown'
    # Fix login redirect URLs (GitHub returns these when not logged in)
    if 'return_to=' in name:
        m2 = re.search(r'return_to=([^&\"]+)', name)
        if m2:
            name = urllib.parse.unquote(m2.group(1)).strip('/')

    desc_m = re.search(r'<p class=\"col-9[^\"]*\"[^>]*>(.*?)</p>', repo, re.DOTALL)
    desc = h.unescape(desc_m.group(1).strip()) if desc_m else '暂无描述'

    lang_m = re.search(r'itemprop=\"programmingLanguage\">(.*?)<', repo)
    lang = lang_m.group(1).strip() if lang_m else '-'

    stars_today_m = re.search(r'([\d,]+)\s+stars today', repo)
    stars_today = stars_today_m.group(1) if stars_today_m else '-'

    total_m = re.findall(r'href=\"/[^\"]+/stargazers\"[^>]*>\s*([\d,]+)\s*<', repo)
    if not total_m:
        # Fallback: find star counts in spans
        total_m = re.findall(r'>\s*([\d,]+)\s*<', repo)
    total_stars = total_m[0] if total_m else '-'

    print(f'{count}. **[{name}](https://github.com/{name})** ⭐{total_stars} (+{stars_today} today)')
    print(f'   {lang} | {desc}')
    print()
" 2>/dev/null || echo "⚠️ GitHub Trending 数据解析失败"
}

# ====== 主流程 ======
echo "# ☀️ 每日早报 — $(date '+%Y-%m-%d %A')"
echo ""

case "$SECTION_VAL" in
  stock)   fetch_stock ;;
  ai)      fetch_ai_news ;;
  github)  fetch_github_trending ;;
  all)
    fetch_stock
    fetch_ai_news
    fetch_github_trending
    ;;
  *) echo "未知板块: $SECTION_VAL (可选: stock, ai, github, all)" ;;
esac

echo "---"
echo "_数据采集时间: $(date '+%H:%M:%S')_"
