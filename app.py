import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import CONTRACTS, BASE, OTHERS, DEFAULT_COST_BPS
from src.loader import load_data
from src.validate import validate
from src.normalize import normalize
from src.signals import build_spreads
from src.backtest import walk_forward, summarize

INK, BRASS, MIST, GOOD, BAD, GRID = "#2A2418", "#B8860B", "#7A6F58", "#3E7B4F", "#A8412F", "#E9DFC4"
LINES = {"GOLDM": INK, "GOLDTEN": BRASS, "GOLDGUINEA": "#5C4A1E", "GOLDPETAL": "#A8A29A"}

st.set_page_config(page_title="GoldLens", page_icon="🪙", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3 { font-family: 'IBM Plex Serif', Georgia, serif !important; letter-spacing: -0.01em; color: #2A2418; }
.block-container { padding-top: 2rem; max-width: 1200px; }
.verdict { border-left: 6px solid var(--c); background: #FBF6E6; padding: 1rem 1.25rem; border-radius: 0; }
.verdict .t { font-family: 'IBM Plex Serif', serif; font-size: 1.5rem; color: var(--c); margin: 0; }
.verdict .s { color: #5b5240; margin: .25rem 0 0 0; }
.warn { background: #FBF3DC; border-left: 3px solid #B8860B; padding: .6rem .9rem; color: #5b4300; }
.kpi { background: #fff; padding: .8rem .2rem .4rem; border-top: 3px solid #B8860B; }
.kpi .v { font-size: 1.6rem; font-weight: 600; color: #2A2418; } .kpi .l { color: #7A6F58; font-size: .85rem; }
</style>""", unsafe_allow_html=True)


# ---------- cached pipeline ----------
@st.cache_data(show_spinner="Loading and validating data...")
def pipeline():
    raw, source = load_data()
    clean, log = validate(raw)
    return raw, clean, log, source


@st.cache_data(show_spinner=False)
def spreads_for(clean, window):
    return build_spreads(clean, window)


@st.cache_data(show_spinner="Running walk-forward backtest...")
def run_bt(sp, costs_t, exit_z, min_dte, max_hold):
    return walk_forward(sp, costs=dict(costs_t), exit_z=exit_z, min_dte=min_dte, max_hold=max_hold)


def style(fig, h=380, title=None):
    fig.update_layout(height=h, title=title, margin=dict(l=10, r=10, t=40 if title else 10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="IBM Plex Sans, sans-serif", color=INK),
                      legend=dict(orientation="h", y=1.1, x=0))
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def kpi(col, value, label):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


def verdict_card(s):
    c = {"good": GOOD, "bad": BAD}.get(s["tone"], MIST)
    sub = (f"{s['n']} trades · {s['pos_folds']} of {s['folds']} test windows profitable · "
           f"net ₹{s['net'] * 100:,.0f} per 100 g after costs") if s["n"] else "Loosen the parameters or add more history."
    st.markdown(f'<div class="verdict" style="--c:{c}"><p class="t">{s["verdict"]}</p><p class="s">{sub}</p></div>',
                unsafe_allow_html=True)


raw, clean, log, source = pipeline()
synthetic = source.startswith("SYNTHETIC")

# ---------- sidebar ----------
st.sidebar.markdown("## GoldLens")
st.sidebar.caption("Is any gap between MCX gold contracts a real trade, or just units and expiry?")
page = st.sidebar.radio("View", ["Overview", "Data Health", "Compare", "Time Machine", "Backtest", "Alerts"],
                        label_visibility="collapsed")
dmin, dmax = clean.date.min().date(), clean.date.max().date()
asof = pd.Timestamp(st.sidebar.slider("As-of date", dmin, dmax, dmax, format="DD MMM YYYY"))
st.sidebar.caption("Everything below is computed using only data up to this date.")
with st.sidebar.expander("Cost assumptions (bps per side, per leg)"):
    costs = {s: st.slider(s, 0.0, 15.0, float(DEFAULT_COST_BPS[s]), 0.5) for s in CONTRACTS}
with st.sidebar.expander("Strategy settings"):
    exit_z = st.slider("Exit when |z| below", 0.0, 1.5, 0.5, 0.1)
    min_dte = st.slider("Close out this many days before expiry", 1, 10, 3)
    max_hold = st.slider("Max holding days", 3, 30, 15)
if synthetic:
    st.sidebar.markdown('<div class="warn"><b>Synthetic demo data.</b> Results here are not market evidence. '
                        'Put real Bhavcopy CSVs in <code>data/real/</code> to switch automatically.</div>', unsafe_allow_html=True)

visible = clean[clean.date <= asof]
sp_all = spreads_for(visible, 30)
sp = sp_all  # already truncated to as-of

# ---------- pages ----------
if page == "Overview":
    st.title("Which MCX gold contract is really mispriced?")
    st.write("GoldLens puts all four MCX gold contracts on one yardstick, rupees per gram of fine gold, "
             "then tests whether any gap survives costs on data the strategy has not seen.")
    if synthetic:
        st.markdown('<div class="warn"><b>You are looking at synthetic demo data</b> with deliberately injected data faults, '
                    'so the dashboard works offline. Swap in real Bhavcopy files for real results.</div>', unsafe_allow_html=True)
    trades, folds = run_bt(sp, tuple(costs.items()), exit_z, min_dte, max_hold)
    s = summarize(trades, folds)
    c = st.columns(4)
    kpi(c[0], f"{visible.date.nunique()}", "trading days used")
    kpi(c[1], f"{len(log[log.date <= asof])}", "data problems caught and logged")
    kpi(c[2], f"{s['n']}", "backtest trades (unseen data only)")
    kpi(c[3], f"₹{s['cost'] * 100:,.0f}", "costs paid per 100 g, all trades")
    st.write("")
    verdict_card(s)
    st.caption("An honest 'no edge survives' is a valid result. Settlement prices are benchmarks, not executable fills.")

elif page == "Data Health":
    st.title("Data health")
    st.write("Every problem found in the raw files, what we did about it, and nothing fixed silently.")
    lg = log[log.date <= asof]
    c = st.columns(3)
    kpi(c[0], f"{len(raw):,}", "raw rows loaded")
    kpi(c[1], f"{len(visible):,}", "clean rows used")
    kpi(c[2], f"{len(lg)}", "issues logged")
    st.write("")
    if len(lg):
        cnt = lg.issue.value_counts()
        fig = go.Figure(go.Bar(x=cnt.values, y=cnt.index, orientation="h", marker_color=BRASS))
        st.plotly_chart(style(fig, 260, "Issues by type"), width="stretch")
        st.dataframe(lg.assign(date=lg.date.dt.date), width="stretch", hide_index=True)
    else:
        st.success("No data problems found up to this date.")

elif page == "Compare":
    st.title("Same gold, four price tags")
    live = visible[visible.date == visible.date.max()]
    exps = sorted(live.expiry.unique())
    exp = st.selectbox("Expiry", exps, format_func=lambda d: pd.Timestamp(d).strftime("%d %b %Y"))
    day = normalize(live[live.expiry == exp]).set_index("symbol")
    tbl = pd.DataFrame({
        "Quoted price (₹)": day.settle,
        "Quoted per (g)": [CONTRACTS[s]["quote_g"] for s in day.index],
        "Purity": [CONTRACTS[s]["purity"] for s in day.index],
        "₹ per gram of fine gold": day.fine_pg.round(2),
        "Gap vs GOLDM (bps)": ((day.fine_pg / day.loc[BASE, "fine_pg"] - 1) * 1e4).round(1) if BASE in day.index else np.nan,
    })
    st.dataframe(tbl, width="stretch")
    st.caption("Raw quotes look wildly different. On the fine-gold yardstick the real gaps are a few basis points.")
    sym = st.radio("Contract to inspect against GOLDM", OTHERS, horizontal=True)
    s = sp[(sp.symbol == sym) & (sp.expiry == exp)].sort_values("date")
    if len(s):
        fig = go.Figure()
        fig.add_scatter(x=s.date, y=s.spread_bps, name="spread (bps)", line=dict(color=LINES[sym], width=2))
        fig.add_scatter(x=s.date, y=s.mean_past, name="past average", line=dict(color=MIST, dash="dot"))
        fig.add_scatter(x=s.date, y=s.mean_past + 2 * s.std_past, name="+2σ (past)", line=dict(color=GRID), showlegend=False)
        fig.add_scatter(x=s.date, y=s.mean_past - 2 * s.std_past, name="−2σ (past)", line=dict(color=GRID),
                        fill="tonexty", fillcolor="rgba(122,111,88,.12)", showlegend=False)
        st.plotly_chart(style(fig, 380, f"{sym} minus GOLDM, same expiry, fine-gold basis"), width="stretch")
        st.caption("Same-expiry contracts settle to the same gold, so gaps should shrink toward expiry.")

elif page == "Time Machine":
    st.title("Time Machine")
    st.write("Move the as-of date in the sidebar. GoldLens then sees only what was knowable that day. "
             "To prove it, we recompute today's signal from truncated data and compare with the full-history result.")
    full = spreads_for(clean, 30)
    cut = spreads_for(clean[clean.date <= asof], 30)
    a = full[full.date == cut.date.max()].set_index(["symbol", "expiry"])["z"]
    b = cut[cut.date == cut.date.max()].set_index(["symbol", "expiry"])["z"]
    j = pd.concat([a.rename("full history"), b.rename("data up to as-of")], axis=1).dropna()
    ok = bool(np.allclose(j.iloc[:, 0], j.iloc[:, 1])) if len(j) else False
    c = st.columns(3)
    kpi(c[0], asof.strftime("%d %b %Y"), "as-of date")
    kpi(c[1], f"{(clean.date > asof).sum():,}", "future rows hidden from the model")
    kpi(c[2], "Identical ✓" if ok else "MISMATCH ✗", "signal: truncated vs full history")
    st.write("")
    st.dataframe(j.round(3).reset_index().assign(expiry=lambda d: d.expiry.dt.date), width="stretch", hide_index=True)
    st.caption("If these ever differ, the model has been peeking at the future. Pytest checks this on every run.")

elif page == "Backtest":
    st.title("Walk-forward backtest")
    st.write("Each test window uses a threshold chosen only on the 150 days before it. "
             "Signals are decided at the close and traded at the next day's settlement. "
             "Profit is quoted per 100 g of fine gold, the size of one GOLDM lot.")
    trades, folds = run_bt(sp, tuple(costs.items()), exit_z, min_dte, max_hold)
    s = summarize(trades, folds)
    verdict_card(s)
    st.write("")
    if s["n"]:
        c = st.columns(4)
        kpi(c[0], f"₹{s['gross'] * 100:,.0f}", "gross P&L before costs")
        kpi(c[1], f"−₹{s['cost'] * 100:,.0f}", "costs")
        kpi(c[2], f"₹{s['net'] * 100:,.0f}", "net P&L")
        kpi(c[3], f"{s['hit']:.0%}", "winning trades")
        st.write("")
        t = trades.sort_values("exit_date")
        eq = t.net.cumsum() * 100
        fig = go.Figure(go.Scatter(x=t.exit_date, y=eq, mode="lines", line=dict(color=INK, width=2),
                                   fill="tozeroy", fillcolor="rgba(184,134,11,.10)"))
        st.plotly_chart(style(fig, 320, "Cumulative net P&L, ₹ per 100 g (unseen test windows only)"), width="stretch")
        l, r = st.columns(2)
        with l:
            by = trades.groupby("symbol")[["gross", "cost", "net"]].sum() * 100
            fig = go.Figure()
            fig.add_bar(x=by.index, y=by.gross, name="gross", marker_color=MIST)
            fig.add_bar(x=by.index, y=-by.cost, name="costs", marker_color=BAD)
            fig.add_bar(x=by.index, y=by.net, name="net", marker_color=BRASS)
            st.plotly_chart(style(fig, 300, "Where the money goes, by contract (₹ per 100 g)"), width="stretch")
        with r:
            fig = go.Figure(go.Scatter(x=trades.gold_move, y=trades.net * 100, mode="markers",
                                       marker=dict(color=BRASS, size=8, opacity=.8)))
            fig.update_xaxes(title="Gold price move during the trade (₹/g)")
            fig.update_yaxes(title="Net P&L (₹ per 100 g)")
            st.plotly_chart(style(fig, 300, "Gold-neutral check"), width="stretch")
            if pd.notna(s["gold_corr"]):
                st.caption(f"Correlation between trade P&L and gold's move: {s['gold_corr']:.2f}. "
                           "Near zero means profit is not just a bet on gold's direction.")
        st.subheader("Test windows")
        st.dataframe(folds, width="stretch", hide_index=True)
        with st.expander("All trades"):
            st.dataframe(trades.assign(entry_date=trades.entry_date.dt.date, exit_date=trades.exit_date.dt.date,
                                       expiry=trades.expiry.dt.date).round(3), width="stretch", hide_index=True)

elif page == "Alerts":
    st.title("Alerts")
    st.write("GoldLens stays quiet unless a gap is unusual, liquid enough to trade, "
             "and larger than the round-trip cost of closing it.")
    entry = st.slider("Alert when |z| above", 1.0, 4.0, 2.0, 0.1)
    last = sp[sp.date == sp.date.max()].copy()
    last["hurdle_bps"] = [2 * (costs[s] + costs[BASE]) for s in last.symbol]
    last["room_bps"] = (last.spread_bps - last.mean_past).abs()
    last["alert"] = (last.z.abs() > entry) & (~last.thin_any) & (last.dte > min_dte + 2) & (last.room_bps > last.hurdle_bps)
    hits = last[last.alert]
    if hits.empty:
        st.markdown('<div class="verdict" style="--c:#7A6F58"><p class="t">Quiet</p>'
                    '<p class="s">No real signal on this date. That is the intended behaviour.</p></div>', unsafe_allow_html=True)
    else:
        for _, r in hits.iterrows():
            act = f"short {r.symbol}, long {BASE}" if r.z > 0 else f"long {r.symbol}, short {BASE}"
            st.markdown(f'<div class="verdict" style="--c:{BRASS}"><p class="t">{r.symbol} · expiry {r.expiry:%d %b}</p>'
                        f'<p class="s">{act} · z = {r.z:.1f} · room {r.room_bps:.1f} bps vs cost hurdle {r.hurdle_bps:.1f} bps</p></div>',
                        unsafe_allow_html=True)
            st.write("")
    with st.expander("All live contracts on this date"):
        show = last[["symbol", "expiry", "dte", "spread_bps", "z", "thin_any", "hurdle_bps", "room_bps", "alert"]].copy()
        show[["spread_bps", "z", "hurdle_bps", "room_bps"]] = show[["spread_bps", "z", "hurdle_bps", "room_bps"]].round(2)
        st.dataframe(show.assign(expiry=show.expiry.dt.date), width="stretch", hide_index=True)
