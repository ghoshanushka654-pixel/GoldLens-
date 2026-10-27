"""Data Health: every problem we catch is logged, never silently fixed."""
import pandas as pd
from .config import CONTRACTS, MIN_VOLUME_LOTS, UNIT_OUTLIER_PCT
from .normalize import fine_price_per_gram

COLS = ["date", "symbol", "issue", "detail", "action"]


def _issue(date, symbol, issue, detail, action):
    return dict(date=date, symbol=symbol, issue=issue, detail=detail, action=action)


def validate(raw: pd.DataFrame):
    """raw needs: requested_date, returned_date, symbol, expiry, settle, volume, oi.
    Returns (clean_df with column `date` and `thin`, issues_df)."""
    issues = []
    df = raw.copy()
    df["requested_date"] = pd.to_datetime(df["requested_date"])
    df["returned_date"] = pd.to_datetime(df["returned_date"])
    df["expiry"] = pd.to_datetime(df["expiry"])

    # 1) MCX can silently return a different day than requested
    bad = df[df.requested_date != df.returned_date]
    for d, g in bad.groupby("requested_date"):
        issues.append(_issue(d, "ALL", "WRONG_DATE",
                             f"asked for {d.date()}, file contained {g.returned_date.iloc[0].date()}",
                             "Dropped whole day"))
    df = df[df.requested_date == df.returned_date].copy()
    df["date"] = df["requested_date"]

    # 2) contract traded before it was listed (e.g. GOLDTEN before April 2025)
    for sym, c in CONTRACTS.items():
        pre = df[(df.symbol == sym) & (df.date < pd.Timestamp(c["listed"]))]
        if len(pre):
            issues.append(_issue(pre.date.min(), sym, "BEFORE_LISTING",
                                 f"{len(pre)} rows before listing {c['listed']}", "Dropped"))
            df = df.drop(pre.index)

    # 3) duplicates
    dup = df.duplicated(["date", "symbol", "expiry"], keep="first")
    if dup.any():
        issues.append(_issue(df[dup].date.min(), "ALL", "DUPLICATE_ROWS", f"{int(dup.sum())} duplicate rows", "Kept first"))
        df = df[~dup]

    # 4) unit errors: fine-gold price far from the day's median
    df["_fine"] = [fine_price_per_gram(p, s) for p, s in zip(df.settle, df.symbol)]
    med = df.groupby("date")["_fine"].transform("median")
    out = (df["_fine"] / med - 1).abs() > UNIT_OUTLIER_PCT
    for _, r in df[out].iterrows():
        issues.append(_issue(r.date, r.symbol, "UNIT_OUTLIER",
                             f"fine price {r._fine:,.0f}/g vs day median {med[_]:,.0f}/g (likely wrong quote unit)",
                             "Dropped row"))
    df = df[~out].drop(columns="_fine")

    # 5) thin contracts: kept but flagged, never treated as tradable depth
    df["thin"] = df["volume"] < MIN_VOLUME_LOTS
    thin = df[df.thin]
    if len(thin):
        for sym, g in thin.groupby("symbol"):
            issues.append(_issue(g.date.min(), sym, "THIN_VOLUME",
                                 f"{len(g)} contract-days under {MIN_VOLUME_LOTS} lots", "Flagged, excluded from signals"))

    # 6) missing business days (exchange holidays also appear here: informational)
    have = set(df.date.unique())
    if have:
        for d in pd.bdate_range(min(have), max(have)):
            if d not in have:
                issues.append(_issue(d, "ALL", "MISSING_DAY", "no usable data (holiday or bad download)", "Left empty, not filled"))

    log = pd.DataFrame(issues, columns=COLS).sort_values("date").reset_index(drop=True) if issues else pd.DataFrame(columns=COLS)
    return df.drop(columns=["requested_date", "returned_date"]).reset_index(drop=True), log
