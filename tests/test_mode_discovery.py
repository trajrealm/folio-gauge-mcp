"""
tests/test_mode_discovery.py
Test Discovery Mode (Two-Phase)

Phase 1: Discovery agent identifies trending candidates from social sentiment
Phase 2: 9 core analysts evaluate shortlist
Run with: python tests/test_mode_discovery.py
"""

from dotenv import load_dotenv
from src.analysts.discovery import discover_candidates
from src.analysts.portfolio import analyze_portfolio
from src.orchestrator.aggregator import orchestrate_analysis

load_dotenv()

def test_discovery_mode():
    """
    Test discovery mode: Two-phase candidate discovery and evaluation.
    """
    
    print("\n" + "="*70)
    print("🧪 DISCOVERY MODE TEST (Two-Phase)")
    print("="*70 + "\n")
    
    # ========================================================================
    # PHASE 1: SEQUENTIAL FILTERING
    # ========================================================================
    
    print("📍 PHASE 1: DISCOVERY")
    print("-" * 70 + "\n")
    
    print("Step 1️⃣  — Discovery Agent: Find trending candidates")
    print("         Scanning Reddit, StockTwits for trending stocks...\n")
    
    try:
        discovery_result = discover_candidates(limit=3)
        shortlist = discovery_result.candidates
        
        print(f"  ✅ Discovery completed")
        print(f"     Found {len(shortlist)} candidates")
        print(f"     Reasoning: {discovery_result.reasoning}")
        print(f"     Confidence: {discovery_result.confidence:.0%}")
        print(f"     Sources: Reddit={len(discovery_result.sources.get('reddit', []))} " +
              f"StockTwits={len(discovery_result.sources.get('stocktwits', []))}\n")
        
    except Exception as e:
        print(f"  ⚠️  Discovery agent error: {str(e)}")
        shortlist = ["NVDA", "COIN", "SOFI"]
        print(f"     Using fallback candidates: {shortlist}\n")
    
    print(f"Step 2️⃣  — Portfolio Agent: Evaluate portfolio impact")
    print(f"         Checking diversification of candidates...\n")
    
    try:
        portfolio_holdings = [
            {"symbol": ticker, "weight": 1.0 / len(shortlist)}
            for ticker in shortlist
        ]
        portfolio_result = analyze_portfolio(portfolio_holdings)
        
        print(f"  ✅ Portfolio evaluation completed")
        print(f"     Decision: {portfolio_result.decision}")
        print(f"     Reasoning: {portfolio_result.reasoning}\n")
    
    except Exception as e:
        print(f"  ⚠️  Portfolio agent error: {str(e)}")
        print(f"     Proceeding with candidates: {shortlist}\n")
    
    print(f"Step 3️⃣  — Result: Shortlisted candidates")
    print(f"         Ready for Phase 2 analysis\n")
    print(f"  Candidates: {', '.join(shortlist)}\n")
    
    # ========================================================================
    # PHASE 2: PARALLEL ANALYSIS ON SHORTLIST
    # ========================================================================
    
    print("\n" + "-" * 70)
    print("📍 PHASE 2: PARALLEL ANALYSIS ON SHORTLIST")
    print("-" * 70 + "\n")
    
    print("Calling 9 core analysts on each shortlisted ticker...\n")
    
    discovery_recommendations = []
    
    for ticker in shortlist:
        print(f"🔍 Analyzing {ticker}...")
        
        try:
            result = orchestrate_analysis(ticker)
            
            discovery_recommendations.append({
                "symbol": ticker,
                "decision": result.decision,
                "score": result.weighted_score,
                "confidence": result.confidence,
                "dissent": len(result.dissenting_agents),
            })
            
            print(f"   ✅ {ticker}: {result.decision} ({result.weighted_score:.1f}/5, {result.confidence:.0%})")
        
        except Exception as e:
            print(f"   ❌ {ticker}: Error - {str(e)}")
    
    # ========================================================================
    # SUMMARY: SHOULD I ADD TO PORTFOLIO?
    # ========================================================================
    
    print("\n" + "="*70)
    print("🎯 DISCOVERY RESULTS: SHOULD I ADD TO PORTFOLIO?")
    print("="*70 + "\n")
    
    print(f"{'Symbol':<10} {'Decision':<10} {'Score':<10} {'Confidence':<12} {'Recommendation':<15}")
    print("-" * 70)
    
    for r in discovery_recommendations:
        rec = "✅ ADD" if r['decision'] == "BUY" else ("⏸️  MONITOR" if r['decision'] == "HOLD" else "❌ SKIP")
        print(
            f"{r['symbol']:<10} {r['decision']:<10} "
            f"{r['score']:.1f}/5{'':<5} {r['confidence']:.0%}{'':<7} {rec:<15}"
        )
    
    buy_count = sum(1 for r in discovery_recommendations if r['decision'] == "BUY")
    
    print("\n" + "="*70)
    if buy_count > 0:
        print(f"✅ DISCOVERY MODE: Found {buy_count} candidate(s) for adding")
    else:
        print(f"⏸️  DISCOVERY MODE: No strong buy candidates found (HOLD)")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_discovery_mode()
