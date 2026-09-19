# -*- coding: utf-8 -*-
"""
福彩3D 十位杀一码 — Hedge 加权投票核心引擎
=============================================
机制（学习 D:\\通杀一码\\core.py 的 hedge_kill）：
  专家池 = 5924万公式在最新500期穷举选出的 TopK（按族限选，见 bruteforce500.py）
  每期预测：近 win 期专家命中率 = 权重(下限 SMOOTH) → 各专家对当期投票 → 票王 = 十位杀码
  参数 win/k 由 144 组合网格扫描在 500 期回测上自动选优。
walk-forward：第 t 期预测只用 t-1 / t-2 期数据算特征，严格不偷看未来。
500 期回测 = 逐期真实预测记录（近期→远期输出）。
"""
import json
import os
import time

import numpy as np

from engine import load_data, get_next_issue
from formulas import feat_list, FEAT_VERSION, NF

WINDOW = 500          # 回测窗口 / 穷举窗口
WIN_GRID = (30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 150, 180, 200, 240, 300)   # 网格扫描（15×18=270组合）
K_GRID = (6, 8, 10, 13, 16, 20, 24, 28, 32, 40, 48, 64, 80, 96, 128, 160, 200, 256)
SMOOTH = 0.02         # 权重下限
TOPK = 560
PFL = 80              # 每族限选上限（7族×80=560=TOPK）
BASELINE = 0.9        # 十位杀1码随机基线
WIN_MAX = max(WIN_GRID)   # 300：特征矩阵向历史方向扩展，保证回测首期也有满窗口
OOS_OFFSET = 500          # 样本外段起点偏移：前段500期 = 紧邻回测段之前（双段稳健选优）
CSV = 'data/fc3d-history.csv'


# ---------------------------------------------------------------- 矩阵构建

def build_matrices(issues, hh, tt, oo, pool):
    """扩展 pred/hit 矩阵：列 j 对应数据期 L0+j。
    回测期 t∈[N-WINDOW,N) → 列 j=t-L0∈[150,650)，近win窗口 hit[:, j-win:j] 恒满。
    末列 j=N-L0=650 对应下一期预测（特征用第N-1、N-2期数据，未用第N期开奖）。
    返回 (pred, hit, L0, tt_arr)
    """
    N = len(hh)
    L0 = N - WINDOW - WIN_MAX
    assert L0 >= 2, f"数据不足：需要至少 {WINDOW + WIN_MAX + 2} 期，当前 {N}"
    # 特征：数据期 t 的特征由 期t-1、期t-2 计算
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, N + 1)
    ], dtype=np.int16)                                     # (651, 59)
    # 被预测十位：末列占位（预测期，仅用于结构一致，不参与回测）
    at_ext = np.concatenate([np.asarray(tt[L0:N], dtype=np.int16), [0]])  # (651,)
    K = len(pool)
    pred = np.zeros((K, N - L0 + 1), dtype=np.int16)       # (240, 651)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10
    hit = (pred != at_ext[None, :])
    # 断言防未来信息：回测列 j 的 pred 仅由 F_ext[j] 一行（期 L0+j-1 / L0+j-2）算出
    assert hit.shape[1] == N - L0 + 1 == WINDOW + WIN_MAX + 1
    return pred, hit, L0, np.asarray(tt, dtype=np.int16)


# ---------------------------------------------------------------- Hedge 投票

def hedge_vote(win, k, smooth, j, hit, pred):
    """近 win 期命中率 TopK 专家加权投票，票王 = 杀码。
    返回 (kill, sel_idx, weights, votes, top_rate)"""
    lo = j - win
    rates = hit[:, lo:j].mean(axis=1)                      # (K,)
    # 稳定 TopK：命中率降序，并列按专家索引升序（确定性，跨 numpy 版本/机器结果一致）
    ti = np.lexsort((np.arange(len(rates), dtype=np.int64), -rates))[:k]
    w = np.maximum(rates[ti], smooth)
    votes = np.bincount(pred[ti, j], weights=w, minlength=10)
    kill = int(np.argmax(votes))
    return kill, ti, w, votes, float(rates[ti[0]])


def _top3_codes(kill, votes):
    order = sorted(range(10), key=lambda x: -float(votes[x]))
    return [kill] + [c for c in order if c != kill][:2]


# ---------------------------------------------------------------- 网格扫描

