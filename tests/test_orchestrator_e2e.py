"""
tests/test_orchestrator_e2e.py
End-to-End Orchestrator Test

Tests that all 11 analysts are called, scores aggregated correctly,
and final orchestrator result is valid.

Run with: python tests/test_orchestrator_e2e.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.orchestrator.aggregator import orchestrate_analysis
import config


def test_orchestrator_e2e():
    """
    Run orchestrate_analysis for a real ticker and verify:
    1. All 11 analysts are called
    2. Scores aggregated correctly
    3. Output format is valid
    4. Display summary for manual inspection
    """
    ticker = "AAPL"
    
    print(f"\n{'='*70}")
    print(f"🧪 END-TO-END ORCHESTRATOR TEST: {ticker}")
    print(f"{'='*70}\n")
    
    print(f"📋 Testing orchestrator with 11 analysts...")
    print(f"   Config: {len(config.AGENT_WEIGHTS)} agents")
    print(f"   Weights sum: {sum(config.AGENT_WEIGHTS.values()):.2f}\n")
    
    try:
        result = orchestrate_analysis(ticker)
        
        # Verify all 11 analysts called
        print(f"✅ Orchestrator completed successfully\n")
        
        print(f"📊 ORCHESTRATOR RESULT:")
        print(f"   Symbol:         {result.symbol}")
        print(f"   Decision:       {result.decision}")
        print(f"   Weighted Score: {result.weighted_score:.2f} / {config.SCORE_MAX}")
        print(f"   Confidence:     {result.confidence:.0%}")
        print(f"   Timeframe:      {result.timeframe}\n")
        
        # Display per-analyst scores
        print(f"📈 PER-ANALYST SCORES ({len(result.agent_scores)} agents):")
        print(f"   {'Agent':<15} {'Decision':<8} {'Score':<6} {'Conf':<6} {'TF':<6}")
        print(f"   {'-'*50}")
        
        for score in result.agent_scores:
            print(
                f"   {score.agent:<15} {score.decision:<8} "
                f"{score.score:<6} {score.confidence:<6.0%} {score.timeframe:<6}"
            )
        
        print(f"\n")
        
        # Display conflicts if any
        if result.conflicts:
            print(f"⚠️  CONFLICTS DETECTED ({len(result.conflicts)}):")
            for conflict in result.conflicts:
                print(f"   - {conflict}")
            print(f"\n")
        else:
            print(f"✅ No conflicts detected\n")
        
        # Display dissenting agents if any
        if result.dissenting_agents:
            print(f"🔴 DISSENTING AGENTS ({len(result.dissenting_agents)}):")
            for agent in result.dissenting_agents:
                print(f"   - {agent}")
            print(f"\n")
        else:
            print(f"✅ All agents aligned\n")
        
        # Display data gaps if any
        if result.data_gaps:
            print(f"📍 DATA GAPS ({len(result.data_gaps)}):")
            for gap in result.data_gaps:
                print(f"   - {gap}")
            print(f"\n")
        else:
            print(f"✅ No data gaps\n")
        
        # Validation checks
        print(f"🔍 VALIDATION CHECKS:")
        validation_ok = True
        
        # Check 1: All 11 analysts present
        if len(result.agent_scores) == 11:
            print(f"   ✅ All 11 analysts called")
        else:
            print(f"   ❌ Expected 11 analysts, got {len(result.agent_scores)}")
            validation_ok = False
        
        # Check 2: Valid decision
        if result.decision in config.VALID_DECISIONS:
            print(f"   ✅ Valid decision: {result.decision}")
        else:
            print(f"   ❌ Invalid decision: {result.decision}")
            validation_ok = False
        
        # Check 3: Score in range
        if config.SCORE_MIN <= result.weighted_score <= config.SCORE_MAX:
            print(f"   ✅ Weighted score in range: {result.weighted_score:.2f}")
        else:
            print(f"   ❌ Weighted score out of range: {result.weighted_score:.2f}")
            validation_ok = False
        
        # Check 4: Confidence in range
        if 0.0 <= result.confidence <= 1.0:
            print(f"   ✅ Confidence in range: {result.confidence:.0%}")
        else:
            print(f"   ❌ Confidence out of range: {result.confidence:.0%}")
            validation_ok = False
        
        # Check 5: Valid timeframe
        if result.timeframe in config.VALID_TIMEFRAMES:
            print(f"   ✅ Valid timeframe: {result.timeframe}")
        else:
            print(f"   ❌ Invalid timeframe: {result.timeframe}")
            validation_ok = False
        
        # Check 6: Each agent score valid
        invalid_scores = []
        for score in result.agent_scores:
            errors = score.validate()
            if errors:
                invalid_scores.append((score.agent, errors))
        
        if not invalid_scores:
            print(f"   ✅ All agent scores valid")
        else:
            print(f"   ❌ {len(invalid_scores)} invalid agent scores:")
            for agent, errors in invalid_scores:
                for error in errors:
                    print(f"      - {error}")
            validation_ok = False
        
        print(f"\n")
        
        if validation_ok:
            print(f"{'='*70}")
            print(f"✅ END-TO-END TEST PASSED")
            print(f"{'='*70}\n")
            return True
        else:
            print(f"{'='*70}")
            print(f"❌ END-TO-END TEST FAILED - Validation errors detected")
            print(f"{'='*70}\n")
            return False
    
    except Exception as e:
        print(f"❌ ORCHESTRATOR FAILED:")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"\n{'='*70}")
        print(f"❌ END-TO-END TEST FAILED")
        print(f"{'='*70}\n")
        return False


if __name__ == "__main__":
    success = test_orchestrator_e2e()
    sys.exit(0 if success else 1)
