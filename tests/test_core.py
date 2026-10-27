import numpy as np
import pandas as pd
import pytest
from src.config import CONTRACTS
from src.normalize import fine_price_per_gram
from src.data_gen import make_synthetic
from src.validate import validate
from src.signals import build_spreads
from src.backtest import simulate, walk_forward


@pytest.fixture(scope="module")
def data():
    raw = make_synthetic()
    clean, log = validate(raw)
    return raw, clean, log


def test_unit_and_purity_conversion():
    # 10 g of 995 gold quoted at Rs 88,500 -> per gram of fine gold
    assert fine_price_per_gram(88500, "GOLDM") == pytest.approx(88500 / 10 / 0.995)
    assert fine_price_per_gram(8900, "GOLDPETAL") == pytest.approx(8900 / 0.999)
    assert fine_price_per_gram(71200, "GOLDGUINEA") == pytest.approx(71200 / 8 / 0.999)


def test_same_gold_same_fine_price():
    fine = 9000.0
    for s, c in CONTRACTS.items():
        quoted = fine * c["purity"] / 1000 * c["quote_g"]
        assert fine_price_per_gram(quoted, s) == pytest.approx(fine)


def test_wrong_date_is_rejected_and_logged(data):
    raw, clean, log = data
    assert (log.issue == "WRONG_DATE").sum() == 5
    bad_days = log[log.issue == "WRONG_DATE"].date
    assert not clean.date.isin(bad_days).any()


def test_unit_outliers_dropped(data):
    _, clean, log = data
    assert (log.issue == "UNIT_OUTLIER").sum() == 2


def test_thin_contracts_flagged_not_hidden(data):
    _, clean, _ = data
    assert clean.thin.any()


def test_goldten_not_before_listing(data):
    _, clean, _ = data
    assert clean[clean.symbol == "GOLDTEN"].date.min() >= pd.Timestamp("2025-04-01")


def test_no_look_ahead_in_signal(data):
    """Changing FUTURE data must not change any past z-score."""
    _, clean, _ = data
    cutoff = clean.date.sort_values().unique()[300]
    base = build_spreads(clean).set_index(["symbol", "expiry", "date"])["z"]
    tampered = clean.copy()
    tampered.loc[tampered.date > cutoff, "settle"] *= 1.3
    alt = build_spreads(tampered).set_index(["symbol", "expiry", "date"])["z"]
    past = base.index.get_level_values("date") <= cutoff
    assert np.allclose(base[past].dropna(), alt.reindex(base.index)[past].dropna())


def test_costs_are_deducted(data):
    _, clean, _ = data
    sp = build_spreads(clean)
    t = simulate(sp)
    assert len(t) > 0
    assert (t.cost > 0).all()
    assert np.allclose(t.net, t.gross - t.cost)


def test_higher_costs_never_improve_result(data):
    _, clean, _ = data
    sp = build_spreads(clean)
    lo = simulate(sp, costs={"GOLDM": 1, "GOLDTEN": 1, "GOLDGUINEA": 1, "GOLDPETAL": 1}).net.sum()
    hi = simulate(sp, costs={"GOLDM": 8, "GOLDTEN": 8, "GOLDGUINEA": 8, "GOLDPETAL": 8}).net.sum()
    assert hi < lo


def test_walk_forward_test_windows_do_not_overlap(data):
    _, clean, _ = data
    trades, folds = walk_forward(build_spreads(clean))
    ends = pd.to_datetime(folds.test.str.split(" to ").str[1])
    starts = pd.to_datetime(folds.test.str.split(" to ").str[0])
    assert (starts.iloc[1:].values > ends.iloc[:-1].values).all()