def build_oos_matrices(issues, hh, tt, oo, pool):
    """前段500期(样本外) pred/hit 矩阵：段起点 o_start = N-1000（紧邻回测段之前）。
    用于双段稳健选优——每组合同时报告段内/样本外命中率，防纯段内选择偏差峰值。
    返回 (pred, hit, L0)；与 build_matrices 同构，末列占位不参与回测。"""
    N = len(hh)
    o_start = N - WINDOW - OOS_OFFSET        # 前段起点（7730）
    L0 = o_start - WIN_MAX                   # 特征起点（7430）
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, o_start + WINDOW + 1)
    ], dtype=np.int16)
    at_ext = np.concatenate([np.asarray(tt[L0:o_start + WINDOW], dtype=np.int16), [0]])
    K = len(pool)
    pred = np.zeros((K, o_start + WINDOW - L0 + 1), dtype=np.int16)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10
    hit = (pred != at_ext[None, :])
    return pred, hit, L0


def grid_scan(hit, pred, tt_arr, L0, hit_o=None, pred_o=None, L0_o=None,
              win_grid=None, k_grid=None):
    """270 组合 (win,k) 双段扫描：段内500期 + 前段500期(样本外)。
    选优口径（防选择偏差峰值）：先过滤段内命中 ≥ 峰值-2期(0.4pp)，
    候选内 样本外命中率 → k更大 → win更大。"""
    if win_grid is None:
        win_grid = WIN_GRID
    if k_grid is None:
        k_grid = K_GRID
    N = len(tt_arr)
    start = N - WINDOW
    o_start = start - OOS_OFFSET
    results = []
    for win in win_grid:
        for k in k_grid:
            hits = 0
            for t in range(start, N):
                j = t - L0
                kill, *_ = hedge_vote(win, k, SMOOTH, j, hit, pred)
                if kill != int(tt_arr[t]):
                    hits += 1
            out_hits = None
            if hit_o is not None and pred_o is not None and L0_o is not None:
                out_hits = 0
                for t in range(o_start, o_start + WINDOW):
                    j = t - L0_o
                    kill, *_ = hedge_vote(win, k, SMOOTH, j, hit_o, pred_o)
                    if kill != int(tt_arr[t]):
                        out_hits += 1
            results.append({'win': win, 'k': k, 'hits': hits,
                            'total': WINDOW, 'rate': round(hits / WINDOW, 4),
                            'out_hits': out_hits,
                            'out_rate': round(out_hits / WINDOW, 4) if out_hits is not None else None})
    # 选优：段内峰值组内（≥峰值-2期）→ 样本外降序 → k → win
    max_in = max(r['hits'] for r in results)
    cand = [r for r in results if r['hits'] >= max_in - 2]
    cand.sort(key=lambda r: (-(r['out_rate'] if r['out_rate'] is not None else 0),
                             -r['k'], -r['win']))
    results.sort(key=lambda r: (-r['rate'], -(r['out_rate'] or 0), -r['k'], -r['win']))
    return results, cand[0]


# ---------------------------------------------------------------- 500期回测

def run_backtest(pool, pred, hit, L0, issues, hh, tt, oo, best_win, best_k):
    """500期逐期真实回测（walk-forward），返回 (rows[近期在上], summary)。"""
    N = len(hh)
    start = N - WINDOW
    rows = []
    for t in range(start, N):
        j = t - L0
        kill, ti, w, votes, top_rate = hedge_vote(best_win, best_k, SMOOTH, j, hit, pred)
        sel = ti.tolist()
        chief = pool[sel[0]]
        rows.append({
            'issue': str(issues[t]),
            'num': f"{hh[t]}{tt[t]}{oo[t]}",
            'tens': int(tt[t]),              # 真实开奖十位（逐期对账用）
            'kill': kill,
            'hit': bool(kill != int(tt[t])),
            'top3': _top3_codes(kill, votes),
            'n_exp': best_k,
            'votes': [round(float(x), 4) for x in votes],
            'fname': chief['name'],
            'fam': chief['family'],
            'rate': round(top_rate, 4),
        })
    hits = [r['hit'] for r in rows]
    rate = sum(hits) / len(hits)
    cur_win = cur_lose = 0
    for h in reversed(hits):
        if h: cur_win += 1
        else: break
    for h in reversed(hits):
        if not h: cur_lose += 1
        else: break
    max_win = max_lose = cw = cl = 0
    for h in hits:
        if h: cw += 1; cl = 0
        else: cl += 1; cw = 0
        max_win = max(max_win, cw); max_lose = max(max_lose, cl)
    # 专家池均值（选择偏差口径）
    j_end = (N - 1) - L0
    pool_avg = float(hit[:, j_end - WINDOW + 1:j_end + 1].mean())
    rows.reverse()                                        # 近期→远期
    summary = {
        'hit': int(sum(hits)), 'total': WINDOW, 'rate': round(rate, 4),
        'baseline': BASELINE,
        'pool_avg': round(pool_avg, 4),
        'max_win': int(max_win), 'max_lose': int(max_lose),
        'cur_win': int(cur_win), 'cur_lose': int(cur_lose),
    }
    return rows, summary


# ---------------------------------------------------------------- 1000期连续回测

