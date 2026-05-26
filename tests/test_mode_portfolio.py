"""
tests/test_mode_portfolio.py
Test Portfolio Mode

Tests portfolio CSV analysis with per-holding recommendations.
Run with: python tests/test_mode_portfolio.py
"""

from dotenv import load_dotenv
load_dotenv()  
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.orchestrator.aggregator import orchestrate_analysis


def test_portfolio_mode():
    """
    Test portfolio mode: Analyze multiple holdings from CSV.
    """
    
    print("\n" + "="*70)
    print("🧪 PORTFOLIO MODE TEST (Multi-Holding Analysis)")
    print("="*70 + "\n")
    
    # Sample portfolio (in real use, load from CSV)
    portfolio = [
        {"symbol": "AAPL", "qty": 50, "avg_cost": 150.00, "type": "long"},
        {"symbol": "MSFT", "qty": 20, "avg_cost": 310.00, "type": "long"},
        {"symbol": "NVDA", "qty": 10, "avg_cost": 420.00, "type": "long"},
    ]
    
    print(f"📋 Portfolio: {len(portfolio)} holdings\n")
    
    results = []
    
    for holding in portfolio:
        ticker = holding["symbol"]
        qty = holding["qty"]
        avg_cost = holding["avg_cost"]
        
        print(f"📊 Analyzing {ticker} ({qty} shares @ ${avg_cost:.2f})...")
        print("-" * 70)
        
        try:
            # Analyze ticker (same as individual mode)
            result = orchestrate_analysis(ticker)
            
            # Generate recommendation
            if result.decision == "BUY":
                rec = "ACCUMULATE"
                action = f"Add {int(qty * 0.2)} more shares"
            elif result.decision == "SELL":
                rec = "TRIM"
                action = f"Reduce by {int(qty * 0.3)} shares"
            else:
                rec = "HOLD"
                action = "No change"
            
            results.append({
                "symbol": ticker,
                "decision": result.decision,
                "recommendation": rec,
                "action": action,
                "score": result.weighted_score,
                "confidence": result.confidence,
            })
            
            print(f"  Current Decision: {result.decision}")
            print(f"  Recommendation:   {rec}")
            print(f"  Action:           {action}")
            print(f"  Confidence:       {result.confidence:.0%}\n")
        
        except Exception as e:
            print(f"  ❌ Error: {str(e)}\n")
    
    # Summary
    print("\n" + "="*70)
    print("📈 PORTFOLIO RECOMMENDATIONS SUMMARY")
    print("="*70 + "\n")
    
    for r in results:
        print(f"{r['symbol']:<8} {r['recommendation']:<12} {r['action']:<30} ({r['confidence']:.0%})")
    
    print("\n" + "="*70)
    print("✅ PORTFOLIO MODE TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_portfolio_mode()
