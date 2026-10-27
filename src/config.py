"""Contract specs and cost assumptions. EDIT THESE after checking the official MCX contract specs."""

# lot_g   = grams in one lot
# quote_g = grams the quoted price refers to (price is Rs per quote_g grams)
# purity  = fineness (995 -> 99.5% gold)
CONTRACTS = {
    "GOLDM":      dict(lot_g=100, quote_g=10, purity=995, listed="2000-01-01"),
    "GOLDTEN":    dict(lot_g=10,  quote_g=10, purity=999, listed="2025-04-01"),
    "GOLDGUINEA": dict(lot_g=8,   quote_g=8,  purity=999, listed="2000-01-01"),
    "GOLDPETAL":  dict(lot_g=1,   quote_g=1,  purity=999, listed="2000-01-01"),
}
BASE = "GOLDM"                      # most liquid contract, used as the reference
OTHERS = [s for s in CONTRACTS if s != BASE]

# Assumed cost per side per leg, in basis points of notional (brokerage + exchange fees + taxes + slippage).
# These are ASSUMPTIONS, adjustable in the app. Thin contracts get a higher slippage guess.
DEFAULT_COST_BPS = {"GOLDM": 1.5, "GOLDTEN": 2.5, "GOLDGUINEA": 4.0, "GOLDPETAL": 6.0}

MIN_VOLUME_LOTS = 50       # below this a contract-day is flagged as thin
UNIT_OUTLIER_PCT = 0.05    # >5% away from the day's median fine-gold price = suspected unit error
