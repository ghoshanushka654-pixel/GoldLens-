# GoldLens

**Which MCX gold contract is really mispriced?**
Team NYX, Hack in Hills '26 (Track 3: Commodity Derivatives Intelligence).

MCX lists gold futures in four sizes (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL) with different quote units, purities
and expiries. GoldLens puts them on one yardstick (Rs per gram of fine gold), logs data faults, and tests
whether any gap survives costs in a walk-forward backtest. An honest "no edge" is a valid result.

## Two ways to run it

**1. Front end only (no install).** Open `docs/index.html` in a browser, or serve it:
```
cd docs
python -m http.server 8000      # then visit http://localhost:8000
```
Sign in or continue as a guest. Screens: Dashboard (Time Machine), Converter, Trade check, Upload data, Alerts, Account.
Sign-in is a demo that stores details in the browser only.

**2. Full Python app (Streamlit) and tests.**
```
python -m venv venv
venv\Scripts\activate           # Windows (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q             # 10 tests
```

## Data
Runs on SYNTHETIC demo data (clearly labelled, with deliberately injected faults) until you add real data.
To use real MCX Bhavcopy files, put one CSV per trading day in `data/real/`, with the date in the file name
(e.g. `bhavcopy_2025-06-30.csv`). If columns are not recognised, add the real names to `ALIASES` in `src/loader.py`.
Check `src/config.py` (lot size, quote unit, purity, costs) against the official MCX contract specifications.
After changing data, regenerate the front end with `python build_front.py`.

## Layout
- `src/` data loading, validation, normalisation, signals, backtest
- `app.py` Streamlit dashboard
- `front_template.html`, `build_front.py` build the static front end into `docs/index.html`
- `tests/` automated tests (unit conversion, wrong-date rejection, no look-ahead, costs, walk-forward windows)

## Honest limits
Settlement prices are benchmarks, not fills. Costs are assumptions. GOLDTEN history starts April 2025.
Volume is not depth. Results on synthetic data demonstrate the machinery, not a market edge.
