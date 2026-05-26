"""
test_tool_technical.py
----------------------
Tests src/tools/technical.py (yfinance + pandas_ta technical indicators).
Run from project root:
    uv run python tests/test_tool_technical.py

No API key required. No rate limits. Should complete in ~2-3 seconds.
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  technical.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.technical import get_technical_snapshot, get_ohlcv_history

# ---------------------------------------------------------------------------
# Technical snapshot (single yfinance call)
# ---------------------------------------------------------------------------

print(f"  Fetching technical snapshot (1 API call)...")
snap = get_technical_snapshot(TICKER)

print(f"\n  {'─'*56}")
print(f"  Technical Snapshot")
print(f"  {'─'*56}")
print(f"  Symbol:          {snap.symbol}")
print(f"  Price:           {'${:.2f}'.format(snap.price) if snap.price else 'N/A'}")
print(f"  SMA 20:          {'${:.2f}'.format(snap.sma_20) if snap.sma_20 else 'N/A'}")
print(f"  SMA 50:          {'${:.2f}'.format(snap.sma_50) if snap.sma_50 else 'N/A'}")
print(f"  SMA 200:         {'${:.2f}'.format(snap.sma_200) if snap.sma_200 else 'N/A'}")
print(f"  RSI 14:          {'{:.2f}'.format(snap.rsi_14) if snap.rsi_14 else 'N/A'}")
print(f"  MACD:            {'{:.4f}'.format(snap.macd_value) if snap.macd_value else 'N/A'}")
print(f"  MACD Signal:     {'{:.4f}'.format(snap.macd_signal) if snap.macd_signal else 'N/A'}")
print(f"  MACD Histogram:  {'{:.4f}'.format(snap.macd_histogram) if snap.macd_histogram else 'N/A'}")
print(f"  Fetched At:      {snap.fetched_at}")

# Quick interpretation hints
if snap.price and snap.sma_20 and snap.sma_50:
    above_20 = snap.price > snap.sma_20
    above_50 = snap.price > snap.sma_50
    above_200 = snap.price > snap.sma_200 if snap.sma_200 else None
    print(f"\n  Price vs SMAs:   {'above' if above_20 else 'below'} SMA20 | "
          f"{'above' if above_50 else 'below'} SMA50"
          + (f" | {'above' if above_200 else 'below'} SMA200" if above_200 is not None else ""))

if snap.rsi_14:
    if snap.rsi_14 > 70:
        print(f"  RSI {snap.rsi_14:.1f}:         Overbought (>70)")
    elif snap.rsi_14 < 30:
        print(f"  RSI {snap.rsi_14:.1f}:         Oversold (<30)")
    else:
        print(f"  RSI {snap.rsi_14:.1f}:        Neutral (30-70)")

if snap.macd_value and snap.macd_signal:
    print(f"  MACD vs Signal:  {'bullish crossover' if snap.macd_value > snap.macd_signal else 'bearish crossover'}")

# ---------------------------------------------------------------------------
# OHLCV history (same single yfinance call, just different function)
# ---------------------------------------------------------------------------

print(f"\n  {'─'*56}")
print(f"  OHLCV History (last 10 trading days)")
print(f"  {'─'*56}")

candles = get_ohlcv_history(TICKER, period="1mo")
recent = candles[-10:] if len(candles) >= 10 else candles

for c in recent:
    vol_str = f"{c.volume:,.0f}" if c.volume else "N/A"
    print(f"  {c.timestamp}  O:{c.open:>8.2f}  H:{c.high:>8.2f}  "
          f"L:{c.low:>8.2f}  C:{c.close:>8.2f}  V:{vol_str:>14}")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

validation = {
    "price_returned":     snap.price is not None,
    "sma_20_returned":    snap.sma_20 is not None,
    "sma_50_returned":    snap.sma_50 is not None,
    "sma_200_returned":   snap.sma_200 is not None,
    "rsi_14_returned":    snap.rsi_14 is not None,
    "macd_returned":      snap.macd_value is not None,
    "macd_signal_returned": snap.macd_signal is not None,
    "candles_returned":   len(candles) > 0,
    "fetched_at_present": bool(snap.fetched_at),
    "symbol_correct":     snap.symbol == TICKER,
}

issues = [k for k, v in validation.items() if not v]

print()
print(f"  {'─'*56}")
if issues:
    print(f"  ⚠️   Issues:")
    for issue in issues:
        print(f"        - {issue}")
else:
    print(f"  ✅  All key fields returned data")
print()