# Money-Flow-Report

Generiert einen PDF-Bericht (4–5 Seiten) der zeigt, wohin gerade Geld am
Finanzmarkt rotiert: zwischen Aktien, Bonds, Edelmetallen, Krypto und
einzelnen Sektoren.

## Was die PDF enthält

1. **Deckblatt** mit Risk-On / Risk-Off / Mixed Ampel + aktuelle Signale
2. **Asset-Klassen-Rotation** — 6 normierte Ratio-Charts
   (SPY/TLT, SPY/GLD, GLD/SLV, BTC/GLD, HYG/TLT, Kupfer/Gold)
3. **Sektor-Rotation** — Bar-Chart 1M-Performance + Heatmap (1W/1M/3M)
4. **Krypto & Edelmetalle** — BTC, ETH, Gold, Silber
5. **Macro-Indikatoren** — 10Y-Yield, DXY, VIX, Kupfer

## Installation

```bash
pip install -r requirements.txt
```

## Verwendung

```bash
# Standard: 180 Tage Rückblick, speichert money_flow_report.pdf
python money_flow_report.py

# Eigener Pfad und längerer Zeitraum
python money_flow_report.py --output reports/2026-05-13.pdf --lookback 365
```

## Datenquelle

Alle Daten kommen kostenlos über `yfinance` von Yahoo Finance. Keine API-Keys
nötig. Lauflänge typisch 20–60 Sekunden je nach Verbindung.

## Hinweise

- Reine Information, **keine Anlageberatung**.
- Kurse können zeitverzögert sein (typ. 15 Min für Aktien, live für Krypto).
- Bei Wochenenden/Feiertagen bleiben die letzten Werte stehen.
