"""
src/backtest/earnings.py
------------------------
Backtest of the earnings analyst. For every 10-Q and 10-K a company filed since
--start, the analyst runs as of the filing date (it sees only data filed on or
before that day) and its score is compared with the stock's later return.

  build     contexts.jsonl       labels and LLM prompt per (symbol, as_of): SEC data + embeddings
  score     scores_<model>.csv   LLM score per context (model: LLM_MODEL_AGENTS, temperature 0);
            --batch sends them as one batch job (about half price, up to 24 hours)
  evaluate  outcomes_<model>.csv and a printed report per scored model: returns from the
            close of the first trading day after as_of, 21/63/126 days, in excess of SPY

Each step appends as it goes and skips finished rows on a rerun; a failed row
is logged with its stack trace, recorded with its error and retried next run.

Run (see docs/BACKTEST.md):
    uv run python -m src.backtest.earnings build --tickers AAPL,MSFT,JPM
    uv run python -m src.backtest.earnings score
    uv run python -m src.backtest.earnings evaluate
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from src import config
from src.agent.scoring import AgentScore
from src.analysts.earnings import (
    SIGNALS,
    EarningsAnalysis,
    EarningsContext,
    build_earnings_context,
    earnings_messages,
    finish_earnings,
    score_earnings,
)
from src.tools.edgar import delete_filings, get_filings_since
from src.utils.batch import run_batch
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_OUT = Path("data/backtest/earnings")
SCORE_FIELDS = ["symbol", "as_of", "model", "score", "decision", "confidence", "guidance", "reasoning", "error"]
LABELS = ("eps_trend", "momentum", "quality")

_write_lock = threading.Lock()


def parse_tickers(value: str) -> list[str]:
    """Comma-separated symbols, or a .csv file with a header row ('symbol' column, else the first)."""
    if value.endswith(".csv"):
        frame = pd.read_csv(value)
        column = "symbol" if "symbol" in frame.columns else frame.columns[0]
        return [str(s).strip().upper() for s in frame[column].dropna()]
    return [s.strip().upper() for s in value.split(",") if s.strip()]


def _latest(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Last row per (symbol, as_of): a rerun's row replaces a failed one."""
    return {(r["symbol"], r["as_of"]): r for r in rows}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open()] if path.exists() else []


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _append_jsonl(path: Path, row: dict) -> None:
    with _write_lock, path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _append_csv(path: Path, row: dict) -> None:
    with _write_lock:
        new = not path.exists()
        with path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SCORE_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)


# --- build --------------------------------------------------------------------


def build(symbols: list[str], start: date, out: Path, workers: int) -> None:
    """One context per 10-Q/10-K filed since start, built as of its filing date."""
    config.QDRANT_PATH = config.BACKTEST_QDRANT_PATH  # before the first Qdrant use
    path = out / "contexts.jsonl"
    done = {key for key, row in _latest(_read_jsonl(path)).items() if not row.get("error")}

    def run(symbol: str) -> None:
        try:
            filings = [f for f in get_filings_since(symbol, start) if f.filing_type in ("10-K", "10-Q")]
        except Exception:
            logger.exception(f"{symbol}: could not list filings")
            return
        for filing in reversed(filings):  # oldest first
            if (symbol, filing.filed_date) in done:
                continue
            row = {"symbol": symbol, "as_of": filing.filed_date, "form": filing.filing_type}
            try:
                context = build_earnings_context(symbol, date.fromisoformat(filing.filed_date))
                row |= context.model_dump(mode="json")
            except Exception as e:
                logger.exception(f"{symbol} as of {filing.filed_date}: build failed")
                row["error"] = repr(e)
            _append_jsonl(path, row)
        delete_filings(symbol)  # keeps the local index small
        logger.info(f"{symbol}: {len(filings)} filings since {start}")

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(run, symbols))


# --- score --------------------------------------------------------------------


def _model_slug(model: str) -> str:
    return model.replace("/", "_")


def _score_row(model: str, context: EarningsContext, agent_score: AgentScore, analysis: EarningsAnalysis | None) -> dict:
    return {
        "symbol": context.symbol,
        "as_of": context.as_of.isoformat(),
        "model": model,
        "score": agent_score.score,
        "decision": agent_score.decision,
        "confidence": agent_score.confidence,
        "guidance": analysis.guidance_signal if analysis else "",
        "reasoning": agent_score.reasoning,
    }


