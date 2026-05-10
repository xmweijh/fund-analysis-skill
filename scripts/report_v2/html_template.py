"""
HTML报告模板模块
通过 AJAX 加载同目录下的 JSON 数据并渲染完整的交互式报告
"""

import os
import json


class HTMLTemplate:
    """
    生成包含 Chart.js 雷达图、可折叠面板和汇总卡片的 HTML 报告。

    用法::

        html = HTMLTemplate.render("report_data.json")
        with open("report.html", "w") as f:
            f.write(html)
    """

    # ── 内联 CSS 路径标记（生成时可替换为实际内容）──────────────────────

    @classmethod
    def _load_css(cls) -> str:
        """尝试读取 static/style.css；不存在则返回空字符串。"""
        css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ── 主渲染入口 ──────────────────────────────────────────────────────

    @classmethod
    def render(cls, json_path: str) -> str:
        """
        生成完整的 HTML 报告字符串。

        参数
        ----
        json_path : str
            JSON 数据文件路径（可以是绝对路径或相对路径）。
            HTML 中的 AJAX 请求将使用该文件的 basename，
            因此 HTML 文件和 JSON 文件需放在同一目录下。

        返回
        ----
        str
            完整的 HTML 文档字符串。
        """
        json_basename = os.path.basename(json_path)
        css_content = cls._load_css()

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>基金分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
{css_content}
</style>
</head>
<body>
<div class="container">

  <!-- 加载提示 -->
  <div id="loading">正在加载报告数据…</div>
  <div id="error-msg"></div>

  <!-- 报告主体（数据加载后填充） -->
  <div id="report" style="display:none;"></div>

</div>

<script>
// ─────────────────────────────────────────────────────────────────────────────
//  工具函数
// ─────────────────────────────────────────────────────────────────────────────

