"""
src/analysts/news.py
News Analyst Agent

The LLM classifies each recent article (relevance, sentiment, materiality),
a text task. Code then computes net sentiment, score and confidence from
those labels, so the score is traceable to the articles behind it.
Errors propagate to the caller.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.tools.news import NewsArticle, get_ticker_news
from src.utils.llm import get_llm

from .. import config

SENTIMENT = {"positive": 1, "neutral": 0, "negative": -1}


class ArticleLabel(BaseModel):
    index: int = Field(description="Article number from the list")
    relevant: bool = Field(description="Primarily about this company")
    sentiment: Literal["positive", "neutral", "negative"]
    materiality: Literal["high", "low"]


class NewsClassification(BaseModel):
    articles: list[ArticleLabel]
    summary: str = Field(description="2-3 sentences on the main catalysts")
    key_stories: list[str]
    risk_flags: list[str]


def _format_articles(articles: list[NewsArticle]) -> str:
    lines = []
    for i, a in enumerate(articles):
        line = f"[{i}] {a.published:%Y-%m-%d} | {a.source} | {a.title}"
        lines.append(f"{line} - {a.summary}" if a.summary else line)
    return "\n".join(lines)


def _net(labels: list[ArticleLabel]) -> float | None:
    """Materiality-weighted (positive - negative) / total, in -1..1."""
    if not labels:
        return None
    weights = [config.NEWS_HIGH_MATERIALITY_WEIGHT if a.materiality == "high" else 1 for a in labels]
    return sum(w * SENTIMENT[a.sentiment] for w, a in zip(weights, labels)) / sum(weights)


def _band(net: float | None) -> int | None:
    if net is None:
        return None
    return 1 if net > config.NEWS_NET_BAND else -1 if net < -config.NEWS_NET_BAND else 0


def _score(net: float) -> int:
    strong, band = config.NEWS_STRONG_BAND, config.NEWS_NET_BAND
    if net > strong:
        return 5
    if net > band:
        return 4
    if net < -strong:
        return 1
    if net < -band:
        return 2
    return 3


def _neutral(ticker: str, reasoning: str, data_gaps: list[str]) -> AgentScore:
    return AgentScore(
        agent="news",
        symbol=ticker,
        decision="HOLD",
        score=3,
        timeframe="short",
        reasoning=reasoning,
        confidence=0.1,
        data_gaps=data_gaps,
    )


def analyze_news(ticker: str) -> AgentScore:
    """
    Flow:
      1. Fetch recent articles (tools/news.py)
      2. LLM labels each article and summarizes the catalysts
      3. Code computes net sentiment (high materiality counts double) -> score
      4. Confidence = relevant coverage x agreement of high-materiality and overall direction
    """
    feed = get_ticker_news(ticker)
    data_gaps = [f"News feed unavailable: {s}" for s in feed.failed_sources]
    if not feed.articles:
        return _neutral(ticker, f"No news in the last {config.NEWS_MAX_AGE_DAYS} days", data_gaps + ["No recent news"])

    llm = get_llm(config.LLM_MODEL_AGENTS, config.LLM_TEMPERATURE_AGENTS)
    result: NewsClassification = llm.with_structured_output(NewsClassification).invoke(
        [
            {"role": "system", "content": load_prompt("news")},
            {"role": "user", "content": f"Classify these articles for {ticker}:\n\n{_format_articles(feed.articles)}"},
        ],
        config={"run_name": "News Agent"},
    )

    relevant = [a for a in result.articles if a.relevant and 0 <= a.index < len(feed.articles)]
    if not relevant:
        return _neutral(ticker, "No relevant news", data_gaps + ["No relevant news"])

    net = _net(relevant)
    high = [a for a in relevant if a.materiality == "high"]
    signals = [s for s in (_band(net), _band(_net(high))) if s is not None]
    counts = {s: sum(a.sentiment == s for a in relevant) for s in SENTIMENT}
    facts = (
        f"{len(relevant)} relevant of {len(feed.articles)} articles "
        f"({counts['positive']} positive, {counts['neutral']} neutral, {counts['negative']} negative; "
        f"{len(high)} high materiality); net sentiment {net:+.2f}."
    )

    parts = [result.summary, facts]
    if result.key_stories:
        parts.append("Key stories: " + "; ".join(result.key_stories) + ".")
    if result.risk_flags:
        parts.append("Risks: " + ", ".join(result.risk_flags) + ".")

    score = _score(net)
    return AgentScore(
        agent="news",
        symbol=ticker,
        decision=decision_from_score(score),
        score=score,
        timeframe="short",
        reasoning="News: " + " ".join(parts),
        confidence=compute_confidence(min(1.0, len(relevant) / config.NEWS_FULL_COVERAGE), signals),
        data_gaps=data_gaps,
    )