def score(out: Path, workers: int, batch: bool = False) -> None:
    """Score every built context with config.LLM_MODEL_AGENTS at temperature 0."""
    contexts = [r for r in _latest(_read_jsonl(out / "contexts.jsonl")).values() if not r.get("error")]
    model = config.LLM_MODEL_AGENTS
    path = out / f"scores_{_model_slug(model)}.csv"
    done = {key for key, row in _latest(_read_csv(path)).items() if not row["error"]}
    todo = [EarningsContext.model_validate(r) for r in contexts if (r["symbol"], r["as_of"]) not in done]
    logger.info(f"Scoring {len(todo)} of {len(contexts)} contexts with {model}{' (batch)' if batch else ''}")
    if batch:
        _score_batch(model, todo, path, out / f"batch_{_model_slug(model)}.json")
        return

    def run(context: EarningsContext) -> None:
        try:
            agent_score, analysis = score_earnings(context, temperature=config.BACKTEST_TEMPERATURE)
            row = _score_row(model, context, agent_score, analysis)
        except Exception as e:
            logger.exception(f"{context.symbol} as of {context.as_of}: scoring failed")
            row = {"symbol": context.symbol, "as_of": context.as_of.isoformat(), "model": model, "error": repr(e)}
        _append_csv(path, row)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(run, todo))


def _score_batch(model: str, todo: list[EarningsContext], path: Path, state: Path) -> None:
    """One batch job for every context with a prompt; contexts without SEC data need no LLM."""
    for context in (c for c in todo if c.prompt is None):
        _append_csv(path, _score_row(model, context, *score_earnings(context)))
    contexts = {f"{c.symbol}|{c.as_of}": c for c in todo if c.prompt is not None}
    if not contexts:
        return

    messages = {cid: earnings_messages(c) for cid, c in contexts.items()}
    results = run_batch(model, messages, EarningsAnalysis, config.BACKTEST_TEMPERATURE, state)
    for cid, context in contexts.items():
        result = results[cid]
        if isinstance(result, str):
            logger.error(f"{context.symbol} as of {context.as_of}: batch request failed: {result}")
            row = {"symbol": context.symbol, "as_of": context.as_of.isoformat(), "model": model, "error": result}
        else:
            row = _score_row(model, context, finish_earnings(context, result), result)
        _append_csv(path, row)


# --- evaluate -----------------------------------------------------------------


def excess_return(closes: pd.DataFrame, symbol: str, as_of: str, days: int) -> float:
    """
    Stock return minus SPY return, from the close of the first trading day after
    as_of to the close `days` trading days later; NaN if not yet available.
    """
    entry = closes.index.searchsorted(pd.Timestamp(as_of), side="right")
    exit_ = entry + days
    if symbol not in closes or exit_ >= len(closes):
        return math.nan
    stock, spy = closes[symbol], closes["SPY"]
    return (stock.iloc[exit_] / stock.iloc[entry] - 1) - (spy.iloc[exit_] / spy.iloc[entry] - 1)


def quarterly_ic(frame: pd.DataFrame, signal: str, target: str) -> pd.Series:
    """
    Rank correlation of signal and target within each filing quarter (one earnings
    season), for quarters with at least config.BACKTEST_MIN_GROUP samples.
    """
    ics = {}
    for quarter, group in frame.groupby("quarter"):
        group = group[[signal, target]].dropna()
        if len(group) >= config.BACKTEST_MIN_GROUP and group[signal].nunique() > 1:
            ics[quarter] = group[signal].rank().corr(group[target].rank())
    return pd.Series(ics, dtype=float)


def _ic_summary(frame: pd.DataFrame, signal: str, target: str) -> dict:
    ics = quarterly_ic(frame, signal, target)
    n, half = len(ics), len(ics) // 2
    return {
        "quarters": n,
        "mean IC": ics.mean(),
        "t-stat": ics.mean() / ics.std() * math.sqrt(n) if n > 1 and ics.std() > 0 else math.nan,
        "% IC > 0": (ics > 0).mean() * 100 if n else math.nan,
        "early IC": ics.iloc[:half].mean(),
        "late IC": ics.iloc[half:].mean(),
    }


def _ic_table(summaries: dict[str, dict]) -> str:
    table = pd.DataFrame(summaries).T.astype({"quarters": int})
    return table.to_string(float_format="{:.3f}".format)


