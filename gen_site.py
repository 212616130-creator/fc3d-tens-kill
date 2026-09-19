# -*- coding: utf-8 -*-
"""
福彩3D 十位杀一码 — 生成固定静态网页（本地「十位杀一码.html」/ 云端「index.html」）
=========================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML:
数据以 window.__DATA__ 内联 JSON 嵌入, 双击即开, 零后端, 可传手机浏览。
网页风格以 D:\\通杀一码\\通杀一码.html 为准（浅色移动优先、红色杀码大字、白卡片、逐期表近期在上）。
输出文件名由环境变量 FC3D_OUT_HTML 控制：云端(GitHub Pages)设为 index.html，本地默认 十位杀一码.html。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_JSON = os.path.join(BASE_DIR, 'cache', 'result.json')
OUT_HTML = os.environ.get('FC3D_OUT_HTML') or os.path.join(BASE_DIR, '十位杀一码.html')
if not os.path.isabs(OUT_HTML):
    OUT_HTML = os.path.join(BASE_DIR, OUT_HTML)

# 内置样式（复刻通杀一码.css）
CSS_TEXT = """
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:#f2f4f7;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#1f2937;padding-bottom:40px}
.wrap{max-width:480px;margin:0 auto;padding:0 10px}
.topbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);backdrop-filter:blur(6px);border-bottom:1px solid #e5e7eb;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.topbar .t{font-size:17px;font-weight:700;letter-spacing:.5px}
.topbar .t b{color:#2563eb}
.topbar .sub{font-size:11px;color:#9ca3af;margin-top:2px}
.card{background:#fff;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);padding:14px 14px;margin-top:10px}
.card h3{font-size:13px;color:#6b7280;font-weight:600;margin-bottom:8px;letter-spacing:.3px}
.balls{display:flex;align-items:center;justify-content:center;gap:12px;padding:4px 0}
.ball{width:52px;height:52px;border-radius:50%;background:linear-gradient(145deg,#fff,#eef2f7);border:2px solid #d1d5db;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:800;color:#111827;box-shadow:inset 0 2px 4px rgba(0,0,0,.06)}
.ball.r{background:linear-gradient(145deg,#ff6b6b,#dc2626);border-color:#b91c1c;color:#fff}
.ball.b{background:linear-gradient(145deg,#60a5fa,#2563eb);border-color:#1d4ed8;color:#fff}
.issue-tag{text-align:center;font-size:12px;color:#6b7280;margin-top:6px}
.kill-box{text-align:center;padding:6px 0 2px}
.kill-label{font-size:13px;color:#6b7280;letter-spacing:2px}
.kill-num{font-size:96px;font-weight:900;line-height:1.15;background:linear-gradient(180deg,#dc2626,#991b1b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.kill-info{font-size:12.5px;color:#374151;margin-top:4px}
.kill-info .f{font-weight:700;color:#2563eb}
.kill-meta{font-size:11.5px;color:#9ca3af;margin-top:6px;line-height:1.6}
.stat-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center}
.stat{background:#f9fafb;border-radius:10px;padding:9px 4px}
.stat .v{font-size:19px;font-weight:800}
.stat .k{font-size:11px;color:#6b7280;margin-top:2px}
.stat.hl{background:#eff6ff}
.stat.hl .v{color:#2563eb}
.v.g{color:#059669}.v.r{color:#dc2626}
.compare{display:flex;justify-content:space-between;font-size:11.5px;color:#6b7280;margin-top:9px;padding:0 2px}
.bar{height:6px;border-radius:3px;background:#e5e7eb;margin-top:5px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:3px;background:#2563eb}
.bar i.green{background:#059669}
.warn{background:#fef3c7;border:1px solid #f59e0b;color:#92400e;border-radius:8px;padding:8px 11px;font-size:11.5px;margin-top:9px;line-height:1.6}
.tbl-scroll{max-height:52vh;overflow-y:auto;border-radius:10px;border:1px solid #eef0f3}
table{width:100%;border-collapse:collapse;font-size:12.5px}
thead th{position:sticky;top:0;background:#f3f4f6;color:#4b5563;font-weight:600;padding:8px 6px;text-align:center;border-bottom:1px solid #e5e7eb;z-index:2;white-space:nowrap}
tbody td{padding:7px 6px;text-align:center;border-bottom:1px solid #f3f4f6}
tbody tr:active{background:#f9fafb}
td.iss{color:#6b7280;font-family:ui-monospace,Consolas,monospace;font-size:11.5px}
td.num{font-weight:700;letter-spacing:1px}
td.tens{font-size:16px;font-weight:800;width:34px}
td.tens.ok{color:#059669}
td.tens.bad{color:#dc2626;background:#fee2e2;border-radius:50%}
td.kill{font-weight:800;font-size:15px}
td.kill.hit{color:#059669}
td.kill.miss{color:#dc2626}
td.res{font-size:15px}
td.fname{font-size:11px;color:#6b7280;max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td.frate{font-size:11px;color:#9ca3af}
td.t3{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#9ca3af}
td.t3 b{color:#dc2626;font-weight:800;font-size:13px}
.miss-row td{background:#fef2f2}
.scan-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}
.scan-cell{background:#f9fafb;border-radius:8px;padding:6px 2px;text-align:center;font-size:11px;color:#6b7280}
.scan-cell b{display:block;font-size:15px;color:#374151;margin-top:2px}
.scan-cell.best{background:#eff6ff;border:1px solid #2563eb}
.scan-cell.best b{color:#2563eb}
.lb-item{display:flex;align-items:center;gap:8px;padding:8px 4px;border-bottom:1px solid #f3f4f6;font-size:12.5px}
.lb-item:last-child{border-bottom:none}
.lb-rank{width:22px;height:22px;border-radius:50%;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#6b7280;flex-shrink:0}
.lb-rank.top3{background:#fef3c7;color:#b45309}
.lb-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lb-fam{font-size:10px;background:#eff6ff;color:#2563eb;border-radius:4px;padding:1px 5px;flex-shrink:0}
.lb-rate{font-weight:700;color:#2563eb;flex-shrink:0}
details{border-top:1px solid #f3f4f6;margin-top:10px}
details summary{cursor:pointer;font-size:13px;font-weight:600;color:#374151;padding:10px 2px;list-style:none;display:flex;align-items:center;justify-content:space-between}
details summary::after{content:"▾";color:#9ca3af;font-size:12px}
details[open] summary::after{content:"▴"}
.footer{margin-top:16px;padding:12px;background:#fff;border-radius:12px;font-size:11px;color:#9ca3af;line-height:1.7}
.footer b{color:#6b7280}
"""

BODY_TEMPLATE = """
  <div class="card" style="border:2px solid #2563eb">
    <div class="kill-box">
      <div class="kill-label" id="killLabel">下期十位杀一码</div>
      <div class="kill-num" id="killNum">-</div>
      <div class="kill-info">机制: <span class="f" id="killFormula">-</span></div>
      <div class="kill-meta" id="killMeta"></div>
      <div class="kill-timing" id="killTiming" style="margin-top:8px;padding:6px 10px;background:#eff6ff;border-radius:8px;font-size:12px;color:#1d4ed8;line-height:1.6"></div>
    </div>
  </div>

  <div class="card">
    <h3>🏆 最新开奖 <span style="color:#9ca3af;font-weight:400">(已开奖 · 用于推算下一期)</span></h3>
    <div class="balls" id="balls"><div class="ball">-</div><div class="ball">-</div><div class="ball">-</div></div>
    <div class="issue-tag" id="lastIssue"></div>
  </div>

  <div class="card">
    <h3>📊 近500期回测汇总 <span style="color:#9ca3af;font-weight:400">(Hedge加权投票 walk-forward)</span></h3>
    <div class="stat-grid">
      <div class="stat hl"><div class="v" id="stRate">-</div><div class="k">回测命中率</div></div>
      <div class="stat"><div class="v" id="stHit">-</div><div class="k">命中/总数</div></div>
      <div class="stat"><div class="v" id="stPool">-</div><div class="k">专家池均值</div></div>
      <div class="stat"><div class="v" id="stMaxWin">-</div><div class="k">最大连中</div></div>
      <div class="stat"><div class="v r" id="stMaxLose">-</div><div class="k">最大连错</div></div>
      <div class="stat"><div class="v g" id="stCur">-</div><div class="k">当前状态</div></div>
    </div>
    <div class="compare">
      <span>理论基线 90%</span>
      <span id="poolNote"></span>
    </div>
    <div class="bar"><i class="green" id="barBase" style="width:0%"></i></div>
    <div class="warn" id="warnSel"></div>
  </div>

  <div class="card">
    <details>
      <summary>📈 1000期连续回测 <span style="color:#9ca3af;font-weight:400;font-size:11px">(walk-forward · 前500=样本外 + 后500=选出段)</span></summary>
      <div class="stat-grid" style="margin:8px 0">
        <div class="stat hl"><div class="v" id="st1000Rate">-</div><div class="k">1000期总命中率</div></div>
        <div class="stat"><div class="v" id="st1000Far">-</div><div class="k">前500期(样本外)</div></div>
        <div class="stat"><div class="v" id="st1000Near">-</div><div class="k">后500期(选出段)</div></div>
        <div class="stat"><div class="v" id="st1000MaxWin">-</div><div class="k">最大连中</div></div>
        <div class="stat"><div class="v r" id="st1000MaxLose">-</div><div class="k">最大连错</div></div>
        <div class="stat"><div class="v" id="st1000Cur">-</div><div class="k">当前状态</div></div>
      </div>
      <div class="warn" id="warn1000"></div>
      <div class="tbl-scroll" style="max-height:45vh">
        <table>
          <thead><tr><th>期号</th><th>开奖</th><th>十位</th><th>票码Top3</th><th>杀码</th><th>结果</th><th>首席专家</th></tr></thead>
          <tbody id="tbBody1000"></tbody>
        </table>
      </div>
    </details>
  </div>

  <div class="card">
    <h3>📌 真实预测记录 <span style="color:#9ca3af;font-weight:400">(每期开奖前真实发布 · 自归档日起逐期累积 · 含Top3票码)</span></h3>
    <div class="tbl-scroll" style="max-height:40vh">
      <table>
        <thead><tr><th>预测期</th><th>发布杀码</th><th>Top3票码</th><th>参数</th><th>发布时间</th><th>开奖十位</th><th>结果</th></tr></thead>
        <tbody id="realBody"><tr><td colspan="7" style="color:#9ca3af">加载中...</td></tr></tbody>
      </table>
    </div>
    <div class="compare" style="margin-top:6px"><span id="realNote" style="font-size:11px;color:#9ca3af">-</span></div>
  </div>

  <div class="card">
    <h3>🎛 参数网格扫描 <span style="color:#9ca3af;font-weight:400">(270组合双段自动选优)</span></h3>
    <div class="scan-grid" id="scanGrid"></div>
    <div class="compare" style="margin-top:8px"><span id="bestScanNote">-</span></div>
  </div>

  <div class="card">
    <details>
      <summary>🏅 专家池 Top50 <span style="color:#9ca3af;font-weight:400;font-size:11px">(按近窗命中率)</span></summary>
      <div id="lbBody"><div class="loading" style="padding:16px">加载中...</div></div>
    </details>
  </div>

  <div class="footer">
    <b>说明</b><br>
    ① 十位杀一码 = 预测杀掉 0-9 中一个数字，下期<b>十位</b>不出现即命中，理论随机基线 <b>90%</b>。<br>
    ② 公式池 <b id="fc">-</b> 个暴力穷举算法（<span id="nfeat">-</span>特征线性组合），在<b>最新500期</b>按命中率选 Top560 专家池（按族限选保证多样性），主机制 <b>Hedge 加权投票</b>：每期取近 <span id="pWin">-</span> 期命中率 Top<span id="pK">-</span> 专家，按命中率加权投票，票王 = 十位杀码。参数经 <b>270 组合双段网格扫描</b>自动选优（段内500期 + 前500期样本外稳健性：先保段内最优、再挑样本外最稳，防选择偏差峰值）。<br>
    ③ 回测为<b>事后统一重算</b>（walk-forward 不偷看未来，但参数是最终选定的）——500/1000期回测表是<b>参考口径</b>；<b>「📌 真实预测记录」才是每期开奖前真实发布的杀码</b>（自归档日起逐期累积，含当时参数）。<br>
    ④ <b>选择偏差警示</b>：专家池是在回测的同一段 500 期上按命中率选出的——段内高分是选择偏差上界（270组合中挑峰值），真实水平更接近「样本外稳健性」指标（前500期独立段回测）；「固定公式」高分同为<b>选择偏差假象</b>（5924万公式中挑最大值）。<b>不构成任何购彩建议</b>。<br>
    ⑤ <b>固定快照</b>：本页为数据快照（生成于 <span id="genTime">-</span>），数据更新后请重新导出。
  </div>
"""


def build_html(data):
    payload = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>福彩3D · 十位杀一码 (固定快照)</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <div class="t">福彩3D · <b>十位杀一码</b></div>
      <div class="sub" id="dataInfo">数据加载中...</div>
    </div>
  </div>
{BODY_TEMPLATE}
</div>
<script>
window.__DATA__ = {payload};
</script>
<script>
var DATA = window.__DATA__;
var $ = function(id){{ return document.getElementById(id); }};
function fmtPct(x){{ return (x*100).toFixed(1)+"%"; }}
function render(d){{
  DATA = d;
  var n = d.next, s = d.summary, di = d.data_info, pi = d.pool_info;
  $("dataInfo").textContent = "数据至 " + di.last + " 期 · 共 " + di.n_issues + " 期 · " + pi.n_features + "特征/" + pi.pool_size_total.toLocaleString() + "公式 · 专家池 " + pi.topk + " (固定快照)";
  $("fc").textContent = pi.pool_size_total.toLocaleString();
  $("nfeat").textContent = pi.n_features;
  var num = di.last_draw;
  $("balls").innerHTML = '<div class="ball r">'+num[0]+'</div><div class="ball r">'+num[1]+'</div><div class="ball r">'+num[2]+'</div>';
  $("lastIssue").textContent = "第 " + di.last + " 期开奖";
  $("killLabel").textContent = n.target_issue + " 期 十位杀一码";
  $("killNum").textContent = n.kill;
  $("killFormula").textContent = "Hedge 加权投票 (K=" + n.n_experts + ", win=" + n.win + ")";
  $("killMeta").innerHTML = "首席专家近"+ n.win +"期命中率 <b>" + fmtPct(n.top_rate) + "</b> · 基线 90%<br>Top3票码: " + n.top3_vote.join(" / ") +
    "<br>参考: " + n.refs.map(function(r){{ return r.name + " → 杀" + r.kill; }}).join(" · ");
  // 提前量提示：预测期 vs 发布时间 vs 开奖时间（北京 21:15）
  if (d.generated_at && n.target_issue) {{
    var pub = String(d.generated_at).slice(0, 16).replace("T", " ");
    $("killTiming").innerHTML = "📅 预测 <b>" + n.target_issue + "</b> 期 · 发布 <b>" + pub + "</b><br>" +
      "🎯 开奖 <b>" + n.target_issue + "</b> 期当天 21:15（北京）· <b>提前约 23 小时</b> · 开奖后自动更新下一期";
  }}
  $("stRate").textContent = fmtPct(s.rate);
  $("stRate").style.color = s.rate >= s.baseline ? "#2563eb" : "#dc2626";
  $("stHit").textContent = s.hit + "/" + s.total;
  $("stPool").textContent = fmtPct(s.pool_avg);
  $("stMaxWin").textContent = s.max_win;
  $("stMaxLose").textContent = s.max_lose;
  if(s.cur_lose > 0){{ $("stCur").textContent = "连错"+s.cur_lose; $("stCur").style.color = "#dc2626"; }}
  else {{ $("stCur").textContent = "连中"+s.cur_win; $("stCur").style.color = "#059669"; }}
  var oosRate = (d.best_scan && d.best_scan.out_rate != null) ? d.best_scan.out_rate : null;
  $("poolNote").textContent = (oosRate != null ? "样本外稳健性 " + fmtPct(oosRate) + " · " : "") + "专家池均值 " + fmtPct(s.pool_avg) + " · 固定公式(偏差) " + fmtPct(d.fixed.rate);
  $("barBase").style.width = Math.min(100, (s.baseline*100)) + "%";
  if (oosRate != null) {{
    var od = (oosRate - s.baseline) * 100;
    var msg = "⚠ 段内回测 " + fmtPct(s.rate) + " 是选择偏差上界（专家池在该500期段内选出）；前500期样本外稳健性 " + fmtPct(oosRate) + "（基线90%），真实预测水平更接近样本外。";
    if (od > 2) msg += " 样本外高于基线 " + od.toFixed(1) + "pp，略有稳健优势，但切勿以段内数字为准。";
    else if (od >= -2) msg += " 样本外贴近基线（±2pp内），无稳定超额信号。";
    else msg += " 样本外低于基线，谨慎参考。";
    $("warnSel").textContent = msg;
  }} else {{
    var diff = (s.rate - s.baseline) * 100;
    if (Math.abs(diff) > 6) {{
      $("warnSel").textContent = "⚠ 回测率与90%基线偏离 " + diff.toFixed(1) + "pp，超出500期二项波动常规范围，疑含过拟合，请谨慎参考。";
    }} else {{
      $("warnSel").textContent = "⚠ 专家池在回测的同一段500期上选出（穷举窗口=回测窗口），回测含轻微选择偏差，样本外会回落。";
    }}
  }}
  $("pWin").textContent = d.params.win;
  $("pK").textContent = d.params.k;
  var sg = "";
  var scanList = d.scan.slice().sort(function(a,b){{ return (b.rate-a.rate) || ((b.out_rate||0)-(a.out_rate||0)) || b.k-a.k || b.win-a.win; }}).slice(0,36);
  scanList.forEach(function(r){{
    var cls = (r.win === d.best_scan.win && r.k === d.best_scan.k) ? " best" : "";
    var outTxt = (r.out_rate != null) ? '<span style="display:block;font-size:10px;color:' + (r.out_rate >= 0.9 ? "#059669" : "#dc2626") + '">外' + fmtPct(r.out_rate) + '</span>' : "";
    sg += '<div class="scan-cell' + cls + '">win' + r.win + '/K' + r.k + '<b>' + fmtPct(r.rate) + '</b>' + r.hits + '/' + r.total + outTxt + '</div>';
  }});
  $("scanGrid").innerHTML = sg;
  $("bestScanNote").textContent = "双段稳健选优: win=" + d.best_scan.win + ", K=" + d.best_scan.k + " → 段内 " + fmtPct(d.best_scan.rate) + " · 样本外 " + (oosRate != null ? fmtPct(oosRate) : "-") + "（Top36/270展示）";

  // ---- 真实预测记录（每期开奖前真实发布）----
  if (d.real && d.real.length > 0) {{
    var rh = "";
    d.real.forEach(function(r){{
      var st = "";
      if (r.hit === true) st = '✅命中';
      else if (r.hit === false) st = '❌杀错';
      else st = '⏳待开奖';
      var tensTxt = (r.tens != null) ? r.tens : '-';
      var tensCls = (r.hit === true) ? "ok" : (r.hit === false) ? "bad" : "";
      var pub = r.published_at ? String(r.published_at).slice(5, 16) : '-';
      // Top3票码：票王(杀码)加粗红，其余灰色
      var t3 = (r.top3 && r.top3.length) ? r.top3.map(function(c, i){{
        return i === 0 ? '<b style="color:#dc2626">' + c + '</b>' : '<span style="color:#9ca3af">' + c + '</span>';
      }}).join('·') : '-';
      rh += '<tr>' +
        '<td class="iss">' + r.target_issue + '</td>' +
        '<td class="kill ' + (r.hit === true ? "hit" : (r.hit === false ? "miss" : "")) + '">' + r.kill + '</td>' +
        '<td class="t3">' + t3 + '</td>' +
        '<td class="frate">win' + r.win + '/K' + r.k + '</td>' +
        '<td class="frate">' + pub + '</td>' +
        '<td class="tens ' + tensCls + '">' + tensTxt + '</td>' +
        '<td class="res">' + st + '</td></tr>';
    }});
    $("realBody").innerHTML = rh;
    var done = d.real.filter(function(r){{ return r.hit != null; }}).length;
    var hits = d.real.filter(function(r){{ return r.hit === true; }}).length;
    $("realNote").textContent = "已归档 " + d.real.length + " 期真实预测 · 已开奖 " + done + " 期 · 命中 " + hits + "/" + done +
      (done > 0 ? " = " + (hits/done*100).toFixed(1) + "%" : "") + "（自归档日起逐期累积，历史500期为事后重算参考）";
  }} else {{
    $("realBody").innerHTML = '<tr><td colspan="7" style="color:#9ca3af">暂无真实预测记录（从下一次开奖归档起）</td></tr>';
    $("realNote").textContent = "自归档日起逐期累积真实发布记录";
  }}

  if (d.rows1000 && d.summary1000) {{
    var s1 = d.summary1000;
    $("st1000Rate").textContent = fmtPct(s1.rate);
    $("st1000Rate").style.color = s1.rate >= s1.baseline ? "#2563eb" : "#dc2626";
    $("st1000Far").textContent = fmtPct(s1.far_rate);
    $("st1000Far").style.color = s1.far_rate >= s1.baseline ? "#2563eb" : "#dc2626";
    $("st1000Near").textContent = fmtPct(s1.near_rate);
    $("st1000MaxWin").textContent = s1.max_win;
    $("st1000MaxLose").textContent = s1.max_lose;
    if(s1.cur_lose > 0){{ $("st1000Cur").textContent = "连错"+s1.cur_lose; $("st1000Cur").style.color = "#dc2626"; }}
    else {{ $("st1000Cur").textContent = "连中"+s1.cur_win; $("st1000Cur").style.color = "#059669"; }}
    var fd = (s1.far_rate - s1.baseline) * 100;
    $("warn1000").textContent = "⚠ 前500期是样本外（专家池在最新500期选出，未见过前段数据）：" + fmtPct(s1.far_rate) + " 才是真实水平参考；后500期 " + fmtPct(s1.near_rate) + " 含选择偏差。样本外较基线 " + (fd >= 0 ? "+" : "") + fd.toFixed(1) + "pp（±1.3pp噪声内，无统计显著超额）。";
    var html2 = "";
    d.rows1000.forEach(function(r){{
      var cls = r.hit ? "hit" : "miss";
      var t3 = (r.top3 || [r.kill]).map(function(c, i){{ return i === 0 ? '<b>' + c + '</b>' : c; }}).join("·");
      var vd = r.votes ? " · 票数分布[" + r.votes.map(function(v){{return v.toFixed(1);}}).join(",") + "]" : "";
      var tens = (r.tens != null) ? r.tens : String(r.num).charAt(1);   // 兼容旧缓存
      html2 += '<tr class="' + (r.hit ? "" : "miss-row") + '">' +
        '<td class="iss">' + r.issue + '</td>' +
        '<td class="num">' + r.num + '</td>' +
        '<td class="tens ' + (r.hit ? "ok" : "bad") + '">' + tens + '</td>' +
        '<td class="t3">' + t3 + '</td>' +
        '<td class="kill ' + cls + '">' + r.kill + '</td>' +
        '<td class="res">' + (r.hit ? "✅" : "❌") + '</td>' +
        '<td class="fname" title="' + r.fname + ' [' + r.fam + ']' + vd + '">' + r.fname + '</td></tr>';
    }});
    $("tbBody1000").innerHTML = html2;
  }}
  var lb = "";
  d.leaderboard.forEach(function(f, i){{
    var rank = i < 3 ? '<div class="lb-rank top3">' + (i+1) + '</div>' : '<div class="lb-rank">' + (i+1) + '</div>';
    lb += '<div class="lb-item">' + rank +
      '<span class="lb-name">' + f.name + '</span>' +
      '<span class="lb-fam">' + f.fam + '</span>' +
      '<span class="lb-rate">' + fmtPct(f.rate_recent) + '</span></div>';
  }});
  $("lbBody").innerHTML = lb || "无数据";
  $("genTime").textContent = d.generated_at;
}}
render(DATA);
</script>
</body>
</html>
"""


def main():
    if not os.path.exists(CACHE_JSON):
        raise RuntimeError("未找到 cache/result.json，请先运行 hedge_core.py 或 update.py")
    with open(CACHE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 嵌入逐期真实预测记录（archive.jsonl 归档的每期开奖前真实发布）
    try:
        import archive
        data['real'] = archive.load_records()
    except Exception:
        data['real'] = []
    html = build_html(data)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    s, n = data['summary'], data['next']
    print(f"已生成固定网页: {OUT_HTML}")
    print(f"数据至 {data['data_info']['last']} 期 | 公式池 {data['pool_info']['pool_size_total']:,} | 专家池 {data['pool_info']['topk']}")
    print(f"机制: Hedge(K={n['n_experts']},win={n['win']}) | 回测 {s['hit']}/{s['total']} = {s['rate']*100:.2f}% (基线90%)")
    print(f"下一期 {n['target_issue']} 十位杀 {n['kill']}")
    print("手机访问 GitHub Pages / 本地双击 HTML 均可查看。")

if __name__ == '__main__':
    main()
