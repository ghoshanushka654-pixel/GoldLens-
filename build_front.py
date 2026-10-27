"""Builds the standalone front-end (one HTML file, no backend) from the Python pipeline results."""
import json, pandas as pd
from src.loader import load_data
from src.validate import validate
from src.signals import build_spreads
from src.backtest import walk_forward
from src.config import CONTRACTS, BASE, OTHERS, DEFAULT_COST_BPS

raw, src = load_data(); clean, log = validate(raw)
sp = build_spreads(clean); tr, fo = walk_forward(sp)
dates = sorted(clean.date.unique()); iso = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates]
ix = {d: i for i, d in enumerate(dates)}
front = sp[sp.dte >= 10].sort_values("dte").groupby(["symbol", "date"]).head(1)
ser, base = {}, [None] * len(dates)
for k in OTHERS:
    g = front[front.symbol == k].set_index("date")
    r = lambda col, n: [None if d not in g.index or pd.isna(g.at[d, col]) else round(float(g.at[d, col]), n) for d in dates]
    ser[k] = dict(s=r("spread_bps", 1), m=r("mean_past", 1), z=r("z", 2))
    if k == OTHERS[0]:
        base = r("base_pg", 1)
trades = [[ix[r.entry_date], ix[r.exit_date], r.symbol, round(float(r.gross), 3), round(float(r.p_sum), 1), round(float(r.b_sum), 1), int(r.fold)]
          for r in tr.itertuples()]
folds = [r.test for r in fo.itertuples()]
issues = [[r.date.strftime("%Y-%m-%d"), r.symbol, r.issue, r.detail, r.action] for r in log.itertuples()]
data = dict(iso=iso, ser=ser, base=base, trades=trades, nfold=len(folds), issues=issues,
            spec={k: [v["quote_g"], v["purity"], v["lot_g"]] for k, v in CONTRACTS.items()},
            cost=DEFAULT_COST_BPS, source=src)
html = open("front_template.html").read().replace("__DATA__", json.dumps(data, separators=(",", ":")))
open("docs/index.html", "w").write(html)
print(len(html), len(trades), len(issues), src)
