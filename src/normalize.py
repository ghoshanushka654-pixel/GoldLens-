import pandas as pd
from .config import CONTRACTS


def fine_price_per_gram(settle, symbol):
    """Quoted price -> Rs per gram of FINE (pure) gold."""
    c = CONTRACTS[symbol]
    return settle / c["quote_g"] / (c["purity"] / 1000.0)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["fine_pg"] = [fine_price_per_gram(p, s) for p, s in zip(out["settle"], out["symbol"])]
    out["dte"] = (pd.to_datetime(out["expiry"]) - pd.to_datetime(out["date"])).dt.days
    return out
