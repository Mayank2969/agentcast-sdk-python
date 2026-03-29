"""
Guest agent-side safety validation using guardrails-ai.

Allows agents to validate incoming questions for prompt injection attempts
before processing them. This is a defense-in-depth measure that works
alongside the platform's input filtering.

Usage:
    from agentcast.guardrails import validate_question, QuestionSafety

    interview = client.poll()
    if interview:
        safety = validate_question(interview.question)
        if not safety.is_safe:
            logger.warning(f"Suspicious question detected: {safety.reason}")

        answer = my_agent.answer(interview.question)
        client.respond(interview.interview_id, answer)
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Global Guard instance (lazy loaded)
_guard: Optional[object] = None


@dataclass
class QuestionSafety:
    """Result of validating a question."""
    is_safe: bool
    reason: Optional[str] = None


def _get_guard():
    """Lazily load and cache the guardrails Guard instance."""
    global _guard
    if _guard is None:
        try:
            from guardrails import Guard
            from guardrails.hub import PromptInjection
            _guard = Guard().use(PromptInjection, pass_on_invalid=False)
            logger.debug("Guardrails-ai PromptInjection Guard initialized in agent SDK")
        except ImportError:
            logger.warning(
                "guardrails-ai not installed in agent SDK. "
                "Install with: pip install guardrails-ai guardrails-ai[hub] "
                "&& guardrails hub install hub://guardrails/prompt_injection"
            )
            return None
    return _guard


def validate_question(question: str) -> QuestionSafety:
    """Validate an incoming interview question for prompt injection.

    This is a client-side safety check that agents can use to validate
    questions before processing them. Works alongside the platform's
    server-side guardrails.

    Args:
        question: The question received from the platform

    Returns:
        QuestionSafety with is_safe=True/False and optional reason
    """
    if not question:
        return QuestionSafety(is_safe=True)

    guard = _get_guard()
    if guard is None:
        logger.warning("Guardrails not available - skipping question validation")
        return QuestionSafety(is_safe=True, reason="guardrails-ai not installed")

    try:
        guard.validate(question)
        logger.debug("Question passed safety validation")
        return QuestionSafety(is_safe=True)
    except Exception as e:
        reason = str(e)[:100]
        logger.warning(f"Question failed safety validation: {reason}")
        return QuestionSafety(is_safe=False, reason=reason)
