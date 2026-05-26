"""
src/analysts/earnings.py
Earnings Analyst Agent

Analyzes earnings surprises, guidance, and earnings growth using SEC filings.
Uses RAG (Retrieval-Augmented Generation) to query 10-K and 10-Q filings
for earnings-specific signals:
  1. Earnings surprise history
  2. Earnings growth trends
  3. Forward guidance and management commentary
  4. Earnings quality and sustainability

Uses skill and prompt from markdown files to guide analysis.
Returns AgentScore with earnings-based outlook.
"""

from __future__ import annotations

from src.agent.scoring import AgentScore
from src.agent.knowledge import load_skill, get_system_message
from src.tools.edgar import (
    ingest_if_needed,
    query_filings,
    FilingQueryResult,
)
from langchain_openai import ChatOpenAI
from .. import config
import json
from src.utils.logger import get_logger
import traceback

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


EARNINGS_QUESTIONS = {
    "10-K": [
        "What is the historical earnings per share (EPS) trend over the past 3-5 years?",
        "How has the company's earnings quality evolved? Are there one-time items or non-recurring charges?",
        "What is management's outlook on future earnings growth?",
    ],
    "10-Q": [
        "Did the company beat or miss earnings estimates in this quarter?",
        "How did EPS compare to the prior year quarter?",
        "Did management provide any guidance or commentary on earnings outlook?",
    ],
}


def _query_and_format(symbol: str, questions: list[str], filing_type: str) -> str:
    """
    Query vector DB for earnings-specific questions and format results.

    Args:
        symbol: Stock ticker
        questions: List of earnings questions to query
        filing_type: Filing type filter ("10-K", "10-Q")
    """
    sections: list[str] = []

    for question in questions:
        try:
            result: FilingQueryResult = query_filings(
                symbol, question, filing_type=filing_type
            )

            if not result.answer_chunks:
                continue

            # Format chunks with their source dates
            chunks_text = "\n---\n".join(result.answer_chunks)
            section = f"Q: {question}\nSources: {filing_type} ({', '.join(set(result.filed_dates))})\n{chunks_text}"
            sections.append(section)
        except Exception as e:
            logger.error(f"Error querying filings for {symbol}, question: {question}, filing_type: {filing_type}: {str(e)}")

    return "\n\n".join(sections)


def _synthesize_with_llm(symbol: str, context: str) -> dict:
    """
    Use LLM to synthesize earnings-specific filing content into a structured analysis.
    Uses earnings skill and prompt from markdown files to guide analysis.
    """
    llm = _get_llm()

    # Load system prompt with embedded skill knowledge
    system_prompt = get_system_message("earnings", include_skill=True)

    user_prompt = f"""Analyze the following SEC filing excerpts for {symbol}'s earnings performance and outlook.

{context}

Based on these filings, provide your assessment of {symbol}'s earnings quality and growth trajectory.

Return ONLY a valid JSON object with this exact structure, no preamble or markdown:
{{
  "decision": "BUY|SELL|HOLD",
  "score": <1-5>,
  "confidence": <0.0-1.0>,
  "eps_trend": "strong|solid|flat|declining",
  "growth_rate": <float>,
  "beat_ratio": <0.0-1.0>,
  "guidance_signal": "raised|maintained|lowered|withdrawn",
  "quality_assessment": "high|medium|low",
  "reasoning": "<explanation>",
  "key_signals": [<list of signals>],
  "risk_flags": [<list of risks>]
}}"""

    try:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], config={"run_name": "Earnings Agent"})

        if not response.content or not response.content.strip():
            raise ValueError("Empty LLM response")
        return json.loads(response.content)
    except Exception as e:
        traceback.print_exc()
        logger.error(f"LLM synthesis error for {symbol}: {str(e)}. Defaulting to HOLD with low confidence.")
        return {
            "decision": "HOLD",
            "score": 3,
            "confidence": 0.3,
            "reasoning": f"LLM analysis failed: {str(e)}",
            "earnings_flags": ["LLM synthesis error"],
        }


def analyze_earnings(ticker: str) -> AgentScore:
    """
    Analyze earnings signals from SEC filings using RAG pipeline.

    Flow:
      1. Ingest filings into ChromaDB if not already done
      2. Query vector DB with earnings-specific questions for 10-K, 10-Q
      3. LLM synthesizes retrieved chunks into a structured score
      4. Return AgentScore focused on earnings quality and growth

    """
    data_gaps: list[str] = []

    try:
        # Step 1: Ingest filings (skips if already done)
        try:
            ingest_result = ingest_if_needed(ticker)

            if ingest_result.get("total", 0) == 0 and not ingest_result.get("skipped"):
                data_gaps.append("No filing text could be ingested")
                return AgentScore(
                    agent="earnings",
                    symbol=ticker,
                    decision="HOLD",
                    score=2,
                    timeframe="mid",
                    reasoning="No SEC filing data available for earnings analysis",
                    confidence=0.2,
                    data_gaps=data_gaps,
                )
        except Exception as e:
            logger.error(f"Filing ingestion error for {ticker}: {str(e)}")
            data_gaps.append(f"Filing ingestion error: {str(e)}")

        # Step 2: Query vector DB for earnings-specific content
        context_parts: list[str] = []

        for filing_type, questions in EARNINGS_QUESTIONS.items():
            section = _query_and_format(ticker, questions, filing_type)
            if section:
                context_parts.append(f"=== {filing_type} ===\n{section}")
            else:
                data_gaps.append(f"No {filing_type} earnings content retrieved")

        if not context_parts:
            data_gaps.append("Vector DB returned no earnings-specific results")
            return AgentScore(
                agent="earnings",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="SEC filings available but no earnings-specific content extracted",
                confidence=0.2,
                data_gaps=data_gaps,
            )

        full_context = "\n\n".join(context_parts)

        # Step 3: LLM synthesis for earnings signals
        llm_result = _synthesize_with_llm(ticker, full_context)

        decision = llm_result.get("decision", "HOLD")
        score = int(llm_result.get("score", 3))
        confidence = float(llm_result.get("confidence", 0.5))
        reasoning = llm_result.get("reasoning", "Earnings analysis complete.")
        earnings_flags = llm_result.get("earnings_flags", [])

        # Clamp score to valid range
        score = max(1, min(5, score))
        confidence = max(0.0, min(1.0, confidence))

        # Incorporate earnings flags into reasoning (not data_gaps)
        # Earnings flags are analyst observations, not missing data
        if earnings_flags:
            flag_str = ", ".join(earnings_flags)
            reasoning = f"{reasoning} Key findings: {flag_str}."

        return AgentScore(
            agent="earnings",
            symbol=ticker,
            decision=decision,
            score=score,
            timeframe="mid",  # earnings reflect quarterly/annual outlook
            reasoning=f"Earnings (RAG): {reasoning}",
            confidence=confidence,
            data_gaps=data_gaps,
        )

    except Exception as e:
        logger.error(f"Unexpected error in earnings analysis for {ticker}: {str(e)}")
        data_gaps.append(f"Earnings analysis error: {str(e)}")
        return AgentScore(
            agent="earnings",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="mid",
            reasoning=f"Earnings analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
