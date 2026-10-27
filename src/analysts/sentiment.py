"""
src/analysts/sentiment.py
Sentiment Analyst Agent (retail sentiment and attention)

Each source is a tool the agent calls; each is optional (a failure is logged
with its stack trace and recorded as a data gap; the analysis continues with
the rest):
  - StockTwits posts: tag counts (code) and text tone (LLM)
  - Attention: ApeWisdom mention counts, StockTwits trending
  - Polymarket: non-price prediction markets, as context

Labels from numbers are computed in code and given to the LLM as facts.
News belongs to the news analyst and is not used here.
"""

from __future__ import annotations

from typing import Callable, Literal, TypeVar

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.agent.tool_agent import run_tool_agent
from src.tools.apewisdom import ApeWisdomMention, fetch_mentions
from src.tools.polymarket import fetch_polymarket_markets
from src.tools.stocktwits import StockTwitsSentiment, fetch_stocktwits_sentiment, fetch_stocktwits_trending
from src.utils.logger import get_logger

from .. import config

logger = get_logger(__name__)

T = TypeVar("T")
SIGNALS = {"bullish": 1, "neutral": 0, "bearish": -1}


class SentimentAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=strong bearish, 3=neutral, 5=strong bullish")
    text_tone: Literal["bullish", "neutral", "bearish", "not_assessable"] = Field(
        description="Tone of the StockTwits post texts"
    )
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _fetch(name: str, fn: Callable[[str], T], ticker: str, data_gaps: list[str]) -> T | None:
    """Run one source; on failure log the stack trace, record a data gap, return None."""
    try:
        return fn(ticker)
    except Exception as e:
        logger.exception(f"{name} failed for {ticker}")
        data_gaps.append(f"{name} unavailable: {e}")
        return None


def _tag_label(st: StockTwitsSentiment | None) -> str | None:
    """Net tagged sentiment (bullish - bearish) / tagged vs config.SENTIMENT_NET_BAND."""
    if st is None or st.bullish + st.bearish < config.SENTIMENT_MIN_TAGGED:
        return None
    net = (st.bullish - st.bearish) / (st.bullish + st.bearish)
    band = config.SENTIMENT_NET_BAND
    return "bullish" if net > band else "bearish" if net < -band else "neutral"


def _attention_label(mentions: ApeWisdomMention | None) -> str:
    if mentions is None:
        return "not ranked"
    if mentions.mentions < config.ATTENTION_MIN_MENTIONS:
        return "low"
    if not mentions.mentions_24h_ago:
        return "rising"
    change = mentions.mentions / mentions.mentions_24h_ago - 1
    band = config.ATTENTION_CHANGE_BAND
    return "rising" if change > band else "falling" if change < -band else "stable"


@tool(response_format="content_and_artifact")
def get_stocktwits_posts(ticker: str) -> tuple[str, dict]:
    """Fetch the latest StockTwits posts for a stock ticker: bullish/bearish tag counts with
    a tagged-sentiment label computed in code (fact), and recent post texts."""
    gaps: list[str] = []
    st = _fetch("StockTwits posts", fetch_stocktwits_sentiment, ticker.upper(), gaps)
    tag = _tag_label(st)
    artifact = {"available": st is not None, "tag": tag, "gaps": gaps}
    if st is None:
        return f"StockTwits posts unavailable for {ticker}.", artifact
    lines = [
        f"StockTwits latest {st.bullish + st.bearish + st.untagged} posts: "
        f"{st.bullish} tagged bullish, {st.bearish} tagged bearish, {st.untagged} untagged",
        f"Tagged sentiment (fact): {tag or 'not assessable (too few tagged posts)'}",
    ]
    lines += [f"  - {m[:200]}" for m in st.messages[: config.SENTIMENT_MESSAGES_FOR_LLM]]
    return "\n".join(lines), artifact