def run_backtest_long(pool, issues, hh, tt, oo, best_win, best_k, n_seg=1000):
    """1000期连续回测（walk-forward）：第t期只用 t-1/t-2 数据 + 近 best_win 期命中率。
    专家池仍在最新500期（8231~8730）选出——故 前500期=样本外（真实水平参考 91~92%），
    后500期=选出段（选择偏差上界 99%+）。rows 按 t 升序生成后反转（近期在上）。
    返回 (rows[1000行 近期在上], summary1000)。"""
    N = len(hh)
    start = N - n_seg
    L0 = start - best_win          # 特征起点：留 best_win 期历史窗，保证回测首期也有满窗口
    assert L0 >= 2, f"数据不足：需要至少 {n_seg + best_win + 2} 期，当前 {N}"
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, N + 1)
    ], dtype=np.int16)
    at_ext = np.concatenate([np.asarray(tt[L0:N], dtype=np.int16), [0]])
    K = len(pool)
    pred = np.zeros((K, N - L0 + 1), dtype=np.int16)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10
    hit = (pred != at_ext[None, :])
    rows = []
    for t in range(start, N):
        j = t - L0
        kill, ti, w, votes, top_rate = hedge_vote(best_win, best_k, SMOOTH, j, hit, pred)
        chief = pool[ti[0]]
        rows.append({
            'issue': str(issues[t]),
            'num': f"{hh[t]}{tt[t]}{oo[t]}",
            'tens': int(tt[t]),              # 真实开奖十位（逐期对账用）
            'kill': kill,
            'hit': bool(kill != int(tt[t])),
            'top3': _top3_codes(kill, votes),
            'n_exp': best_k,
            'votes': [round(float(x), 4) for x in votes],
            'fname': chief['name'],
            'fam': chief['family'],
            'rate': round(top_rate, 4),
        })
    hits = [r['hit'] for r in rows]                      # t 升序：前500=远期样本外，后500=近期选出段
    out_hits = sum(hits[:500])                           # 远期500期（样本外 7731~8230）
    in_hits = sum(hits[500:])                            # 近期500期（选出段 8231~8730）
    rate = sum(hits) / len(hits)
    max_win = max_lose = cw = cl = 0
    for h in hits:
        if h: cw += 1; cl = 0
        else: cl += 1; cw = 0
        max_win = max(max_win, cw); max_lose = max(max_lose, cl)
    cur_win = cur_lose = 0
    for h in reversed(hits):
        if h: cur_win += 1
        else: break
    for h in reversed(hits):
        if not h: cur_lose += 1
        else: break
    rows.reverse()                                       # 近期→远期
    summary1000 = {
        'hit': int(sum(hits)), 'total': n_seg, 'rate': round(rate, 4),
        'baseline': BASELINE,
        'far_hits': int(out_hits), 'far_rate': round(out_hits / 500, 4),   # 远期500=样本外
        'near_hits': int(in_hits), 'near_rate': round(in_hits / 500, 4),   # 近期500=选出段
        'max_win': int(max_win), 'max_lose': int(max_lose),
        'cur_win': int(cur_win), 'cur_lose': int(cur_lose),
    }
    return rows, summary1000


# ---------------------------------------------------------------- 下期预测

