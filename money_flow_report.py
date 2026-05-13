"""
Money-Flow-Report Generator
Fetches market data via yfinance, computes rotation ratios, builds charts,
and renders a 4-5 page PDF report showing where money is flowing.

Usage:
    python money_flow_report.py [--output report.pdf] [--lookback 180]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec


TICKERS = {
    "SPY": "S&P 500 (Aktien)",
    "TLT": "20Y Treasuries (Bonds)",
    "GLD": "Gold",
    "SLV": "Silber",
    "HYG": "High-Yield Bonds",
    "DX-Y.NYB": "US-Dollar-Index (DXY)",
    "^VIX": "VIX (Angstindex)",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "^TNX": "10Y Treasury Yield",
    "HG=F": "Kupfer Futures",
}

SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLY": "Consumer Disc.",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication",
}

RATIOS = [
    ("SPY", "TLT", "Aktien vs. Bonds", "↑ = Risk-On (raus aus Bonds)"),
    ("SPY", "GLD", "Aktien vs. Gold", "↑ = Risk-On (raus aus Gold)"),
    ("GLD", "SLV", "Gold vs. Silber", "↑ = Angst steigt"),
    ("BTC-USD", "GLD", "Bitcoin vs. Gold", "↑ = spekulatives Geld in Krypto"),
    ("HYG", "TLT", "Junk vs. Treasuries", "↑ = Risikoappetit hoch"),
    ("HG=F", "GLD", "Kupfer vs. Gold", "↑ = Wachstumserwartung"),
]


@dataclass
class MarketSnapshot:
    prices: pd.DataFrame
    sectors: pd.DataFrame
    start: datetime
    end: datetime


def fetch_data(lookback_days: int) -> MarketSnapshot:
    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)
    all_tickers = list(TICKERS.keys()) + list(SECTORS.keys())

    print(f"Lade Daten für {len(all_tickers)} Ticker ({start.date()} → {end.date()})…")
    raw = yf.download(
        all_tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )

    closes = {}
    for t in all_tickers:
        try:
            if (t, "Close") in raw.columns:
                closes[t] = raw[(t, "Close")]
            elif t in raw.columns.get_level_values(0):
                closes[t] = raw[t]["Close"]
        except Exception:
            continue

    df = pd.DataFrame(closes).dropna(how="all").ffill()
    prices = df[[c for c in TICKERS if c in df.columns]]
    sectors = df[[c for c in SECTORS if c in df.columns]]
    return MarketSnapshot(prices=prices, sectors=sectors, start=start, end=end)


def perf(series: pd.Series, days: int) -> float:
    if len(series) < days + 1:
        return float("nan")
    return float(series.iloc[-1] / series.iloc[-days - 1] - 1.0) * 100.0


def classify_regime(snap: MarketSnapshot) -> tuple[str, str, list[str]]:
    p = snap.prices
    signals = []

    def trend(symbol: str, window: int = 20) -> float:
        if symbol not in p.columns or len(p[symbol].dropna()) < window:
            return 0.0
        s = p[symbol].dropna()
        return float(s.iloc[-1] / s.iloc[-window] - 1.0)

    spy_tlt = trend("SPY") - trend("TLT")
    spy_gld = trend("SPY") - trend("GLD")
    btc_gld = trend("BTC-USD") - trend("GLD")
    dxy = trend("DX-Y.NYB")
    vix_now = float(p["^VIX"].iloc[-1]) if "^VIX" in p.columns else 0.0

    score = 0
    if spy_tlt > 0: score += 1; signals.append("Aktien schlagen Bonds (SPY/TLT ▲)")
    else: score -= 1; signals.append("Bonds schlagen Aktien (SPY/TLT ▼)")

    if spy_gld > 0: score += 1; signals.append("Aktien schlagen Gold (SPY/GLD ▲)")
    else: score -= 1; signals.append("Gold schlägt Aktien (SPY/GLD ▼)")

    if btc_gld > 0: score += 1; signals.append("Krypto schlägt Gold (BTC/GLD ▲)")
    else: signals.append("Gold schlägt Krypto (BTC/GLD ▼)")

    if vix_now < 18: score += 1; signals.append(f"VIX niedrig ({vix_now:.1f})")
    elif vix_now > 25: score -= 1; signals.append(f"VIX erhöht ({vix_now:.1f})")
    else: signals.append(f"VIX neutral ({vix_now:.1f})")

    if dxy > 0.02: signals.append(f"Dollar stark (DXY +{dxy*100:.1f}%)")
    elif dxy < -0.02: signals.append(f"Dollar schwach (DXY {dxy*100:.1f}%)")

    if score >= 2:
        regime, color = "RISK-ON", "#1a8a3a"
    elif score <= -2:
        regime, color = "RISK-OFF", "#c0392b"
    else:
        regime, color = "MIXED / NEUTRAL", "#d4a017"
    return regime, color, signals


def page_cover(pdf: PdfPages, snap: MarketSnapshot) -> None:
    regime, color, signals = classify_regime(snap)
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("Money-Flow-Report", fontsize=26, fontweight="bold", y=0.95)

    ax = fig.add_axes([0.1, 0.0, 0.8, 0.85])
    ax.axis("off")

    ax.text(0.5, 0.92, f"Stand: {snap.end.strftime('%d.%m.%Y')}",
            ha="center", fontsize=12, color="#555")
    ax.text(0.5, 0.87, f"Zeitraum: letzte {(snap.end - snap.start).days} Tage",
            ha="center", fontsize=10, color="#777")

    ax.add_patch(plt.Rectangle((0.15, 0.65), 0.7, 0.15, facecolor=color, alpha=0.85))
    ax.text(0.5, 0.725, regime, ha="center", va="center",
            fontsize=28, fontweight="bold", color="white")

    ax.text(0.5, 0.58, "Aktuelle Marktsignale", ha="center", fontsize=14, fontweight="bold")
    for i, s in enumerate(signals):
        ax.text(0.1, 0.52 - i * 0.04, f"• {s}", fontsize=11)

    ax.text(0.5, 0.18, "Inhalt", ha="center", fontsize=14, fontweight="bold")
    toc = [
        "1. Asset-Klassen-Rotation (Ratios)",
        "2. Sektor-Rotation (Aktien)",
        "3. Krypto & Edelmetalle",
        "4. Macro-Indikatoren",
    ]
    for i, t in enumerate(toc):
        ax.text(0.2, 0.13 - i * 0.025, t, fontsize=10)

    ax.text(0.5, 0.02, "Datenquelle: Yahoo Finance | Erstellt mit Python/matplotlib",
            ha="center", fontsize=8, color="#999")
    pdf.savefig(fig); plt.close(fig)


def page_ratios(pdf: PdfPages, snap: MarketSnapshot) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("1. Asset-Klassen-Rotation", fontsize=18, fontweight="bold", y=0.97)
    gs = GridSpec(3, 2, figure=fig, top=0.92, bottom=0.05, hspace=0.5, wspace=0.3)

    for i, (a, b, title, hint) in enumerate(RATIOS):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        if a not in snap.prices.columns or b not in snap.prices.columns:
            ax.text(0.5, 0.5, "n/a", ha="center", va="center"); ax.axis("off"); continue
        ratio = (snap.prices[a] / snap.prices[b]).dropna()
        norm = ratio / ratio.iloc[0] * 100
        ax.plot(norm.index, norm.values, linewidth=1.5, color="#2c3e50")
        ax.axhline(100, color="#aaa", linestyle="--", linewidth=0.7)
        change = norm.iloc[-1] - 100
        col = "#1a8a3a" if change > 0 else "#c0392b"
        ax.fill_between(norm.index, 100, norm.values,
                        where=(norm.values >= 100), color="#1a8a3a", alpha=0.15)
        ax.fill_between(norm.index, 100, norm.values,
                        where=(norm.values < 100), color="#c0392b", alpha=0.15)
        ax.set_title(f"{a}/{b} — {title}", fontsize=10, fontweight="bold")
        ax.text(0.02, 0.95, f"{change:+.1f}%", transform=ax.transAxes,
                fontsize=11, fontweight="bold", color=col, va="top")
        ax.text(0.02, 0.05, hint, transform=ax.transAxes, fontsize=7, color="#666")
        ax.tick_params(axis="x", labelsize=7, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(alpha=0.2)
    pdf.savefig(fig); plt.close(fig)


def page_sectors(pdf: PdfPages, snap: MarketSnapshot) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("2. Sektor-Rotation (Aktien)", fontsize=18, fontweight="bold", y=0.97)

    perf_table = {}
    for sym in snap.sectors.columns:
        s = snap.sectors[sym].dropna()
        perf_table[sym] = {
            "1W": perf(s, 5),
            "1M": perf(s, 21),
            "3M": perf(s, 63),
        }
    df = pd.DataFrame(perf_table).T
    df["Name"] = [SECTORS.get(i, i) for i in df.index]
    df = df.sort_values("1M", ascending=True)

    ax1 = fig.add_axes([0.12, 0.55, 0.78, 0.35])
    colors = ["#1a8a3a" if v > 0 else "#c0392b" for v in df["1M"]]
    ax1.barh(df["Name"], df["1M"], color=colors, alpha=0.8)
    ax1.set_title("1-Monats-Performance der GICS-Sektoren", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Performance %", fontsize=9)
    ax1.axvline(0, color="#333", linewidth=0.7)
    ax1.grid(axis="x", alpha=0.2)
    ax1.tick_params(labelsize=8)

    ax2 = fig.add_axes([0.12, 0.08, 0.78, 0.38])
    heat = df[["1W", "1M", "3M"]].values
    im = ax2.imshow(heat, cmap="RdYlGn", aspect="auto", vmin=-15, vmax=15)
    ax2.set_yticks(range(len(df))); ax2.set_yticklabels(df["Name"], fontsize=8)
    ax2.set_xticks([0, 1, 2]); ax2.set_xticklabels(["1 Woche", "1 Monat", "3 Monate"], fontsize=9)
    ax2.set_title("Performance-Heatmap (% Veränderung)", fontsize=11, fontweight="bold")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            v = heat[i, j]
            if not np.isnan(v):
                ax2.text(j, i, f"{v:+.1f}", ha="center", va="center",
                         fontsize=8, color="black")
    fig.colorbar(im, ax=ax2, orientation="vertical", fraction=0.04, pad=0.02)
    pdf.savefig(fig); plt.close(fig)


def page_crypto_metals(pdf: PdfPages, snap: MarketSnapshot) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("3. Krypto & Edelmetalle", fontsize=18, fontweight="bold", y=0.97)
    gs = GridSpec(2, 2, figure=fig, top=0.9, bottom=0.08, hspace=0.4, wspace=0.3)

    pairs = [
        ("BTC-USD", "Bitcoin (USD)"),
        ("ETH-USD", "Ethereum (USD)"),
        ("GLD", "Gold ETF (GLD)"),
        ("SLV", "Silber ETF (SLV)"),
    ]
    for i, (sym, label) in enumerate(pairs):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        if sym not in snap.prices.columns:
            ax.text(0.5, 0.5, "n/a", ha="center", va="center"); ax.axis("off"); continue
        s = snap.prices[sym].dropna()
        norm = s / s.iloc[0] * 100
        change = norm.iloc[-1] - 100
        col = "#1a8a3a" if change > 0 else "#c0392b"
        ax.plot(norm.index, norm.values, color=col, linewidth=1.6)
        ax.fill_between(norm.index, 100, norm.values, color=col, alpha=0.15)
        ax.axhline(100, color="#aaa", linestyle="--", linewidth=0.7)
        ax.set_title(label, fontsize=10, fontweight="bold")
        ax.text(0.02, 0.95, f"{change:+.1f}%", transform=ax.transAxes,
                fontsize=12, fontweight="bold", color=col, va="top")
        ax.tick_params(axis="x", labelsize=7, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(alpha=0.2)
    pdf.savefig(fig); plt.close(fig)


def page_macro(pdf: PdfPages, snap: MarketSnapshot) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("4. Macro-Indikatoren", fontsize=18, fontweight="bold", y=0.97)
    gs = GridSpec(2, 2, figure=fig, top=0.9, bottom=0.08, hspace=0.4, wspace=0.3)

    items = [
        ("^TNX", "10Y Treasury Yield"),
        ("DX-Y.NYB", "US-Dollar-Index (DXY)"),
        ("^VIX", "VIX (Angstindex)"),
        ("HG=F", "Kupfer (Konjunktur)"),
    ]
    for i, (sym, label) in enumerate(items):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        if sym not in snap.prices.columns:
            ax.text(0.5, 0.5, "n/a", ha="center", va="center"); ax.axis("off"); continue
        s = snap.prices[sym].dropna()
        ax.plot(s.index, s.values, color="#2c3e50", linewidth=1.4)
        ax.fill_between(s.index, s.min(), s.values, color="#3498db", alpha=0.12)
        ax.set_title(label, fontsize=10, fontweight="bold")
        ax.text(0.02, 0.95, f"aktuell: {s.iloc[-1]:.2f}",
                transform=ax.transAxes, fontsize=10, fontweight="bold", va="top")
        ax.tick_params(axis="x", labelsize=7, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(alpha=0.2)

    fig.text(0.1, 0.04,
             "Lesart: Steigende Yields + starker DXY → Druck auf Gold/Krypto/EM. "
             "Steigender VIX → Risk-Off. Kupfer als Konjunktur-Frühindikator.",
             fontsize=8, color="#555", wrap=True)
    pdf.savefig(fig); plt.close(fig)


def build_pdf(snap: MarketSnapshot, output: Path) -> None:
    with PdfPages(output) as pdf:
        page_cover(pdf, snap)
        page_ratios(pdf, snap)
        page_sectors(pdf, snap)
        page_crypto_metals(pdf, snap)
        page_macro(pdf, snap)
        pdf.infodict()["Title"] = "Money-Flow-Report"
        pdf.infodict()["Author"] = "money_flow_report.py"
        pdf.infodict()["CreationDate"] = datetime.utcnow()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a money-flow PDF report.")
    parser.add_argument("--output", default="money_flow_report.pdf", type=Path)
    parser.add_argument("--lookback", default=180, type=int,
                        help="Lookback in days (default: 180)")
    args = parser.parse_args()

    snap = fetch_data(args.lookback)
    if snap.prices.empty:
        print("FEHLER: Keine Daten geladen.", file=sys.stderr)
        return 1
    print(f"Erstelle PDF: {args.output}")
    build_pdf(snap, args.output)
    print(f"Fertig. {args.output} ({args.output.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
