"""Generate a DEMO PDF with synthetic but realistic-looking data.
Use this only when you have no internet access. The main entry point
money_flow_report.py fetches real data via yfinance.
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from money_flow_report import SECTORS, MarketSnapshot, build_pdf

rng = np.random.default_rng(7)
idx = pd.date_range(end=datetime.utcnow(), periods=180, freq="B")


def synth(start: float, drift: float = 0.0005, vol: float = 0.01) -> pd.Series:
    r = rng.normal(drift, vol, size=len(idx))
    return pd.Series(start * np.exp(np.cumsum(r)), index=idx)


prices = pd.DataFrame({
    "SPY":       synth(450,    0.0008,  0.009),
    "TLT":       synth(95,    -0.0003,  0.008),
    "GLD":       synth(190,    0.0006,  0.009),
    "SLV":       synth(22,     0.0004,  0.014),
    "HYG":       synth(78,     0.0004,  0.005),
    "DX-Y.NYB":  synth(104,   -0.0002,  0.004),
    "^VIX":      synth(15,    -0.0001,  0.040),
    "BTC-USD":   synth(60000,  0.0020,  0.030),
    "ETH-USD":   synth(3000,   0.0015,  0.035),
    "^TNX":      synth(42,    -0.0001,  0.010),
    "HG=F":      synth(4.2,    0.0007,  0.012),
})
sector_drifts = {
    "XLK": 0.0010, "XLC": 0.0009, "XLY": 0.0007, "XLI": 0.0006,
    "XLF": 0.0005, "XLB": 0.0004, "XLV": 0.0002, "XLRE": 0.0001,
    "XLE": -0.0001, "XLP": -0.0002, "XLU": -0.0003,
}
sectors = pd.DataFrame({
    s: synth(100, sector_drifts.get(s, 0.0003), 0.012) for s in SECTORS
})

snap = MarketSnapshot(prices=prices, sectors=sectors,
                     start=idx[0].to_pydatetime(),
                     end=idx[-1].to_pydatetime())

out = Path("demo_money_flow_report.pdf")
build_pdf(snap, out, demo=True)
print(f"Demo-PDF erstellt: {out.resolve()} ({out.stat().st_size // 1024} KB)")
