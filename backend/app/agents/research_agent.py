import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List

from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools

from app.agents.model_factory import get_model

logger = logging.getLogger("super_tutor.research")


@dataclass
class ResearchResult:
    content: str
    sources: List[str] = field(default_factory=list)


def build_research_agent() -> Agent:
    return Agent(
        name="ResearchAgent",
        model=get_model(),
        tools=[DuckDuckGoTools(enable_search=True, enable_news=False, fixed_max_results=5)],
        instructions="""You are a research assistant. When given a topic, perform web research and synthesize findings.

Steps:
1. Run 2-3 targeted DuckDuckGo searches on the topic using different query angles.
2. Read and synthesize the results into a comprehensive content body of at least 600 words.
3. Collect the source URLs from your searches.

Return ONLY valid JSON with exactly two keys (no markdown fences, no explanation):
{
  "content": "<synthesized research text, at least 600 words, written as educational prose>",
  "sources": ["<url1>", "<url2>", "<url3>"]
}

Rules:
- content must be comprehensive educational prose covering the topic in depth
- sources must be an array of 3-5 URL strings from your searches
- Return ONLY valid JSON, no markdown fences, no explanation""",
    )


def _parse_json_safe(raw: str) -> dict:
    """Strip markdown fences and parse JSON; returns empty dict on failure."""
    # Remove triple-backtick fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {}


def run_research(topic: str, focus_prompt: str = "") -> ResearchResult:
    """Run the research agent for a topic, returning synthesized content and source URLs.

    Raises on provider/network failures — callers should handle and emit an error event.
    """
    agent = build_research_agent()
    input_text = topic
    if focus_prompt:
        input_text = f"{topic}\n\nFocus on: {focus_prompt}"

    logger.info("Research start — topic=%r focus=%r", topic[:80], focus_prompt[:40] if focus_prompt else "")
    _t = time.perf_counter()
    response = agent.run(input_text)
    raw = response.content if hasattr(response, "content") else str(response)

    data = _parse_json_safe(raw)
    content = data.get("content", "")
    sources = data.get("sources", [])

    if not isinstance(sources, list):
        sources = []
    sources = [s for s in sources if isinstance(s, str)]

    logger.info(
        "Research done — elapsed=%.2fs content_chars=%d sources=%d",
        time.perf_counter() - _t,
        len(content),
        len(sources),
    )
    return ResearchResult(content=content, sources=sources)
