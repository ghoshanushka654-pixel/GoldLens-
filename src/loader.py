"""Load real MCX Bhavcopy CSVs from data/real/ if present; otherwise use synthetic demo data."""
import re
from pathlib import Path
import pandas as pd
from .config import CONTRACTS
from .data_gen import make_synthetic

ROOT = Path(__file__).resolve().parent.parent
REAL_DIR = ROOT / "data" / "real"

# Flexible column-name mapping: MCX files vary, so we match on lower-cased names.
ALIASES = {
    "date": ["date", "trade date", "tradedate", "returned_date"],
    "symbol": ["symbol", "commodity", "instrument name", "scrip"],
    "expiry": ["expiry date", "expirydate", "expiry", "expiry_date"],
    "settle": ["settlement price", "settle", "close", "closing price", "settle price", "ltp"],
    "volume": ["volume(in lots)", "volume (in lots)", "volume", "qty", "traded qty"],
    "oi": ["open interest(in lots)", "open interest", "oi"],
}


def _find(cols, names):
    low = {c.lower().strip(): c for c in cols}
    for n in names:
        if n in low:
            return low[n]
    return None


def _date_from_name(path):
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", path.stem)
    if m:
        return pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{2})[-_]?(\d{2})[-_]?(20\d{2})", path.stem)
    return pd.Timestamp(int(m[3]), int(m[2]), int(m[1])) if m else None


def load_real(folder=REAL_DIR):
    files = sorted(Path(folder).glob("*.csv"))
    if not files:
        return None
    frames = []
    for f in files:
        raw = pd.read_csv(f)
        m = {k: _find(raw.columns, v) for k, v in ALIASES.items()}
        missing = [k for k in ("date", "symbol", "expiry", "settle") if m[k] is None]
        if missing:
            raise ValueError(f"{f.name}: cannot find columns for {missing}. Found: {list(raw.columns)}. "
                             f"Add the real names to ALIASES in src/loader.py")
        df = pd.DataFrame({
            "returned_date": pd.to_datetime(raw[m["date"]], dayfirst=True, errors="coerce"),
            "symbol": raw[m["symbol"]].astype(str).str.upper().str.strip(),
            "expiry": pd.to_datetime(raw[m["expiry"]], dayfirst=True, errors="coerce"),
            "settle": pd.to_numeric(raw[m["settle"]], errors="coerce"),
            "volume": pd.to_numeric(raw[m["volume"]], errors="coerce").fillna(0) if m["volume"] else 0,
            "oi": pd.to_numeric(raw[m["oi"]], errors="coerce").fillna(0) if m["oi"] else 0,
        })
        df = df[df.symbol.isin(CONTRACTS)].dropna(subset=["returned_date", "expiry", "settle"])
        # The date we ASKED for comes from the file name; the date inside the file may differ.
        req = _date_from_name(f)
        df["requested_date"] = req if req is not None else df["returned_date"]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_data():
    """Returns (raw_df, source_label)."""
    real = load_real()
    if real is not None and len(real):
        return real, "REAL MCX Bhavcopy"
    return make_synthetic(), "SYNTHETIC DEMO DATA"
