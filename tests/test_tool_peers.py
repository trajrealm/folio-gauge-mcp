"""
test_tool_peers.py
------------------
Tests src/tools/peers.py (peer discovery and comparison).
Run from project root:
    uv run python tests/test_tool_peers.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  peers.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.peers import compare_to_peers, score_peer_position

comparison = compare_to_peers(TICKER, peer_count=5)

print(f"  Target Symbol:  {comparison.target_symbol}")
print(f"  Company:        {comparison.target_metrics.name}")
print(f"  Sector:         {comparison.target_metrics.sector}")
print(f"  Industry:       {comparison.target_metrics.industry}")

print()
print(f"  {'─'*56}")
print(f"  Target Metrics:")
print(f"  {'─'*56}")
print(f"  PE Ratio:       {comparison.target_metrics.pe_ratio}")
print(f"  Price/Book:     {comparison.target_metrics.price_to_book}")
print(f"  Debt/Equity:    {comparison.target_metrics.debt_to_equity}")
print(f"  Profit Margin:  {comparison.target_metrics.profit_margin}")
print(f"  Revenue Growth: {comparison.target_metrics.revenue_growth}")
print(f"  ROE:            {comparison.target_metrics.roe}")

print()
print(f"  {'─'*56}")
print(f"  Peer Averages (n={len(comparison.peers)}):")
print(f"  {'─'*56}")
print(f"  Avg PE:         {comparison.peer_avg_pe}")
print(f"  Avg Price/Book: {comparison.peer_avg_pb}")
print(f"  Avg Debt/Equity:{comparison.peer_avg_debt_equity}")

print()
print(f"  {'─'*56}")
print(f"  Target vs Peer Comparison:")
print(f"  {'─'*56}")
print(f"  PE Diff:        {comparison.target_vs_peer_pe}")
print(f"  P/B Diff:       {comparison.target_vs_peer_pb}")
print(f"  D/E Diff:       {comparison.target_vs_peer_de}")

if comparison.peers:
    print()
    print(f"  {'─'*56}")
    print(f"  Peers Found:")
    print(f"  {'─'*56}")
    for i, peer in enumerate(comparison.peers[:5], 1):
        pe = peer.pe_ratio if peer.pe_ratio is not None else "N/A"
        pb = peer.price_to_book if peer.price_to_book is not None else "N/A"
        roe = peer.roe if peer.roe is not None else "N/A"
        print(f"  [{i}] {peer.symbol:6} {peer.name[:35]}")
        print(f"      PE: {pe:8} | P/B: {pb:8} | ROE: {roe}")

# Score peer position
scores = score_peer_position(comparison)

print()
print(f"  {'─'*56}")
print(f"  Peer Position Scoring:")
print(f"  {'─'*56}")
print(f"  Valuation Score: {scores.get('valuation_score')}")
print(f"  Quality Score:   {scores.get('quality_score')}")
print(f"  Overall Score:   {scores.get('overall_score')}")

# Quick validation
none_fields = [
    k for k, v in {
        "target_symbol": comparison.target_symbol,
        "target_metrics": comparison.target_metrics,
        "peers_found": len(comparison.peers) > 0,
        "overall_score": scores.get("overall_score"),
    }.items() if not v
]

print()
if none_fields:
    print(f"  ⚠️   Issues: {none_fields}")
else:
    print(f"  ✅  All key fields returned data")
print()
