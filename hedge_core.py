g: utf-8 -*-
"""
福彩3D 十位杀一码 — Hedge 加权投票核心引擎
=============================================
机制（学习 D:\\通杀一码\\core.py 的 hedge_kill）：
  专家池 = 5924万公式在最新500期穷举选出的 TopK（按族限选，见 bruteforce500.py）
  每期预测：近 win 期专家命中率 = 权重(下限 SMOOTH) → 各专家对当期投票 → 票王 = 十位杀码
  参数 win/k 由 144 组合网格扫描在 500 期回测上自动选优。
walk-forward：第 t 期预测只用 t-1 / t-2 期数据算特征，严格不偷看未来。
500 期回测 = 逐期真实预测记录（近期→远期输出）。

1000期连续回测：
  - 没有真实归档记录的期数：使用 walk-forward 事后重算结果
  - 存在 archive.jsonl 真实预测记录的期数：使用真实发布记录
  - 因此1000期表不会把“事后重算”冒充成“真实预测”
"""
import json
import os
import time

import numpy as np

from engine import load_data, get_next_issue
from formulas import feat_list, FEAT_VERSION, NF

WINDOW = 500
WIN_GRID = (
    30, 40, 50, 60, 70, 80, 90, 100, 110, 120,
    150, 180, 200, 240, 300
)
K_GRID = (
    6, 8, 10, 13, 16, 20, 24, 28, 32, 40,
    48, 64, 80, 96, 128, 160, 200, 256
)
SMOOTH = 0.02
TOPK = 560
PFL = 80
BASELINE = 0.9
WIN_MAX = max(WIN_GRID)
OOS_OFFSET = 500
CSV = 'data/fc3d-history.csv'


# ---------------------------------------------------------------- 辅助：真实预测归档

def load_real_records():
    """
    读取 archive.py 中已经保存的真实预测记录。

    返回：
        {issue: record}

    如果 archive.py 不存在、读取失败或没有记录，则返回空字典。

    注意：
    这里的真实记录只用于1000期连续回测的“对账覆盖”，
    不参与专家池、参数扫描或下一期预测算法。
    """
    try:
        import archive
        records = archive.load_records()
    except Exception as e:
        print(f"提示：读取真实预测归档失败，将全部使用回测重算：{e}")
        return {}

    if not records:
        return {}

    result = {}
    for r in records:
        if not isinstance(r, dict):
            continue

        issue = r.get('target_issue')
        if issue is None:
            issue = r.get('issue')

        if issue is None:
            continue

        issue = str(issue).strip()
        if not issue:
            continue

        result[issue] = r

    print(f"真实预测归档：{len(result)} 期")
    return result


def apply_real_record(row, real):
    """
    用真实预测记录覆盖1000期回测中的同一期。

    原则：
      1. 真实记录存在 → kill/top3/参数等采用真实发布值
      2. 真实记录不存在 → 保留事后重算
      3. 开奖十位、开奖数字仍来自历史开奖数据
      4. 增加 source/source_label 标记

    这样可以避免把真实预测和事后回测混成一种数据。
    """
    if not real:
        row['source'] = 'replay'
        row['source_label'] = '事后重算'
        return row

    # ---- 真实杀码 ----
    if real.get('kill') is not None:
        try:
            row['kill'] = int(real['kill'])
        except (TypeError, ValueError):
            pass

    # ---- Top3 ----
    top3 = real.get('top3')
    if top3 is None:
        top3 = real.get('top3_vote')

    if isinstance(top3, (list, tuple)) and len(top3):
        clean_top3 = []
        for x in top3:
            try:
                clean_top3.append(int(x))
            except (TypeError, ValueError):
                continue
        if clean_top3:
            row['top3'] = clean_top3

    # ---- 参数 ----
    if real.get('k') is not None:
        try:
            row['n_exp'] = int(real['k'])
        except (TypeError, ValueError):
            pass

    if real.get('win') is not None:
        try:
            row['win'] = int(real['win'])
        except (TypeError, ValueError):
            pass

    # ---- votes ----
    votes = real.get('votes')
    if votes is None:
        votes = real.get('top3_vote_dist')

    if isinstance(votes, (list, tuple)):
        try:
            row['votes'] = [round(float(x), 4) for x in votes]
        except (TypeError, ValueError):
            pass

    # ---- 专家信息 ----
    if real.get('fname') is not None:
        row['fname'] = str(real['fname'])

    if real.get('fam') is not None:
        row['fam'] = str(real['fam'])

    # ---- 当时首席专家命中率 ----
    if real.get('rate') is not None:
        try:
            row['rate'] = round(float(real['rate']), 4)
        except (TypeError, ValueError):
            pass

    # ---- 真实发布信息 ----
    if real.get('published_at') is not None:
        row['published_at'] = real['published_at']

    # 保留其他可能有用的真实记录字段
    if real.get('formula_name') is not None:
        row['real_formula_name'] = real['formula_name']

    if real.get('n_experts') is not None:
        try:
            row['n_experts_real'] = int(real['n_experts'])
        except (TypeError, ValueError):
            pass

    # 真实预测的命中状态必须根据开奖十位重新计算，
    # 不直接信任归档中的 hit，避免归档字段和历史开奖数据不一致。
    row['hit'] = bool(row['kill'] != int(row['tens']))

    row['source'] = 'real'
    row['source_label'] = '真实预测'

    return row