/** 安全转义 HTML */
function esc(str) {{
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

/** 保留两位小数，不足则显示 '-' */
function fmt2(v) {{
  return (v !== null && v !== undefined) ? Number(v).toFixed(2) : '–';
}}

/** 带正负号的两位小数 */
function fmtSign(v) {{
  if (v === null || v === undefined) return '–';
  const n = Number(v);
  return (n >= 0 ? '+' : '') + n.toFixed(2);
}}

/** 根据数值（分数）返回颜色类 */
function scoreClass(v) {{
  if (v === null || v === undefined) return 'neutral';
  const n = Number(v);
  if (n >= 65) return 'score-high';
  if (n >= 40) return 'score-medium';
  return 'score-low';
}}

/** 根据估值状态文本返回 badge 类 */
function valuationBadgeClass(status) {{
  const s = (status || '').trim();
  if (s.includes('低估')) return 'badge-green';
  if (s.includes('高估')) return 'badge-red';
  if (s.includes('合理')) return 'badge-yellow';
  return 'badge-gray';
}}

/** 根据操作建议返回 card 颜色类 */
function actionCardClass(action) {{
  const a = (action || '').trim();
  if (['买入','加仓','建仓'].includes(a)) return 'action-buy';
  if (['定投'].includes(a)) return 'action-sip';
  if (['持有'].includes(a)) return 'action-hold';
  if (['减仓','卖出','清仓'].includes(a)) return 'action-sell';
  return 'action-watch';
}}

// ─────────────────────────────────────────────────────────────────────────────
//  面板折叠功能
// ─────────────────────────────────────────────────────────────────────────────

function initPanels() {{
  document.querySelectorAll('.panel-header').forEach(function(header) {{
    header.addEventListener('click', function() {{
      header.classList.toggle('open');
      const body = header.nextElementSibling;
      if (body && body.classList.contains('panel-body')) {{
        body.classList.toggle('open');
      }}
    }});
  }});
}}

// ─────────────────────────────────────────────────────────────────────────────
//  雷达图
// ─────────────────────────────────────────────────────────────────────────────

function renderRadarChart(scores) {{
  const canvas = document.getElementById('radarChart');
  if (!canvas || !scores) return;

  const labels = ['技术面', '基本面', '估值面', '资金面', '情绪面'];
  const values = [
    scores.technical   || 0,
    scores.fundamental || 0,
    scores.valuation   || 0,
    scores.capital_flow || 0,
    scores.sentiment   || 0,
  ];

  new Chart(canvas, {{
    type: 'radar',
    data: {{
      labels: labels,
      datasets: [{{
        label: '五维评分',
        data: values,
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        borderColor: 'rgba(99, 102, 241, 0.9)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
        pointRadius: 4,
      }}],
    }},
    options: {{
      responsive: true,
      scales: {{
        r: {{
          min: 0,
          max: 100,
          ticks: {{
            stepSize: 20,
            font: {{ size: 10 }},
          }},
          pointLabels: {{
            font: {{ size: 12, weight: '600' }},
            color: '#1a1a2e',
          }},
          grid: {{ color: 'rgba(0,0,0,0.06)' }},
        }},
      }},
      plugins: {{
        legend: {{ display: false }},
      }},
    }},
  }});
}}

// ─────────────────────────────────────────────────────────────────────────────
//  摘要卡片
// ─────────────────────────────────────────────────────────────────────────────

function buildSummaryCards(d) {{
  const scores = d.scores || {{}};
  const position = d.position_advice || {{}};
  const action = position.action || d.action || '–';
  const totalScore = scores.total;
  const valuationStatus = (d.valuation || {{}}).status || '–';

  // 目标仓位
  const targetPct  = position.target_pct !== undefined ? fmt2(position.target_pct) + '%' : '–';
  // 当前仓位
  const currentPct = position.current_pct !== undefined ? fmt2(position.current_pct) + '%' : '–';

  const cards = [
    {{
      label: '综合评分',
      value: totalScore !== undefined ? Number(totalScore).toFixed(1) : '–',
      sub: '满分 100 分',
      cls: 'card ' + scoreClass(totalScore),
    }},
    {{
      label: '估值状态',
      value: esc(valuationStatus),
      sub: d.valuation ? ('PE: ' + fmt2(d.valuation.pe_ttm) + ' / PB: ' + fmt2(d.valuation.pb)) : '',
      cls: 'card ' + (valuationStatus.includes('低估') ? 'action-buy' : valuationStatus.includes('高估') ? 'action-sell' : 'neutral'),
    }},
    {{
      label: '操作建议',
      value: esc(action),
      sub: esc(d.conclusion || ''),
      cls: 'card ' + actionCardClass(action),
    }},
    {{
      label: '目标仓位',
      value: targetPct,
      sub: '当前: ' + currentPct,
      cls: 'card neutral',
    }},
  ];

  return '<div class="summary-grid">' +
    cards.map(function(c) {{
      return '<div class="' + c.cls + '">' +
        '<div class="card-label">' + c.label + '</div>' +
        '<div class="card-value">' + c.value + '</div>' +
        (c.sub ? '<div class="card-sub">' + c.sub + '</div>' : '') +
        '</div>';
    }}).join('') +
    '</div>';
}}

// ─────────────────────────────────────────────────────────────────────────────
//  各面板 HTML 构建函数
// ─────────────────────────────────────────────────────────────────────────────

/** 雷达图面板 */
function buildRadarPanel(scores) {{
  if (!scores) return '';
  return '<div class="chart-section">' +
    '<h2>五维评分雷达图</h2>' +
    '<div class="chart-wrapper"><canvas id="radarChart"></canvas></div>' +
    '</div>';
}}

/** 技术分析面板 */
function buildTechnicalPanel(tech) {{
  if (!tech) return '';

  // MA 均线
  const maRows = [
    ['MA5',  tech.ma5],
    ['MA10', tech.ma10],
    ['MA20', tech.ma20],
    ['MA60', tech.ma60],
    ['MA250 (年线)', tech.ma250],
  ].filter(function(r) {{ return r[1] !== null && r[1] !== undefined; }})
   .map(function(r) {{
     return '<tr><td>' + esc(r[0]) + '</td><td>' + fmt2(r[1]) + '</td></tr>';
   }}).join('');

  // MACD
  const macd = tech.macd || {{}};
  const macdHtml = (macd.dif !== undefined)
    ? '<p style="margin-top:12px;"><strong>MACD</strong>：' +
      'DIF=' + fmt2(macd.dif) + '，DEA=' + fmt2(macd.dea) + '，BAR=' + fmt2(macd.bar) +
      '，信号：<span class="badge ' + (macd.signal === '金叉' ? 'badge-green' : 'badge-red') + '">' + esc(macd.signal) + '</span></p>'
    : '';

  // RSI
  const rsi = tech.rsi || {{}};
  const rsiHtml = (rsi.rsi_6 !== undefined)
    ? '<p style="margin-top:8px;"><strong>RSI</strong>：' +
      'RSI6=' + fmt2(rsi.rsi_6) + '，RSI12=' + fmt2(rsi.rsi_12) + '，RSI24=' + fmt2(rsi.rsi_24) +
      '，状态：<span class="badge badge-blue">' + esc(rsi.status) + '</span></p>'
    : '';

  // 乖离率
  const biasHtml = (tech.bias_ma5 !== undefined || tech.bias_ma20 !== undefined)
    ? '<p style="margin-top:8px;"><strong>乖离率</strong>：' +
      (tech.bias_ma5  !== undefined ? 'MA5=' + fmtSign(tech.bias_ma5) + '%  ' : '') +
      (tech.bias_ma20 !== undefined ? 'MA20=' + fmtSign(tech.bias_ma20) + '%  ' : '') +
      (tech.bias_ma250 !== undefined ? '年线=' + fmtSign(tech.bias_ma250) + '%' : '') +
      '</p>'
    : '';

  // 信号列表
  const signals = (tech.signals || []).map(function(s) {{
    return '<span class="signal-pill">' + esc(s) + '</span>';
  }}).join('');

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">技术面分析</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    '<table class="data-table"><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>' +
    maRows +
    '<tr><td>趋势</td><td>' + esc(tech.trend) + '</td></tr>' +
    '<tr><td>形态</td><td>' + esc(tech.formation) + '</td></tr>' +
    '</tbody></table>' +
    macdHtml + rsiHtml + biasHtml +
    (signals ? '<div class="signal-list" style="margin-top:12px;">' + signals + '</div>' : '') +
    '</div></div>';
}}

/** 仓位管理面板 */
function buildPositionPanel(pos) {{
  if (!pos) return '';

  const deviation = Number(pos.deviation_pct || 0);
  const currentPct = Number(pos.current_pct || 0);
  const targetPct  = Number(pos.target_pct  || 0);
  const maxPct     = Number(pos.max_pct || 100);

  // 进度条颜色
  const barColor = Math.abs(deviation) > 10 ? 'red' : (Math.abs(deviation) > 5 ? 'yellow' : 'green');
  const barWidth = Math.min(100, (currentPct / Math.max(maxPct, 1)) * 100).toFixed(1);

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">仓位管理</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    '<div class="kv-list">' +
    '<span class="kv-key">当前仓位</span><span class="kv-val">' + fmt2(pos.current_pct) + '%</span>' +
    '<span class="kv-key">目标仓位</span><span class="kv-val">' + fmt2(pos.target_pct) + '%</span>' +
    '<span class="kv-key">最低线</span><span class="kv-val">' + fmt2(pos.min_pct) + '%</span>' +
    '<span class="kv-key">最高线</span><span class="kv-val">' + fmt2(pos.max_pct) + '%</span>' +
    '<span class="kv-key">偏离度</span><span class="kv-val ' + (deviation > 0 ? 'val-high' : deviation < 0 ? 'val-low' : '') + '">' + fmtSign(deviation) + '%</span>' +
    '<span class="kv-key">操作建议</span><span class="kv-val"><strong>' + esc(pos.action) + '</strong></span>' +
    '<span class="kv-key">紧急程度</span><span class="kv-val">' + esc(pos.urgency) + '</span>' +
    (pos.reason ? '<span class="kv-key">理由</span><span class="kv-val">' + esc(pos.reason) + '</span>' : '') +
    '</div>' +
    '<div class="position-bar-wrap">' +
    '<div class="position-bar-track">' +
    '<div class="position-bar-fill ' + barColor + '" style="width:' + barWidth + '%"></div>' +
    '</div>' +
    '<div class="position-bar-markers"><span>' + fmt2(pos.min_pct) + '%</span><span>目标 ' + fmt2(pos.target_pct) + '%</span><span>' + fmt2(pos.max_pct) + '%</span></div>' +
    '</div>' +
    '</div></div>';
}}

/** 定投面板 */
function buildSIPPanel(sip) {{
  if (!sip) return '';

  const takeProfitRows = (sip.take_profit_plans || []).map(function(tp) {{
    return '<tr><td>' + esc(tp.profit_level || tp.level || '') + '</td><td>' + esc(tp.description || '') + '</td></tr>';
  }}).join('');

  const reasons = (sip.reasons || []).map(function(r) {{
    return '<li>' + esc(r) + '</li>';
  }}).join('');

  const risks = (sip.risks || []).map(function(r) {{
    return '<li>' + esc(r) + '</li>';
  }}).join('');

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">定投建议</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    (sip.recommended_amount !== undefined && sip.recommended_amount !== null
      ? '<div class="sip-highlight">' +
        '<div class="sip-label">建议定投金额</div>' +
        '<div class="sip-amount">¥' + Number(sip.recommended_amount).toLocaleString('zh-CN', {{minimumFractionDigits:0}}) + '</div>' +
        '<div style="font-size:12px;color:#3b82f6;margin-top:4px;">基础金额 ¥' + (sip.base_amount || '–') + ' × ' + fmt2(sip.multiplier) + ' 倍</div>' +
        '</div>'
      : '') +
    '<div class="kv-list">' +
    '<span class="kv-key">策略</span><span class="kv-val">' + esc(sip.strategy) + '</span>' +
    '<span class="kv-key">信号</span><span class="kv-val"><strong>' + esc(sip.signal) + '</strong></span>' +
    '<span class="kv-key">信心度</span><span class="kv-val">' + (sip.confidence || '–') + ' / 100</span>' +
    '</div>' +
    (reasons ? '<p style="margin-top:12px;font-weight:600;font-size:13px;">建议理由</p><ul style="padding-left:18px;margin-top:6px;font-size:13px;">' + reasons + '</ul>' : '') +
    (risks ? '<p style="margin-top:12px;font-weight:600;font-size:13px;color:#dc2626;">风险提示</p><ul style="padding-left:18px;margin-top:6px;font-size:13px;color:#6b7280;">' + risks + '</ul>' : '') +
    (takeProfitRows
      ? '<p style="margin-top:12px;font-weight:600;font-size:13px;">止盈计划</p>' +
        '<table class="data-table" style="margin-top:8px;"><thead><tr><th>触发条件</th><th>操作</th></tr></thead><tbody>' + takeProfitRows + '</tbody></table>'
      : '') +
    '</div></div>';
}}



/** 基金经理面板 */
function buildManagerPanel(mgr) {{
  if (!mgr) return '';

  const tags = (mgr.tags || []).map(function(t) {{
    return '<span class="signal-pill">' + esc(t) + '</span>';
  }}).join('');

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">基金经理</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    '<div class="kv-list">' +
    '<span class="kv-key">姓名</span><span class="kv-val">' + esc(mgr.manager_name || '–') + '</span>' +
    '<span class="kv-key">从业年限</span><span class="kv-val">' + (mgr.experience_years || '–') + ' 年</span>' +
    '<span class="kv-key">管理本基金</span><span class="kv-val">' + (mgr.manage_years || '–') + ' 年</span>' +
    '<span class="kv-key">平均年化</span><span class="kv-val">' + (mgr.avg_return !== undefined ? fmt2(mgr.avg_return) + '%' : '–') + '</span>' +
    '<span class="kv-key">综合评分</span><span class="kv-val ' + scoreClass(mgr.score) + '>' + (mgr.score !== undefined ? Number(mgr.score).toFixed(1) : '–') + '</span>' +
    '<span class="kv-key">评价</span><span class="kv-val">' + esc(mgr.assessment || '–') + '</span>' +
    '</div>' +
    (tags ? '<div class="signal-list" style="margin-top:12px;">' + tags + '</div>' : '') +
    '</div></div>';
}}

/** 年度业绩面板 */
function buildYearlyPerformancePanel(perf) {{
  if (!perf || !perf.yearly_performance || perf.yearly_performance.length === 0) return '';

  const rows = perf.yearly_performance.map(function(y) {{
    const ret = y.return_pct;
    const bench = y.benchmark_return;
    const excess = y.excess_return;
    const rank = y.rank_percentile;

    let retClass = 'neutral';
    if (ret > 10) retClass = 'positive';
    else if (ret < -10) retClass = 'negative';

    return '<tr>' +
      '<td>' + esc(y.year) + '</td>' +
      '<td class="' + retClass + '">' + (ret !== undefined ? fmtSign(ret) + '%' : '–') + '</td>' +
      '<td>' + (bench !== undefined ? fmtSign(bench) + '%' : '–') + '</td>' +
      '<td class="' + (excess > 0 ? 'positive' : excess < 0 ? 'negative' : '') + '">' + (excess !== undefined ? fmtSign(excess) + '%' : '–') + '</td>' +
      '<td>' + (rank !== undefined ? fmt2(rank) + '%' : '–') + '</td>' +
      '</tr>';
  }}).join('');

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">历年业绩</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    '<table class="data-table"><thead><tr><th>年份</th><th>基金收益</th><th>基准收益</th><th>超额收益</th><th>同类排名</th></tr></thead><tbody>' + rows + '</tbody></table>' +
    '</div></div>';
}}


/** 估值面板 */
function buildValuationPanel(val) {{
  if (!val) return '';

  const statusBadge = '<span class="badge ' + valuationBadgeClass(val.status) + '">' + esc(val.status) + '</span>';

  return '<div class="panel">' +
    '<div class="panel-header"><span class="panel-title">估值分析</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body">' +
    '<div class="kv-list">' +
    (val.pe_ttm !== undefined && val.pe_ttm !== null ? '<span class="kv-key">PE-TTM</span><span class="kv-val">' + fmt2(val.pe_ttm) + '</span>' : '') +
    (val.pb     !== undefined && val.pb     !== null ? '<span class="kv-key">PB</span><span class="kv-val">' + fmt2(val.pb) + '</span>' : '') +
    (val.pe_percentile !== undefined && val.pe_percentile !== null ? '<span class="kv-key">PE 历史百分位</span><span class="kv-val">' + fmt2(val.pe_percentile) + '%</span>' : '') +
    (val.pb_percentile !== undefined && val.pb_percentile !== null ? '<span class="kv-key">PB 历史百分位</span><span class="kv-val">' + fmt2(val.pb_percentile) + '%</span>' : '') +
    (val.risk_premium  !== undefined && val.risk_premium  !== null ? '<span class="kv-key">风险溢价</span><span class="kv-val">' + fmt2(val.risk_premium) + '%</span>' : '') +
    '<span class="kv-key">估值状态</span><span class="kv-val">' + statusBadge + '</span>' +
    (val.update_date ? '<span class="kv-key">更新日期</span><span class="kv-val">' + esc(val.update_date) + '</span>' : '') +
    '</div>' +
    '</div></div>';
}}

/** 五维评分面板 */
function buildScoresPanel(scores) {{
  if (!scores) return '';

  const dims = [
    ['技术面', scores.technical],
    ['基本面', scores.fundamental],
    ['估值面', scores.valuation],
    ['资金面', scores.capital_flow],
    ['情绪面', scores.sentiment],
    ['综合总分', scores.total],
  ];

  const rows = dims.map(function(d) {{
    const v = d[1];
    const cls = scoreClass(v);
    return '<tr><td>' + esc(d[0]) + '</td>' +
      '<td class="' + cls + '" style="font-weight:600;">' + (v !== undefined && v !== null ? Number(v).toFixed(1) : '–') + '</td>' +
      '</tr>';
  }}).join('');

  return '<div class="panel">' +
    '<div class="panel-header open"><span class="panel-title">五维评分明细</span><span class="panel-icon">▼</span></div>' +
    '<div class="panel-body open">' +
    '<table class="data-table"><thead><tr><th>维度</th><th>得分</th></tr></thead><tbody>' + rows + '</tbody></table>' +
    '</div></div>';
}}

// ─────────────────────────────────────────────────────────────────────────────
//  主渲染函数
// ─────────────────────────────────────────────────────────────────────────────

function render(d) {{
  // 标题区
  const fundName = esc(d.fund_name || ('基金 ' + (d.fund_code || '')));
  const fundCode = esc(d.fund_code || '');
  const genTime  = esc(d.generated_at || new Date().toLocaleString('zh-CN'));

  let html = '';

  // Header
  html += '<div class="report-header">' +
    '<h1>' + fundName + (fundCode ? '（' + fundCode + '）' : '') + ' 基金分析报告</h1>' +
    '<div class="subtitle">报告生成时间：' + genTime + '</div>' +
    '</div>';

  // 摘要卡片
  html += buildSummaryCards(d);

  // 雷达图（放在卡片下方）
  html += buildRadarPanel(d.scores);

  // 五维评分明细
  html += buildScoresPanel(d.scores);

  // 历年业绩
  html += buildYearlyPerformancePanel(d.performance);

  // 基金经理
  html += buildManagerPanel(d.manager);

  // 技术面
  html += buildTechnicalPanel(d.technical);

  // 估值
  html += buildValuationPanel(d.valuation);

  // 仓位管理
  html += buildPositionPanel(d.position_advice);

  // 定投
  if (d.sip_enabled && d.sip_advice) {{
    html += buildSIPPanel(d.sip_advice);
  }}

  // 免责声明
  html += '<div class="disclaimer">' +
    '<strong>免责声明</strong>：本报告仅供参考，不构成任何投资建议。' +
    '投资有风险，入市需谨慎。基金过往业绩不代表未来表现。' +
    '</div>';

  document.getElementById('report').innerHTML = html;
  document.getElementById('report').style.display = '';
  document.getElementById('loading').style.display = 'none';

  // 初始化面板折叠和图表
  initPanels();
  renderRadarChart(d.scores);
}}

// ─────────────────────────────────────────────────────────────────────────────
//  数据加载（AJAX fetch JSON 文件）
// ─────────────────────────────────────────────────────────────────────────────

const JSON_FILE = '{json_basename}';

fetch(JSON_FILE)
  .then(function(resp) {{
    if (!resp.ok) throw new Error('HTTP ' + resp.status + ': ' + JSON_FILE);
    return resp.json();
  }})
  .then(function(data) {{
    render(data);
  }})
  .catch(function(err) {{
    document.getElementById('loading').style.display = 'none';
    const errEl = document.getElementById('error-msg');
    errEl.textContent = '加载数据失败：' + err.message;
    errEl.style.display = '';
    console.error(err);
  }});
</script>
</body>
</html>"""
