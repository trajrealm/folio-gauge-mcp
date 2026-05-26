# test_fred_tool.py
from dotenv import load_dotenv
load_dotenv()

from src.tools.fred import get_economic_indicators

indicators = get_economic_indicators()

print(f"Fed Funds Rate:     {indicators.fed_funds_rate}%")
print(f"Unemployment Rate:  {indicators.unemployment_rate}%")
print(f"CPI YoY Change:     {indicators.cpi_yoy_change}%")
print(f"Yield Spread 10Y2Y: {indicators.yield_spread_10y2y}%")
print(f"GDP Growth Rate:    {indicators.gdp_growth_rate}%")
print(f"VIX Index:          {indicators.vix_index}")
print(f"Fetched At:         {indicators.fetched_at}")