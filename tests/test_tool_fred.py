"""
test_tool_fred.py
-----------------
Smoke-tests src/tools/fred.py (macro snapshot). Requires FRED_API_KEY in .env.
Run from project root:
    uv run python -m tests.test_tool_fred
"""

from dotenv import load_dotenv

load_dotenv()

from src.tools.fred import get_macro_snapshot  # noqa: E402

print("\n== fred.py tool ==\n")

snapshot = get_macro_snapshot()
for field, value in snapshot.model_dump().items():
    print(f"  {field:<18} {value}")
print()

checks = {
    "Fed funds in 0-20%": 0 <= snapshot.fed_funds <= 20,
    "CPI YoY in -5..20%": -5 <= snapshot.cpi_yoy <= 20,
    "Unemployment in 0-25%": 0 < snapshot.unemployment < 25,
    "Cached on second call": get_macro_snapshot() is snapshot,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
