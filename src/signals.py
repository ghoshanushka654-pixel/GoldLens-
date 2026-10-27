"""Same-expiry spreads between each contract and the reference (GOLDM), on a fine-gold basis.
The z-score uses ONLY past data (shifted by one day), so no look-ahead."""
import pandas as pd
from .config import BASE
from .normalize import normalize


def build_spreads(clean: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    n = normalize(clean)
    base = n[n.symbol == BASE][["date", "expiry", "fine_pg", "thin", "volume"]].rename(
        columns={"fine_pg": "base_pg", "thin": "base_thin", "volume": "base_vol"})
    oth = n[n.symbol != BASE]
    m = oth.merge(base, on=["date", "expiry"], how="inner")
    m["spread"] = m["fine_pg"] - m["base_pg"]
    m["spread_bps"] = m["spread"] / m["base_pg"] * 1e4
    m["thin_any"] = m["thin"] | m["base_thin"]
    m = m.sort_values(["symbol", "expiry", "date"]).reset_index(drop=True)
    grp = m.groupby(["symbol", "expiry"])["spread_bps"]
    prev = grp.shift(1)                                  # yesterday and earlier only
    m["_prev"] = prev
    g2 = m.groupby(["symbol", "expiry"])["_prev"]
    m["mean_past"] = g2.transform(lambda s: s.rolling(window, min_periods=10).mean())
    m["std_past"] = g2.transform(lambda s: s.rolling(window, min_periods=10).std())
    m["z"] = (m["spread_bps"] - m["mean_past"]) / m["std_past"]
    return m.drop(columns="_prev")