def merge_real_into_rows(rows, real_records):
    """
    将真实预测记录覆盖到1000期回测结果。

    返回：
        merged_rows, real_count

    rows 可以是近期在上，也可以是时间升序。
    """
    if not rows or not real_records:
        for r in rows:
            r['source'] = 'replay'
            r['source_label'] = '事后重算'
        return rows, 0

    count = 0

    for row in rows:
        issue = str(row.get('issue', ''))
        real = real_records.get(issue)

        if real is not None:
            apply_real_record(row, real)
            count += 1
        else:
            row['source'] = 'replay'
            row['source_label'] = '事后重算'

    return rows, count


def calc_streaks(hits):
    """
    根据最终显示的数据重新计算连中/连错。
    hits:
        True = 杀中
        False = 杀错
    """
    if not hits:
        return {
            'max_win': 0,
            'max_lose': 0,
            'cur_win': 0,
            'cur_lose': 0,
        }

    max_win = 0
    max_lose = 0
    cw = 0
    cl = 0

    for h in hits:
        if h:
            cw += 1
            cl = 0
        else:
            cl += 1
            cw = 0

        max_win = max(max_win, cw)
        max_lose = max(max_lose, cl)

    cur_win = 0
    cur_lose = 0

    for h in reversed(hits):
        if h:
            cur_win += 1
        else:
            break

    for h in reversed(hits):
        if not h:
            cur_lose += 1
        else:
            break

    return {
        'max_win': int(max_win),
        'max_lose': int(max_lose),
        'cur_win': int(cur_win),
        'cur_lose': int(cur_lose),
    }


# ---------------------------------------------------------------- 矩阵构建

def build_matrices(issues, hh, tt, oo, pool):
    """扩展 pred/hit 矩阵。"""
    N = len(hh)
    L0 = N - WINDOW - WIN_MAX

    assert L0 >= 2, (
        f"数据不足：需要至少 {WINDOW + WIN_MAX + 2} 期，当前 {N}"
    )

    F_ext = np.array([
        feat_list(
            hh[t - 1],
            tt[t - 1],
            oo[t - 1],
            prev=(hh[t - 2], tt[t - 2], oo[t - 2])
        )
        for t in range(L0, N + 1)
    ], dtype=np.int16)

    at_ext = np.concatenate([
        np.asarray(tt[L0:N], dtype=np.int16),
        [0]
    ])

    K = len(pool)
    pred = np.zeros(
        (K, N - L0 + 1),
        dtype=np.int16
    )

    for i, exp in enumerate(pool):
        cols = np.array(
            [idx for _, idx in exp['terms']],
            dtype=np.intp
        )
        coeffs = np.array(
            [c for c, _ in exp['terms']],
            dtype=np.int16
        )

        if len(cols) == 1:
            pred[i, :] = (
                F_ext[:, cols[0]] * coeffs[0] + exp['const']
            ) % 10
        else:
            pred[i, :] = (
                (
                    F_ext[:, cols]
                    * coeffs[None, :]
                ).sum(axis=1)
                + exp['const']
            ) % 10

    hit = pred != at_ext[None, :]

    assert hit.shape[1] == N - L0 + 1 == WINDOW + WIN_MAX + 1

    return pred, hit, L0, np.asarray(tt, dtype=np.int16)


# ---------------------------------------------------------------- Hedge 投票

