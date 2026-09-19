# -*- coding: utf-8 -*-
"""
福彩3D 十位杀一码 — 生成固定静态网页
=========================================================
读 cache/result.json，输出一个完全自包含的单文件 HTML。

重要：
1000期连续回测表：
  - 有 archive.jsonl 真实预测记录 → 显示真实预测
  - 没有真实预测记录 → 显示 walk-forward 事后重算
  - 页面明确标记数据来源

输出文件：
  云端：index.html
  本地：十位杀一码.html

环境变量：
  FC3D_OUT_HTML
"""

import json
import os


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CACHE_JSON = os.path.join(
    BASE_DIR,
    'cache',
    'result.json'
)

OUT_HTML = (
    os.environ.get('FC3D_OUT_HTML')
    or os.path.join(
        BASE_DIR,
        '十位杀一码.html'
    )
)

if not os.path.isabs(OUT_HTML):
    OUT_HTML = os.path.join(
        BASE_DIR,
        OUT_HTML
    )


# ---------------------------------------------------------------- CSS

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
.kill-timing{margin-top:8px;padding:6px 10px;background:#eff6ff;border-radius:8px;font-size:12px;color:#1d4ed8;line-height:1.6}
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
.source-real{display:inline-block;background:#eff6ff;color:#2563eb;border-radius:5px;padding:2px 5px;font-size:10px;white-space:nowrap}
.source-replay{display:inline-block;background:#f3f4f6;color:#6b7280;border-radius:5px;padding:2px 5px;font-size:10px;white-space:nowrap}
.source-mixed{display:inline-block;background:#fef3c7;color:#92400e;border-radius:5px;padding:2px 5px;font-size:10px;white-space:nowrap}
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
.real-row td{background:#f8fbff}
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


# ---------------------------------------------------------------- HTML主体

BODY_TEMPLATE = """
  <div class="card" style="border:2px solid #2563eb">
    <div class="kill-box">
      <div class="kill-label" id="killLabel">下期十位杀一码</div>
      <div class="kill-num" id="killNum">-</div>
      <div class="kill-info">
        机制:
        <span class="f" id="killFormula">-</span>
      </div>
      <div class="kill-meta" id="killMeta"></div>
      <div id="killTiming"></div>
    </div>
  </div>

  <div class="card">
    <h3>
      🏆 最新开奖
      <span style="color:#9ca3af;font-weight:400">
        (已开奖 · 用于推算下一期)
      </span>
    </h3>

    <div class="balls" id="balls">
      <div class="ball">-</div>
      <div class="ball">-</div>
      <div class="ball">-</div>
    </div>

    <div class="issue-tag" id="lastIssue"></div>
  </div>

  <div class="card">
    <h3>
      📊 近500期回测汇总
      <span style="color:#9ca3af;font-weight:400">
        (Hedge加权投票 walk-forward)
      </span>
    </h3>

    <div class="stat-grid">
      <div class="stat hl">
        <div class="v" id="stRate">-</div>
        <div class="k">回测命中率</div>
      </div>

      <div class="stat">
        <div class="v" id="stHit">-</div>
        <div class="k">命中/总数</div>
      </div>

      <div class="stat">
        <div class="v" id="stPool">-</div>
        <div class="k">专家池均值</div>
      </div>

      <div class="stat">
        <div class="v" id="stMaxWin">-</div>
        <div class="k">最大连中</div>
      </div>

      <div class="stat">
        <div class="v r" id="stMaxLose">-</div>
        <div class="k">最大连错</div>
      </div>

      <div class="stat">
        <div class="v g" id="stCur">-</div>
        <div class="k">当前状态</div>
      </div>
    </div>

    <div class="compare">
      <span>理论基线 90%</span>
      <span id="poolNote"></span>
    </div>

    <div class="bar">
      <i class="green" id="barBase" style="width:0%"></i>
    </div>

    <div class="warn" id="warnSel"></div>
  </div>


  <div class="card">
    <details>
      <summary>
        📈 1000期连续回测
        <span style="color:#9ca3af;font-weight:400;font-size:11px">
          (真实记录优先 + 其余walk-forward重算)
        </span>
      </summary>

      <div
        style="margin:8px 0;background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:9px 10px;font-size:11px;color:#6b7280;line-height:1.7"
        id="source1000Note">
        数据来源说明加载中...
      </div>

      <div class="stat-grid" style="margin:8px 0">
        <div class="stat hl">
          <div class="v" id="st1000Rate">-</div>
          <div class="k">1000期总命中率</div>
        </div>

        <div class="stat">
          <div class="v" id="st1000Far">-</div>
          <div class="k">前500期</div>
        </div>

        <div class="stat">
          <div class="v" id="st1000Near">-</div>
          <div class="k">后500期</div>
        </div>

        <div class="stat">
          <div class="v" id="st1000MaxWin">-</div>
          <div class="k">最大连中</div>
        </div>

        <div class="stat">
          <div class="v r" id="st1000MaxLose">-</div>
          <div class="k">最大连错</div>
        </div>

        <div class="stat">
          <div class="v" id="st1000Cur">-</div>
          <div class="k">当前状态</div>
        </div>
      </div>

      <div class="warn" id="warn1000"></div>

      <div class="tbl-scroll" style="max-height:45vh">
        <table>
          <thead>
            <tr>
              <th
