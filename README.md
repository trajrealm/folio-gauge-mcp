# folio-gauge

Multi-agent stock analysis in Python 3.12, built on LangGraph and OpenAI, using free data sources. Runs as a Python library or as an MCP server inside Claude Desktop.

Eight analysts score a stock in parallel. Their scores are combined into a **short-term** view (price and news flow) and a **long-term** view (business and valuation). The two views are reconciled into a decision with a risk plan and an investment thesis. Numbers and labels are computed in code; the LLMs read text, weigh context and explain.

## Quick start

```bash
git clone https://github.com/yourusername/folio-gauge-mcp.git
cd folio-gauge-mcp
uv sync                 # or: python3.12 -m venv .venv && pip install -r requirements.txt
cp .env.example .env    # then fill in the keys below
```

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | gpt-4o-mini (analysts) and gpt-4o (evaluator) |
| `FRED_API_KEY` | macro data ([free key](https://fred.stlouisfed.org/docs/api/api_key.html)) |
| `EDGAR_USER_AGENT` | SEC requires a contact, e.g. `folio-gauge you@example.com` |
| `QDRANT_PATH` | optional; local vector index for SEC filings (default `data/qdrant`, no server needed) |
| `LANGSMITH_*` | optional tracing |

## How it works

```
analyze_ticker(symbol)
  8 analysts in parallel           each returns score 1-5, decision, confidence, reasoning
    short term: technical, sentiment, news, sector
    long term:  fundamentals, earnings, peers, macro
  -> consensus per horizon         confidence-weighted; confidence = mean confidence x agreement
  -> combined decision + setup     aligned | long_term | accumulate | trade | none
  -> evaluator                     position size, ATR stop-loss, 2:1 take-profit, gpt-4o thesis
```

| Setup | When | Plan |
|---|---|---|
| aligned / long_term | both horizons agree, or the long term leads | full position (10% x confidence) |
| accumulate | long-term BUY, short-term SELL | starter position (half), add when the trend turns |
| trade | short-term BUY without long-term support | half size, tighter stop |
| held for low confidence | the leading horizon's confidence < 0.4 | HOLD |

| Analyst | Data |
|---|---|
| technical | yfinance price/volume: SMA 50/200, RSI, MACD, returns, volume balance |
| fundamentals | yfinance ratios: valuation, profitability, financial health |
| peers | yfinance industry peers: premium/discount to the peer median |
| sector | SPDR sector ETF vs SPY, stock vs sector |
| earnings | SEC XBRL financials + MD&A / earnings press releases (RAG, local Qdrant) |
| news | Yahoo Finance, Google News, Seeking Alpha RSS |
| sentiment | StockTwits, ApeWisdom mentions, Polymarket |
| macro | FRED (rates, CPI, unemployment, GDP, yield curve, VIX), judged per sector |

Thresholds and weights live in `src/config.py`; prompts in `prompts/<agent>.md`.

## Python usage

```python
from src.agent.graph import analyze_ticker, format_analysis
from src.discovery import run_discovery
from src.portfolio.loader import load_portfolio_csv
from src.portfolio.review import run_portfolio_review

print(format_analysis(analyze_ticker("MSFT")))                     # one stock, ~15s
report = run_portfolio_review(load_portfolio_csv("portfolio.csv"))  # columns: symbol,qty,avg_cost,type
discovery = run_discovery(limit=10)                                 # trending stocks, analyzed and ranked
```

## MCP server (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "folio-gauge": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/folio-gauge-mcp", "python", "-m", "src.mcp.server"]
    }
  }
}
```

Use the full path to `uv` (`which uv`) if Claude Desktop cannot find it. Then ask, e.g. *"Analyze BAC"*, *"What's NVDA's RSI?"* or *"Find trending stocks worth researching"*.

| Level | Tools |
|---|---|
| Data (no LLM) | `tool_market`, `tool_technical`, `tool_peers`, `tool_sector`, `tool_edgar`, `tool_edgar_search`, `tool_news`, `tool_fred`, `tool_stocktwits`, `tool_apewisdom`, `tool_polymarket` |
| Analysts | `analyst_technical`, `analyst_fundamentals`, `analyst_peers`, `analyst_sector`, `analyst_earnings`, `analyst_news`, `analyst_sentiment`, `analyst_macro` |
| Workflows | `analyze_ticker`, `review_portfolio` (holdings list or CSV path), `discover_stocks` (`limit`, default 10) |

Interactive testing in the browser with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run --directory /path/to/folio-gauge-mcp python -m src.mcp.server
```

## Testing

```bash
uv run pytest                                        # unit tests, no network
uv run python -m tests.test_tool_<name> [TICKER]     # one data tool, live
uv run python -m tests.test_analyst_<name> [TICKER]  # one analyst, live
uv run python -m tests.test_orchestrator [TICKER]    # full analysis
uv run python -m tests.test_portfolio_review [--analyze]
uv run python -m tests.test_discovery [--analyze]
uv run python -m tests.test_mcp_server [TICKER] [--full]  # MCP server over stdio
```