@tool(response_format="content_and_artifact")
def get_forum_attention(ticker: str) -> tuple[str, dict]:
    """Fetch ApeWisdom mention rank and 24h mention change on stock discussion forums for a
    stock ticker, with an attention label computed in code (fact)."""
    gaps: list[str] = []
    mentions = _fetch("ApeWisdom mentions", fetch_mentions, ticker.upper(), gaps)
    attention = _attention_label(mentions)
    lines = []
    if mentions is not None:
        lines.append(
            f"ApeWisdom: rank {mentions.rank}, {mentions.mentions} mentions in 24h "
            f"(prior 24h: {mentions.mentions_24h_ago}), rank 24h ago: {mentions.rank_24h_ago or 'n/a'}"
        )
    lines.append(f"ApeWisdom attention (fact): {attention}")
    return "\n".join(lines), {"attention": attention, "gaps": gaps}


@tool(response_format="content_and_artifact")
def get_stocktwits_trending_status(ticker: str) -> tuple[str, dict]:
    """Check whether a stock ticker is trending on StockTwits now."""
    gaps: list[str] = []
    trending_list = _fetch("StockTwits trending", lambda _: fetch_stocktwits_trending(), ticker, gaps)
    if trending_list is None:
        return "StockTwits trending unavailable.", {"gaps": gaps}
    trending = ticker.upper() in {t.symbol for t in trending_list}
    return f"Trending on StockTwits now: {'yes' if trending else 'no'}", {"gaps": gaps}


@tool(response_format="content_and_artifact")
def get_prediction_markets(ticker: str) -> tuple[str, dict]:
    """Fetch non-price Polymarket prediction markets about a company (e.g. earnings beat,
    leadership, product launches) with the probability of the stated outcome."""
    gaps: list[str] = []
    markets = _fetch("Polymarket", fetch_polymarket_markets, ticker.upper(), gaps)
    artifact = {"available": bool(markets), "gaps": gaps}
    if not markets:
        return f"No Polymarket markets for {ticker}.", artifact
    lines = ["Polymarket (probability of the stated outcome):"]
    lines += [f"  - {m.question} {m.outcome}: {m.probability:.0%}" for m in markets]
    return "\n".join(lines), artifact


TOOLS = [get_stocktwits_posts, get_forum_attention, get_stocktwits_trending_status, get_prediction_markets]


def analyze_sentiment(ticker: str) -> AgentScore:
    """
    Flow:
      1. Agent calls each source tool (failures become data gaps); tagged-sentiment
         and attention labels are computed in code
      2. LLM reads post tone and scores; decision is derived from the score
      3. Confidence = coverage x agreement of tagged sentiment and text tone
    """
    ticker = ticker.upper()
    analysis, artifacts = run_tool_agent(
        "sentiment", TOOLS, SentimentAnalysis, f"Assess retail sentiment for {ticker}."
    )
    data_gaps = [gap for t in TOOLS for gap in artifacts[t.name]["gaps"]]
    stocktwits, markets = artifacts["get_stocktwits_posts"], artifacts["get_prediction_markets"]

    if not stocktwits["available"] and not markets["available"]:
        return AgentScore(
            agent="sentiment",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="short",
            reasoning="No directional sentiment data (StockTwits unavailable, no Polymarket markets)",
            confidence=0.1,
            data_gaps=data_gaps,
        )

    tag, attention = stocktwits["tag"], artifacts["get_forum_attention"]["attention"]
    labels_text = (
        f"tagged sentiment: {tag or 'not assessable (too few tagged posts)'}; "
        f"ApeWisdom attention: {attention}"
    )
    signals = [SIGNALS[v] for v in (tag, analysis.text_tone) if v in SIGNALS]

    parts = [analysis.reasoning, f"{labels_text[0].upper() + labels_text[1:]}; text tone: {analysis.text_tone}."]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="sentiment",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="short",
        reasoning="Sentiment: " + " ".join(parts),
        confidence=compute_confidence(len(signals) / 2, signals),
        data_gaps=data_gaps,
    )