def hedge_vote(win, k, smooth, j, hit, pred):
    """
    近 win 期命中率 TopK 专家加权投票。
    """
    lo = j - win

    rates = hit[:, lo:j].mean(axis=1)

    ti = np.lexsort(
        (
            np.arange(len(rates), dtype=np.int64),
            -rates
        )
    )[:k]

    w = np.maximum(rates[ti], smooth)

    votes = np.bincount(
        pred[ti, j],
        weights=w,
        minlength=10
    )

    kill = int(np.argmax(votes))

    return (
        kill,
        ti,
        w,
        votes,
        float(rates[ti[0]])
    )


def _top3_codes(kill, votes):
    order = sorted(
        range(10),
        key=lambda x: -float(votes[x])
    )

    return [
        kill
    ] + [
        c for c in order if c != kill
    ][:2]


# ---------------------------------------------------------------- 网格扫描

def build_oos_matrices(issues, hh, tt, oo, pool):
    """
    前段500期样本外矩阵。
    """
    N = len(hh)

    o_start = N - WINDOW - OOS_OFFSET
    L0 = o_start - WIN_MAX

    F_ext = np.array([
        feat_list(
            hh[t - 1],
            tt[t - 1],
            oo[t - 1],
            prev=(hh[t - 2], tt[t - 2], oo[t - 2])
        )
        for t in range(
            L0,
            o_start + WINDOW + 1
        )
    ], dtype=np.int16)

    at_ext = np.concatenate([
        np.asarray(
            tt[L0:o_start + WINDOW],
            dtype=np.int16
        ),
        [0]
    ])

    K = len(pool)

    pred = np.zeros(
        (
            K,
            o_start + WINDOW - L0 + 1
        ),
        dtype=np.int16
    )

    for i, exp in enumerate(pool):
        cols = np.array(
            [idx for _, idx in exp['terms']],
            dtype=np.intp
        )

        coeffs = np.array(
            [c for c, _ in exp['terms']],
            dtype=np.int16
        )

        if len(cols) == 1:
            pred[i, :] = (
                F_ext[:, cols[0]] * coeffs[0]
                + exp['const']
            ) % 10
        else:
            pred[i, :] = (
                (
                    F_ext[:, cols]
                    * coeffs[None, :]
                ).sum(axis=1)
                + exp['const']
            ) % 10

    hit = pred != at_ext[None, :]

    return pred, hit, L0


def grid_scan(
    hit,
    pred,
    tt_arr,
    L0,
    hit_o=None,
    pred_o=None,
    L0_o=None,
    win_grid=None,
    k_grid=None
):
    """
    270组合双段扫描。
    """
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

                kill, *_ = hedge_vote(
                    win,
                    k,
                    SMOOTH,
                    j,
                    hit,
                    pred
                )

                if kill != int(tt_arr[t]):
                    hits += 1

            out_hits = None

            if (
                hit_o is not None
                and pred_o is not None
                and L0_o is not None
            ):
                out_hits = 0

                for t in range(
                    o_start,
                    o_start + WINDOW
                ):
                    j = t - L0_o

                    kill, *_ = hedge_vote(
                        win,
                        k,
                        SMOOTH,
                        j,
                        hit_o,
                        pred_o
                    )

                    if kill != int(tt_arr[t]):
                        out_hits += 1

            results.append({
                'win': win,
                'k': k,
                'hits': hits,
                'total': WINDOW,
                'rate': round(
                    hits / WINDOW,
                    4
                ),
                'out_hits': out_hits,
                'out_rate': (
                    round(out_hits / WINDOW, 4)
                    if out_hits is not None
                    else None
                )
            })

    max_in = max(
        r['hits']
        for r in results
    )

    cand = [
        r for r in results
        if r['hits'] >= max_in - 2
    ]

    cand.sort(
        key=lambda r: (
            -(
                r['out_rate']
                if r['out_rate'] is not None
                else 0
            ),
            -r['k'],
            -r['win']
        )
    )

    results.sort(
        key=lambda r: (
            -r['rate'],
            -(r['out_rate'] or 0),
            -r['k'],
            -r['win']
        )
    )

    return results, cand[0]


# ---------------------------------------------------------------- 500期回测