def add_outcomes(frame: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """Excess returns per horizon, filing quarter, and the rule-baseline and guidance signals."""
    frame = frame.copy()
    for days in config.BACKTEST_HORIZONS:
        frame[f"excess_{days}d"] = [
            excess_return(closes, s, a, days) for s, a in zip(frame["symbol"], frame["as_of"])
        ]
    frame["quarter"] = pd.PeriodIndex(frame["as_of"], freq="Q").astype(str)
    # Rule baseline: mean +1/0/-1 signal of the labels computed in code, no LLM.
    frame["rule"] = pd.concat([frame[label].map(SIGNALS) for label in LABELS], axis=1).mean(axis=1)
    frame["guidance_signal"] = frame["guidance"].map(SIGNALS)
    return frame


def report(frame: pd.DataFrame, model: str, failed: int) -> str:
    lines = [
        f"== Earnings backtest: {model} ==",
        f"{len(frame)} scored samples ({failed} failed), {frame['symbol'].nunique()} tickers, "
        f"quarters {frame['quarter'].min()} to {frame['quarter'].max()}",
    ]
    for days in config.BACKTEST_HORIZONS:
        target = f"excess_{days}d"
        data = frame.dropna(subset=[target])
        primary = " (primary)" if days == 63 else ""
        lines.append(f"\n-- {days} trading days{primary}: {len(data)} samples with an outcome --")
        if data.empty:
            continue

        signals = {"llm score": "score", "rule baseline": "rule", "guidance": "guidance_signal"}
        lines += [
            "Rank correlation (IC) with excess return, per filing quarter:",
            _ic_table({name: _ic_summary(data, col, target) for name, col in signals.items()}),
        ]

        by_decision = data.groupby("decision")[target].agg(["count", "mean"])
        by_decision["mean"] = (by_decision["mean"] * 100).map("{:+.2f}%".format)
        lines += ["Mean excess return by decision:", by_decision.to_string()]

        median = data["confidence"].median()
        by_confidence = {
            f"confidence < {median:.2f}": _ic_summary(data[data["confidence"] < median], "score", target),
            f"confidence >= {median:.2f}": _ic_summary(data[data["confidence"] >= median], "score", target),
        }
        lines += ["LLM score IC by confidence:", _ic_table(by_confidence)]
    return "\n".join(lines)


def evaluate(out: Path) -> None:
    """Forward returns and the report for every scores_<model>.csv in out."""
    contexts = pd.DataFrame([r for r in _latest(_read_jsonl(out / "contexts.jsonl")).values() if not r.get("error")])
    contexts = contexts.drop(columns=["prompt", "error"], errors="ignore")
    symbols = sorted(contexts["symbol"].unique())
    closes = yf.download([*symbols, "SPY"], start=contexts["as_of"].min(), auto_adjust=True, progress=False)["Close"]

    for path in sorted(out.glob("scores_*.csv")):
        scores = pd.DataFrame(_latest(_read_csv(path)).values())
        ok = scores[scores["error"] == ""].astype({"score": int, "confidence": float})
        if ok.empty:
            print(f"\n{path.name}: no successful scores\n")
            continue
        frame = add_outcomes(contexts.merge(ok, on=["symbol", "as_of"]), closes)
        frame.to_csv(out / path.name.replace("scores_", "outcomes_"), index=False)
        print("\n" + report(frame, ok["model"].iloc[0], len(scores) - len(ok)) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the earnings analyst (docs/BACKTEST.md).")
    commands = parser.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build", help="contexts as of each 10-Q/10-K filing date")
    build_cmd.add_argument("--tickers", required=True, help="comma-separated symbols or a .csv file")
    build_cmd.add_argument("--start", type=date.fromisoformat, default=date.fromisoformat(config.BACKTEST_START))
    build_cmd.add_argument("--workers", type=int, default=config.BACKTEST_BUILD_WORKERS)
    score_cmd = commands.add_parser("score", help="LLM scores with LLM_MODEL_AGENTS")
    score_cmd.add_argument("--workers", type=int, default=config.BACKTEST_SCORE_WORKERS)
    score_cmd.add_argument("--batch", action="store_true", help="one batch job via the LLM_* provider (OpenAI or OpenRouter)")
    evaluate_cmd = commands.add_parser("evaluate", help="forward returns and the report")
    for cmd in (build_cmd, score_cmd, evaluate_cmd):
        cmd.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output directory (default {DEFAULT_OUT})")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    if args.command == "build":
        build(parse_tickers(args.tickers), args.start, args.out, args.workers)
    elif args.command == "score":
        score(args.out, args.workers, args.batch)
    else:
        evaluate(args.out)


if __name__ == "__main__":
    main()
