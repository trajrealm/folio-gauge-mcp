"""
tests/test_mode_individual.py
Test Individual (Ticker) Mode

Tests single-stock analysis with 9 core analysts.
Run with: python tests/test_mode_individual.py
"""

from dotenv import load_dotenv
load_dotenv()

from src.orchestrator.aggregator import orchestrate_analysis
import src.config as config


def test_individual_mode():
    """
    Test individual mode: Analyze single ticker with all 9 analysts.
    """
    
    print("\n" + "="*70)
    print("🧪 INDIVIDUAL MODE TEST (Single Ticker)")
    print("="*70 + "\n")
    
    # Test multiple tickers
    tickers = ["AAPL",] # "MSFT", "TSLA"]
    
    for ticker in tickers:
        print(f"\n📊 Analyzing {ticker}...")
        print("-" * 70)
        
        try:
            result = orchestrate_analysis(ticker)
            
            print(f"  Decision:       {result.decision}")
            print(f"  Score:          {result.weighted_score:.1f} / 5")
            print(f"  Confidence:     {result.confidence:.0%}")
            print(f"  Timeframe:      {result.timeframe}")
            print(f"  Analysts:       {len(result.agent_scores)} / 9")
            
            if result.conflicts:
                print(f"  ⚠️  Conflicts:  {len(result.conflicts)}")
                for conflict in result.conflicts[:2]:
                    print(f"      - {conflict}")
            
            if result.dissenting_agents:
                print(f"  🔴 Dissenters:   {', '.join(result.dissenting_agents[:3])}")
            
            if result.data_gaps:
                print(f"  📍 Data gaps:    {len(result.data_gaps)}")
                for gap in result.data_gaps[:2]:
                    print(f"      - {gap}")
        
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    
    print("\n" + "="*70)
    print("✅ INDIVIDUAL MODE TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_individual_mode()