def run_backtest(
    pool,
    pred,
    hit,
    L0,
    issues,
    hh,
    tt,
    oo,
    best_win,
    best_k
):
    """
    500期逐期事后回测。
    """
    N = len(hh)
    start = N - WINDOW

    rows = []

    for t in range(start, N):
        j = t - L0

        kill, ti, w, votes, top_rate = hedge_vote(
            best_win,
            best_k,
            SMOOTH,
            j,
            hit,
            pred
        )

        sel = ti.tolist()
        chief = pool[sel[0]]

        rows.append({
            'issue': str(issues[t]),
            'num': f"{hh[t]}{tt[t]}{oo[t]}",
            'tens': int(tt[t]),
            'kill': kill,
            'hit': bool(kill != int(tt[t])),
            'top3': _top3_codes(kill, votes),
            'n_exp': best_k,
            'votes': [
                round(float(x), 4)
                for x in votes
            ],
            'fname': chief['name'],
            'fam': chief['family'],
            'rate': round(top_rate, 4),
            'source': 'replay',
            'source_label': '事后重算',
        })

    hits = [
        r['hit']
        for r in rows
    ]

    rate = (
        sum(hits) / len(hits)
        if hits
        else 0
    )

    streak = calc_streaks(hits)

    j_end = (N - 1) - L0

    pool_avg = float(
        hit[
            :,
            j_end - WINDOW + 1:j_end + 1
        ].mean()
    )

    rows.reverse()

    summary = {
        'hit': int(sum(hits)),
        'total': WINDOW,
        'rate': round(rate, 4),
        'baseline': BASELINE,
        'pool_avg': round(pool_avg, 4),
        'max_win': streak['max_win'],
        'max_lose': streak['max_lose'],
        'cur_win': streak['cur_win'],
        'cur_lose': streak['cur_lose'],
    }

    return rows, summary


# ---------------------------------------------------------------- 1000期连续回测

