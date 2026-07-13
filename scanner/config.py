"""Central configuration for the Minervini Trend Template scanner.

Every tunable threshold lives here so strategy tweaks never touch logic.
"""
from dataclasses import dataclass, field


@dataclass
class Config:
    # Moving averages — Minervini's book uses simple MAs; the Chartink
    # reference screener uses EMAs. Toggle here.
    ma_type: str = "sma"  # "sma" | "ema"

    # Condition thresholds
    pct_above_52w_low: float = 0.30   # condition 6: >= 30% above 52-week low
    pct_from_52w_high: float = 0.25   # condition 7: within 25% of 52-week high
    rs_min: int = 70                  # condition 8: RS percentile rank
    volume_condition_enabled: bool = True  # condition 9 (Chartink volume clause)
    volume_ema_days: int = 20

    # Condition 3: MA200 rising over this lookback (~1 month of sessions),
    # with a "preferred" bonus flag at ~5 months.
    ma200_trend_days: int = 21
    ma200_trend_pref_days: int = 105

    # RS rating: IBD-style weighted 12-month return
    rs_weights: dict = field(default_factory=lambda: {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2})

    # Universe quality filter (user wants the low-priced names too — $1 floor).
    # Volume floor is against Alpaca's free IEX feed, which reports only a few
    # percent of consolidated volume: 15k IEX shares ~ several hundred k real.
    min_price: float = 1.0
    min_avg_volume: float = 15_000
    avg_volume_days: int = 30

    # Cups below this confidence are dropped from the report entirely
    # (keeps latest.json small and the dashboard readable)
    report_cup_min_confidence: float = 0.5
    # Cups below this confidence never make the alert email
    email_cup_min_confidence: float = 0.65
    # Each email section lists at most this many rows (rest: "N more on dashboard")
    email_max_rows_per_section: int = 25

    # Near-miss tab: passing all but this many conditions
    near_miss_max_failures: int = 1

    # Cup / cheat-entry detection
    cup_min_depth: float = 0.12       # correction must be >= 12%
    cup_max_depth: float = 0.50       # ... and <= 50%
    cup_min_length: int = 30          # >= ~6 weeks of sessions lip-to-now
    cup_max_length: int = 325         # <= ~65 weeks
    cup_min_bottom_span: int = 5      # sessions within 5% of low (rejects V bottoms)
    plateau_min_days: int = 3
    plateau_max_range: float = 0.08   # high/low span of the pause
    plateau_volume_contraction: float = 0.85  # plateau vol vs cup avg vol


DEFAULT = Config()
