# test_macro_analyst.py
from dotenv import load_dotenv
load_dotenv()

from src.analysts.macro import analyze_macro

# Ticker doesn't affect FRED data — macro is economy-wide
# but test with a real ticker to confirm AgentScore returns correctly
score = analyze_macro("AAPL")

print(f"Agent:      {score.agent}")
print(f"Decision:   {score.decision}")
print(f"Score:      {score.score}/5")
print(f"Confidence: {score.confidence:.0%}")
print(f"Reasoning:  {score.reasoning}")
print(f"Timeframe:  {score.timeframe}")
if score.data_gaps:
    print(f"Data gaps:  {score.data_gaps}")