def run_backtest_long(
    pool,
    issues,
    hh,
    tt,
    oo,
    best_win,
    best_k,
    n_seg=1000,
    real_records=None
):
    """
    1000期连续回测。

    核心规则：

    ① 先完整执行原来的1000期 walk-forward 重算。

    ② 如果某一期存在 archive.py 的真实预测记录，
       则用真实发布记录覆盖该期的：
         kill
         top3
         参数
         votes（如果归档有）
         首席专家（如果归档有）
         发布时间

    ③ 开奖数字、开奖十位始终来自历史开奖 CSV。

    ④ 最终命中率、连中、连错全部根据“最终显示的数据”重新计算。

    ⑤ source:
         real   = 真实预测
         replay = 事后重算
    """
    N = len(hh)

    start = N - n_seg

    L0 = start - best_win

    assert L0 >= 2, (
        f"数据不足：需要至少 {n_seg + best_win + 2} 期，当前 {N}"
    )

    # ------------------------------------------------------------
    # 构造1000期所需特征
    # ------------------------------------------------------------

    F_ext = np.array([
        feat_list(
            hh[t - 1],
            tt[t - 1],
            oo[t - 1],
            prev=(hh[t - 2], tt[t - 2], oo[t - 2])
        )
        for t in range(L0, N + 1)
    ], dtype=np.int16)

    at_ext = np.concatenate([
        np.asarray(
            tt[L0:N],
            dtype=np.int16
        ),
        [0]
    ])

    K = len(pool)

    pred = np.zeros(
        (
            K,
            N - L0 + 1
        ),
        dtype=np.int16
    )

    for i, exp in enumerate(pool):
        cols = np.array(
            [idx for _, idx in exp['terms']],
            dtype=np.intp
        )

        coeffs = np.array(
            [c for c, _ in exp['terms']],
            dtype=np.int16
        )

        if len(cols) == 1:
            pred[i, :] = (
                F_ext[:, cols[0]]
                * coeffs[0]
                + exp['const']
            ) % 10
        else:
            pred[i, :] = (
                (
                    F_ext[:, cols]
                    * coeffs[None, :]
                ).sum(axis=1)
                + exp['const']
            ) % 10

    hit = pred != at_ext[None, :]

    # ------------------------------------------------------------
    # 第一阶段：完全按照原算法生成1000期重算结果
    # ------------------------------------------------------------

    rows = []

    for t in range(start, N):
        j = t - L0

        kill, ti, w, votes, top_rate = hedge_vote(
            best_win,
            best_k,
            SMOOTH,
            j,
            hit,
            pred
        )

        chief = pool[ti[0]]

        rows.append({
            'issue': str(issues[t]),
            'num': f"{hh[t]}{tt[t]}{oo[t]}",
            'tens': int(tt[t]),
            'kill': kill,
            'hit': bool(kill != int(tt[t])),
            'top3': _top3_codes(kill, votes),
            'n_exp': best_k,
            'votes': [
                round(float(x), 4)
                for x in votes
            ],
            'fname': chief['name'],
            'fam': chief['family'],
            'rate': round(top_rate, 4),
            'source': 'replay',
            'source_label': '事后重算',
        })

    # ------------------------------------------------------------
    # 第二阶段：真实预测记录覆盖
    # ------------------------------------------------------------

    if real_records is None:
        real_records = load_real_records()

    rows, real_count = merge_real_into_rows(
        rows,
        real_records
    )

    # ------------------------------------------------------------
    # 第三阶段：按照最终显示结果重新计算统计
    # ------------------------------------------------------------

    # 当前 rows 还是时间升序：
    # 前500 = 远期
    # 后500 = 近期
    hits = [
        bool(r['hit'])
        for r in rows
    ]

    out_hits = sum(hits[:500])
    in_hits = sum(hits[500:])

    rate = (
        sum(hits) / len(hits)
        if hits
        else 0
    )

    streak = calc_streaks(hits)

    # 先记录分段数据来源情况
    far_real = sum(
        1 for r in rows[:500]
        if r.get('source') == 'real'
    )

    far_replay = 500 - far_real

    near_real = sum(
        1 for r in rows[500:]
        if r.get('source') == 'real'
    )

    near_replay = 500 - near_real

    rows.reverse()

    summary1000 = {
        'hit': int(sum(hits)),
        'total': n_seg,
        'rate': round(rate, 4),
        'baseline': BASELINE,

        'far_hits': int(out_hits),
        'far_rate': round(
            out_hits / 500,
            4
        ),

        'near_hits': int(in_hits),
        'near_rate': round(
            in_hits / 500,
            4
        ),

        'max_win': streak['max_win'],
        'max_lose': streak['max_lose'],
        'cur_win': streak['cur_win'],
        'cur_lose': streak['cur_lose'],

        # 新增：数据来源统计
        'real_count': int(real_count),
        'replay_count': int(n_seg - real_count),

        'far_real_count': int(far_real),
        'far_replay_count': int(far_replay),

        'near_real_count': int(near_real),
        'near_replay_count': int(near_replay),

        'source_rule': (
            '存在真实预测归档则采用真实预测；'
            '不存在真实预测归档则采用walk-forward事后重算'
        ),
    }

    return rows, summary1000


# ---------------------------------------------------------------- 下期预测

def next_prediction(
    pool,
    pred,
    hit,
    L0,
    issues,
    hh,
    tt,
    oo,
    fixed_info,
    best_win,
    best_k
):
    """
    下一期预测。
    """
    N = len(hh)

    j = N - L0

    kill, ti, w, votes, top_rate = hedge_vote(
        best_win,
        best_k,
        SMOOTH,
        j,
        hit,
        pred
    )

    experts = [
        {
            'name': pool[i]['name'],
            'fam': pool[i]['family'],
            'kill': int(pred[i, j]),
            'weight': round(float(wi), 4),
        }
        for i, wi in zip(
            ti.tolist(),
            w.tolist()
        )
    ]

    fixed_kill = None

    if fixed_info:
        cols = np.array(
            [idx for _, idx in fixed_info['terms']],
            dtype=np.intp
        )

        coeffs = np.array(
            [c for c, _ in fixed_info['terms']],
            dtype=np.int16
        )

        feats = np.array(
            feat_list(
                hh[N - 1],
                tt[N - 1],
                oo[N - 1],
                prev=(
                    hh[N - 2],
                    tt[N - 2],
                    oo[N - 2]
                )
            ),
            dtype=np.int16
        )

        fixed_kill = int(
            (
                int(
                    (
                        feats[cols] * coeffs
                    ).sum()
                )
                + fixed_info['const']
            ) % 10
        )

    return {
        'target_issue': str(
            get_next_issue(issues[-1])
        ),
        'last_issue': str(
            issues[-1]
        ),
        'last_draw': (
            f"{hh[-1]}{tt[-1]}{oo[-1]}"
        ),
        'kill': kill,
        'formula_name': (
            f"Hedge {best_k}专家加权投票"
            f"(win={best_win})"
        ),
        'n_experts': best_k,
        'win': best_win,
        'top_rate': round(
            top_rate,
            4
        ),
        'top3_vote': _top3_codes(
            kill,
            votes
        ),
        'top3_vote_dist': [
            round(float(x), 4)
            for x in votes
        ],
        'experts': experts,
        'refs': [
            {
                'id': 'Hedge',
                'name': (
                    f"Hedge投票"
                    f"(K={best_k},win={best_win})"
                ),
                'kill': kill
            },
            {
                'id': 'Fixed',
                'name': (
                    f"固定公式"
                    f"({fixed_info['name']})"
                ),
                'kill': fixed_kill
            },
        ],
    }


