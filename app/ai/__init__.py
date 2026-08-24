"""AI Contextual Reasoning and Contradiction Detection Layer."""

from app.ai.contradictions import ContradictionDetector
from app.ai.gemini.client import GeminiClient
from app.ai.news import NewsContextManager

__all__ = [
    "ContradictionDetector",
    "GeminiClient",
    "NewsContextManager",
]
