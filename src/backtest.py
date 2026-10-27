"""Walk-forward, cost-aware backtest of same-expiry spread reversion.
Signals are decided at day t's close and EXECUTED at day t+1's settlement (no trading on the price that made the signal)."""
import numpy as np
import pandas as pd
from .config import DEFAULT_COST_BPS, BASE


def simulate(spreads, entry_z=2.0, exit_z=0.5, min_dte=3, max_hold=15, costs=None):
    costs = costs or DEFAULT_COST_BPS
    trades = []
    for (sym, exp), g in spreads.groupby(["symbol", "expiry"]):
        g = g.sort_values("date").reset_index(drop=True)
        n, i = len(g), 0
        while i < n - 1:
            r = g.iloc[i]
            if (pd.notna(r.z) and abs(r.z) > entry_z and not r.thin_any and r.dte > min_dte + 2):
                side = -1 if r.z > 0 else 1                 # -1: short the rich contract, long GOLDM
                e = g.iloc[i + 1]                           # execute next day
                j = i + 1
                while True:
                    cur = g.iloc[j]
                    held = j - (i + 1)
                    stop = abs(cur.z) < exit_z or cur.dte <= min_dte or held >= max_hold
                    if stop and j < n - 1:
                        x = g.iloc[j + 1]; break           # exit executes next day
                    if j >= n - 1:
                        x = cur; break                      # forced exit on last row
                    j += 1
                gross = side * (x.spread - e.spread)        # Rs per gram of fine gold, 1 g each leg
                cost = ((costs[sym] * (e.fine_pg + x.fine_pg)) + (costs[BASE] * (e.base_pg + x.base_pg))) / 1e4
                trades.append(dict(symbol=sym, expiry=exp, entry_date=e.date, exit_date=x.date,
                                   side="short " + sym if side < 0 else "long " + sym,
                                   gross=gross, cost=cost, net=gross - cost,
                                   entry_spread_bps=e.spread_bps, hold_days=(x.date - e.date).days,
                                   gold_move=x.base_pg - e.base_pg,
                                   p_sum=e.fine_pg + x.fine_pg, b_sum=e.base_pg + x.base_pg))
                i = j + 1
            else:
                i += 1
    cols = ["symbol", "expiry", "entry_date", "exit_date", "side", "gross", "cost", "net",
            "entry_spread_bps", "hold_days", "gold_move", "p_sum", "b_sum"]
    return pd.DataFrame(trades, columns=cols)


def walk_forward(spreads, train_days=150, test_days=45, grid=(1.5, 2.0, 2.5, 3.0), **kw):
    dates = sorted(spreads.date.unique())
    out, folds, k, i = [], [], 0, train_days
    while i < len(dates):
        tr0, tr1 = dates[i - train_days], dates[i - 1]
        te = dates[i:i + test_days]
        sub_tr = spreads[spreads.date.between(tr0, tr1)]
        scores = {e: simulate(sub_tr, entry_z=e, **kw).net.sum() for e in grid}
        best = max(scores, key=scores.get)
        t = simulate(spreads[spreads.date.between(te[0], te[-1])], entry_z=best, **kw)
        t["fold"] = k
        out.append(t)
        folds.append(dict(fold=k, train=f"{pd.Timestamp(tr0).date()} to {pd.Timestamp(tr1).date()}",
                          test=f"{pd.Timestamp(te[0]).date()} to {pd.Timestamp(te[-1]).date()}",
                          chosen_entry_z=best, trades=len(t), net_per_gram=round(t.net.sum(), 2)))
        i += test_days; k += 1
    trades = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    return trades, pd.DataFrame(folds)


def summarize(trades, folds):
    if trades is None or trades.empty:
        return dict(n=0, gross=0, cost=0, net=0, hit=0, pos_folds=0, folds=0, gold_corr=np.nan,
                    verdict="Not enough trades to conclude", tone="neutral")
    n = len(trades)
    pos = int((folds.net_per_gram > 0).sum()) if len(folds) else 0
    nf = int((folds.trades > 0).sum()) if len(folds) else 0
    corr = trades[["net", "gold_move"]].corr().iloc[0, 1] if n > 3 else np.nan
    net = trades.net.sum()
    if n < 10:
        v, tone = "Too few trades to conclude anything", "neutral"
    elif net > 0 and nf and pos >= np.ceil(0.6 * nf):
        v, tone = "Edge survives costs on unseen data (tentative)", "good"
    else:
        v, tone = "No robust edge survives costs", "bad"
    return dict(n=n, gross=trades.gross.sum(), cost=trades.cost.sum(), net=net,
                hit=(trades.net > 0).mean(), pos_folds=pos, folds=nf, gold_corr=corr, verdict=v, tone=tone)