# ---------------------------------------------------------------- 榜单

def build_leaderboard(
    pool,
    hit,
    L0,
    N,
    best_win
):
    """
    池内专家按最近 best_win 期命中率 Top50。
    """
    j = (N - 1) - L0

    rates = hit[
        :,
        j - best_win + 1:j + 1
    ].mean(axis=1)

    idx = np.lexsort(
        (
            np.arange(
                len(rates),
                dtype=np.int64
            ),
            -rates
        )
    )[:50]

    return [
        {
            'name': pool[i]['name'],
            'fam': pool[i]['family'],
            'rate_recent': round(
                float(rates[i]),
                4
            )
        }
        for i in idx
    ]


# ---------------------------------------------------------------- 汇总

def main():
    t0 = time.time()

    issues, hh, tt, oo = load_data(CSV)

    with open(
        'cache/pool.json',
        'r',
        encoding='utf-8'
    ) as f:
        pj = json.load(f)

    pool = pj['pool']
    fixed_info = pj['fixed']

    print(
        f"数据 {len(issues)} 期："
        f"{issues[0]} ~ {issues[-1]}，"
        f"专家池 {len(pool)} 条"
    )

    # ------------------------------------------------------------
    # 500期核心矩阵
    # ------------------------------------------------------------

    pred, hit, L0, tt_arr = build_matrices(
        issues,
        hh,
        tt,
        oo,
        pool
    )

    print(
        f"矩阵构建完成 "
        f"({len(pool)}×{hit.shape[1]})，"
        f"L0={L0}，"
        f"用时 {time.time()-t0:.1f}s"
    )

    # ------------------------------------------------------------
    # 样本外矩阵 + 网格扫描
    # ------------------------------------------------------------

    pred_o, hit_o, L0_o = build_oos_matrices(
        issues,
        hh,
        tt,
        oo,
        pool
    )

    scan, best = grid_scan(
        hit,
        pred,
        tt_arr,
        L0,
        hit_o=hit_o,
        pred_o=pred_o,
        L0_o=L0_o
    )

    oos_note = (
        f"，样本外 {best['out_rate']*100:.2f}%"
        if best.get('out_rate') is not None
        else ""
    )

    print(
        f"网格扫描 {len(scan)} 组合 → "
        f"最优 win={best['win']}, "
        f"k={best['k']}, "
        f"段内 {best['hits']}/{best['total']} "
        f"= {best['rate']*100:.2f}%"
        f"{oos_note}"
    )

    # ------------------------------------------------------------
    # 500期回测
    # ------------------------------------------------------------

    rows, summary = run_backtest(
        pool,
        pred,
        hit,
        L0,
        issues,
        hh,
        tt,
        oo,
        best['win'],
        best['k']
    )

    print(
        f"500期回测: "
        f"命中 {summary['hit']}/{summary['total']} "
        f"= {summary['rate']*100:.2f}% "
        f"(基线 {BASELINE*100:.0f}%)  "
        f"最大连错 {summary['max_lose']}"
    )

    # ------------------------------------------------------------
    # 下一期预测
    # ------------------------------------------------------------

    nxt = next_prediction(
        pool,
        pred,
        hit,
        L0,
        issues,
        hh,
        tt,
        oo,
        fixed_info,
        best['win'],
        best['k']
    )

    print(
        f"下期 {nxt['target_issue']} "
        f"十位杀码: {nxt['kill']} "
        f"(Top3票码 {nxt['top3_vote']})"
    )

    # ------------------------------------------------------------
    # 真实预测归档
    # ------------------------------------------------------------

    real_records = load_real_records()

    # ------------------------------------------------------------
    # 1000期连续回测 + 真实记录覆盖
    # ------------------------------------------------------------

    rows1000, summary1000 = run_backtest_long(
        pool,
        issues,
        hh,
        tt,
        oo,
        best['win'],
        best['k'],
        real_records=real_records
    )

    print(
        f"1000期最终对账: "
        f"命中 {summary1000['hit']}/"
        f"{summary1000['total']} "
        f"= {summary1000['rate']*100:.2f}% "
        f"| 真实记录 "
        f"{summary1000['real_count']}期 "
        f"| 事后重算 "
        f"{summary1000['replay_count']}期"
    )

    print(
        f"  前500: "
        f"{summary1000['far_hits']}/500 "
        f"= {summary1000['far_rate']*100:.2f}% "
        f"| 真实 {summary1000['far_real_count']} "
        f"| 重算 {summary1000['far_replay_count']}"
    )

    print(
        f"  后500: "
        f"{summary1000['near_hits']}/500 "
        f"= {summary1000['near_rate']*100:.2f}% "
        f"| 真实 {summary1000['near_real_count']} "
        f"| 重算 {summary1000['near_replay_count']}"
    )

    # ------------------------------------------------------------
    # 明确检查用户提到的2026251
    # ------------------------------------------------------------

    check_issue = '2026251'

    check_rows = [
        r for r in rows1000
        if str(r.get('issue')) == check_issue
    ]

    if check_rows:
        r = check_rows[0]

        print(
            f"对账检查 {check_issue}: "
            f"杀{r['kill']} "
            f"| 来源={r.get('source_label', '-')}"
        )

        if r.get('source') == 'real':
            print(
                f"  ✓ {check_issue} 已采用真实预测记录"
            )
        else:
            print(
                f"  ! {check_issue} 没有找到真实预测归档，"
                f"当前仍为事后重算"
            )

    # ------------------------------------------------------------
    # 专家榜单
    # ------------------------------------------------------------

    lb = build_leaderboard(
        pool,
        hit,
        L0,
        len(issues),
        best['win']
    )

    # ------------------------------------------------------------
    # 最终 result.json
    # ------------------------------------------------------------

    result = {
        'fingerprint': (
            f"{len(issues)}_"
            f"{issues[-1]}_"
            f"{FEAT_VERSION}"
        ),

        'generated_at': time.strftime(
            '%Y-%m-%d %H:%M:%S'
        ),

        'data_info': {
            'n_issues': len(issues),
            'first': issues[0],
            'last': issues[-1],
            'last_draw': (
                f"{hh[-1]}{tt[-1]}{oo[-1]}"
            )
        },

        'pool_info': {
            'pool_size_total':
                pj['stats']['pool_size_total'],
            'window': WINDOW,
            'topk': TOPK,
            'pfl': PFL,
            'n_families':
                pj['stats']['n_families'],
            'n_features':
                pj.get('n_features', NF),
            'feat_version':
                FEAT_VERSION,
            'scan_seconds':
                pj['stats']['scan_seconds']
        },

        'params': {
            'win': best['win'],
            'k': best['k'],
            'smooth': SMOOTH,
            'baseline': BASELINE,
            'oos_offset': OOS_OFFSET,
            'oos_rate':
                best.get('out_rate')
        },

        'scan': scan,
        'best_scan': best,

        'next': nxt,

        'summary': summary,

        'summary1000': summary1000,

        'fixed': {
            'name': fixed_info['name'],
            'rate': fixed_info['rate'],
            'hits': fixed_info['hits']
        },

        'rows': rows,

        'rows1000': rows1000,

        'leaderboard': lb,

        # --------------------------------------------------------
        # 给网页使用的真实归档
        # --------------------------------------------------------
        'real': list(
            real_records.values()
        ),

        'real_info': {
            'count': len(real_records),
            'rule': (
                '1000期中存在真实归档的期数采用真实预测；'
                '其余期数采用walk-forward事后重算'
            )
        }
    }

    os.makedirs(
        'cache',
        exist_ok=True
    )

    with open(
        'cache/result.json',
        'w',
        encoding='utf-8'
    ) as f:
        json.dump(
            result,
            f,
            ensure_ascii=False
        )

    print(
        f"\n已写入 cache/result.json，"
        f"总用时 {time.time()-t0:.1f}s"
    )

    return result


if __name__ == '__main__':
