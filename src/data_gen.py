"""Synthetic MCX-style gold data so the app runs with zero setup.
Clearly labelled SYNTHETIC in the UI. Includes realistic data faults for the Data Health demo."""
import numpy as np
import pandas as pd
from .config import CONTRACTS

SIGMA_BPS = {"GOLDM": 0.0, "GOLDTEN": 6.0, "GOLDGUINEA": 9.0, "GOLDPETAL": 14.0}
BASE_VOL = {"GOLDM": 9000, "GOLDTEN": 1400, "GOLDGUINEA": 350, "GOLDPETAL": 160}


def _expiries(start, end):
    out = []
    for p in pd.period_range(start, end + pd.offsets.MonthEnd(5), freq="M"):
        d = pd.Timestamp(p.year, p.month, 5)
        while d.weekday() >= 5:
            d += pd.Timedelta(days=1)
        out.append(d)
    return out


def make_synthetic(seed=7, start="2025-04-01", end="2026-10-21", inject_faults=True):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    spot = pd.Series(8900 * np.exp(np.cumsum(rng.normal(0.0004, 0.009, len(days)))), index=days)
    exps = _expiries(pd.Timestamp(start), pd.Timestamp(end))
    rows = []
    state = {}
    for t in days:
        live = [e for e in exps if e > t][:3]
        for rank, e in enumerate(live):
            dte = (e - t).days
            carry = 0.065 * dte / 365
            for sym, c in CONTRACTS.items():
                key = (sym, e)
                prev = state.get(key, 0.0)
                if SIGMA_BPS[sym]:
                    dev = 0.8 * prev + rng.normal(0, SIGMA_BPS[sym])
                else:
                    dev = rng.normal(0, 1.2)
                state[key] = dev
                dev_eff = dev * min(1.0, dte / 8)             # spreads converge into expiry
                fine = spot[t] * (1 + carry) * (1 + dev_eff / 1e4)
                settle = fine * (c["purity"] / 1000.0) * c["quote_g"]
                vol = int(rng.lognormal(np.log(BASE_VOL[sym] / (1 + 3 * rank)), 0.4))
                rows.append((t, t, sym, e, round(settle, 2), vol, vol * 3))
    df = pd.DataFrame(rows, columns=["requested_date", "returned_date", "symbol", "expiry", "settle", "volume", "oi"])
    if inject_faults:
        dates = list(days)
        # 1) MCX silently returns the previous day's file
        for i in rng.choice(np.arange(20, len(dates) - 1), 5, replace=False):
            t, p = dates[i], dates[i - 1]
            prev = df[df.requested_date == p].copy()
            df = df[df.requested_date != t]
            prev["requested_date"] = t
            df = pd.concat([df, prev], ignore_index=True)
        # 2) missing days
        for i in rng.choice(np.arange(20, len(dates) - 1), 4, replace=False):
            df = df[df.requested_date != dates[i]]
        # 3) unit error: petal quoted per 10 g by mistake
        idx = df[df.symbol == "GOLDPETAL"].sample(2, random_state=seed).index
        df.loc[idx, "settle"] *= 10
        # 4) thin / zero volume
        idx = df[df.symbol == "GOLDPETAL"].sample(25, random_state=seed + 1).index
        df.loc[idx, "volume"] = rng.integers(0, 20, len(idx))
    return df.sort_values(["requested_date", "symbol", "expiry"]).reset_index(drop=True)