def next_prediction(pool, pred, hit, L0, issues, hh, tt, oo, fixed_info, best_win, best_k):
    """下一期（2026223）十位杀码：最近 best_win 期专家命中率加权投票。"""
    N = len(hh)
    j = N - L0                                            # 650：F_ext 末行（期N-1/N-2数据）
    kill, ti, w, votes, top_rate = hedge_vote(best_win, best_k, SMOOTH, j, hit, pred)
    experts = [{
        'name': pool[i]['name'], 'fam': pool[i]['family'],
        'kill': int(pred[i, j]), 'weight': round(float(wi), 4),
    } for i, wi in zip(ti.tolist(), w.tolist())]
    # 固定公式对照（选择偏差口径）：fixed 公式对下期预测
    fixed_kill = None
    if fixed_info:
        cols = np.array([idx for _, idx in fixed_info['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in fixed_info['terms']], dtype=np.int16)
        feats = np.array(feat_list(hh[N - 1], tt[N - 1], oo[N - 1],
                                   prev=(hh[N - 2], tt[N - 2], oo[N - 2])), dtype=np.int16)
        fixed_kill = int((int((feats[cols] * coeffs).sum()) + fixed_info['const']) % 10)
    return {
        'target_issue': str(get_next_issue(issues[-1])),
        'last_issue': str(issues[-1]),
        'last_draw': f"{hh[-1]}{tt[-1]}{oo[-1]}",
        'kill': kill,
        'formula_name': f"Hedge {best_k}专家加权投票(win={best_win})",
        'n_experts': best_k,
        'win': best_win,
        'top_rate': round(top_rate, 4),
        'top3_vote': _top3_codes(kill, votes),
        'top3_vote_dist': [round(float(x), 4) for x in votes],
        'experts': experts,
        'refs': [
            {'id': 'Hedge', 'name': f"Hedge投票(K={best_k},win={best_win})", 'kill': kill},
            {'id': 'Fixed', 'name': f"固定公式({fixed_info['name']})", 'kill': fixed_kill},
        ],
    }


# ---------------------------------------------------------------- 榜单

def build_leaderboard(pool, hit, L0, N, best_win):
    """池内专家按最近 best_win 期命中率 Top50。"""
    j = (N - 1) - L0
    rates = hit[:, j - best_win + 1:j + 1].mean(axis=1)
    # 稳定 Top50：并列按索引升序（与 hedge_vote 一致，跨环境确定性）
    idx = np.lexsort((np.arange(len(rates), dtype=np.int64), -rates))[:50]
    return [{'name': pool[i]['name'], 'fam': pool[i]['family'],
             'rate_recent': round(float(rates[i]), 4)} for i in idx]


# ---------------------------------------------------------------- 汇总

def main():
    t0 = time.time()
    issues, hh, tt, oo = load_data(CSV)
    with open('cache/pool.json', 'r', encoding='utf-8') as f:
        pj = json.load(f)
    pool, fixed_info = pj['pool'], pj['fixed']
    print(f"数据 {len(issues)} 期：{issues[0]} ~ {issues[-1]}，专家池 {len(pool)} 条")

    pred, hit, L0, tt_arr = build_matrices(issues, hh, tt, oo, pool)
    print(f"矩阵构建完成 ({len(pool)}×{hit.shape[1]})，L0={L0}，用时 {time.time()-t0:.1f}s")

    pred_o, hit_o, L0_o = build_oos_matrices(issues, hh, tt, oo, pool)
    scan, best = grid_scan(hit, pred, tt_arr, L0, hit_o=hit_o, pred_o=pred_o, L0_o=L0_o)
    oos_note = f"，样本外 {best['out_rate']*100:.2f}%" if best.get('out_rate') is not None else ""
    print(f"网格扫描 {len(scan)} 组合 → 最优 win={best['win']}, k={best['k']}, 段内 {best['hits']}/{best['total']} = {best['rate']*100:.2f}%{oos_note}")

    rows, summary = run_backtest(pool, pred, hit, L0, issues, hh, tt, oo,
                                 best['win'], best['k'])
    print(f"500期回测: 命中 {summary['hit']}/{summary['total']} = {summary['rate']*100:.2f}% "
          f"(基线 {BASELINE*100:.0f}%)  最大连错 {summary['max_lose']}")

    nxt = next_prediction(pool, pred, hit, L0, issues, hh, tt, oo, fixed_info,
                          best['win'], best['k'])
    print(f"下期 {nxt['target_issue']} 十位杀码: {nxt['kill']}  (Top3票码 {nxt['top3_vote']})")

    rows1000, summary1000 = run_backtest_long(pool, issues, hh, tt, oo,
                                              best['win'], best['k'])
    print(f"1000期回测: 命中 {summary1000['hit']}/{summary1000['total']} = {summary1000['rate']*100:.2f}% "
          f"(远期500=样本外 {summary1000['far_rate']*100:.2f}% | 近期500=选出段 {summary1000['near_rate']*100:.2f}%)")

    lb = build_leaderboard(pool, hit, L0, len(issues), best['win'])

    result = {
        'fingerprint': f"{len(issues)}_{issues[-1]}_{FEAT_VERSION}",
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1],
                      'last_draw': f"{hh[-1]}{tt[-1]}{oo[-1]}"},
        'pool_info': {'pool_size_total': pj['stats']['pool_size_total'],
                      'window': WINDOW, 'topk': TOPK, 'pfl': PFL,
                      'n_families': pj['stats']['n_families'],
                      'n_features': pj.get('n_features', NF),
                      'feat_version': FEAT_VERSION,
                      'scan_seconds': pj['stats']['scan_seconds']},
        'params': {'win': best['win'], 'k': best['k'], 'smooth': SMOOTH,
                   'baseline': BASELINE,
                   'oos_offset': OOS_OFFSET,
                   'oos_rate': best.get('out_rate')},
        'scan': scan, 'best_scan': best,
        'next': nxt,
        'summary': summary,
        'summary1000': summary1000,
        'fixed': {'name': fixed_info['name'], 'rate': fixed_info['rate'],
                  'hits': fixed_info['hits']},
        'rows': rows,
        'rows1000': rows1000,
        'leaderboard': lb,
    }
    os.makedirs('cache', exist_ok=True)
    with open('cache/result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"\n已写入 cache/result.json，总用时 {time.time()-t0:.1f}s")
    return result


if __name__ == '__main__':
    main()
